/**
 * Browser-side AI agent with tool-calling.
 * Ported from ai_service/agent.py — uses OpenAI-compatible API directly (no LangChain).
 */
import { suggestSongs } from './tools/suggest-songs.js';
import { queryPlayData } from './tools/query-play-data.js';

// Cached data (loaded once on first tool call)
let _userData = null;
let _songsData = null;
let _playHistory = null;

async function loadUserData() {
  if (!_userData) {
    const res = await fetch('data/user.json');
    _userData = await res.json();
  }
  return _userData;
}

async function loadSongsData() {
  if (!_songsData) {
    const res = await fetch('data/songs.json');
    _songsData = await res.json();
  }
  return _songsData;
}

async function loadPlayHistory() {
  if (!_playHistory) {
    const res = await fetch('data/play-history.json');
    _playHistory = await res.json();
  }
  return _playHistory;
}

/** Clear cached data (call after data refresh). */
export function clearCache() {
  _userData = null;
  _songsData = null;
  _playHistory = null;
}

/** Get API config from localStorage. */
export function getApiConfig() {
  return {
    apiKey: localStorage.getItem('ai_api_key') || '',
    baseUrl: localStorage.getItem('ai_base_url') || 'https://api.openai.com/v1',
    model: localStorage.getItem('ai_model') || 'gpt-4',
  };
}

/** Save API config to localStorage. */
export function setApiConfig({ apiKey, baseUrl, model }) {
  if (apiKey) localStorage.setItem('ai_api_key', apiKey);
  if (baseUrl) localStorage.setItem('ai_base_url', baseUrl);
  if (model) localStorage.setItem('ai_model', model);
}

const SYSTEM_PROMPT = `You are a helpful AI assistant for a maimai (rhythm game) player.

You have access to these tools:
- suggest_songs_tool: Suggest songs to improve rating
- query_play_data_tool: Query daily play stats (play counts, ratings, trends)

Use the appropriate tool based on what the user asks.

MAIMAI RATING SYSTEM (Gen 3.5):
- Rating = Internal Level × Rank Constant × Achievement Rate (capped at 100.5%)
- Achievement rate = score / 10000 (e.g., 99.5% = 0.995)
- ALL PERFECT+ gives +1 bonus rating
- Rating color badges: Rainbow 16000+, Platinum 14500-14999, Gold 14000-14499, etc.
- Rating uses TOP 50 songs: 35 "old" + 15 "new" (new = songs from last 2 versions like PRiSM+ and CiRCLE)
- "NEW SONGS" means songs from the latest 2 game versions, NOT unplayed songs

IMPORTANT FORMATTING RULES:
- Show ALL songs from tool response, do not skip any
- Show score as percentage with 4 decimal places (e.g., 99.5000%, 100.5000%), NEVER show raw numbers like 1005000
- NEVER omit current_rank or current_score - they are REQUIRED fields
- Keep it concise but complete
- In target mode: 'gain_needed' shows how much rating is needed from you to reach the target. 'max_gain' shows the maximum rating you could actually gain if you achieve SSS+. ALWAYS show BOTH when available.

Format for suggest_songs response (target mode):

IMPROVE SONGS:
[title] by [artist] | [level] (.constant) | [current_score%] ([current_rank]) → [target_rank] [target_score%] | need +[gain_needed] (max +[max_gain])

Format for suggest_songs response (best_effort mode):

IMPROVE SONGS:
[title] by [artist] | [level] (.constant) | [current_score%] ([current_rank]) → [target_rank] [target_score%] | +[rating_gain] rating`;

const TOOLS = [
  {
    type: 'function',
    function: {
      name: 'suggest_songs_tool',
      description: 'Suggest songs to improve player rating. Use when player wants song recommendations.',
      parameters: {
        type: 'object',
        properties: {
          target_rating: { type: 'integer', description: 'Target rating to reach (optional)' },
          mode: { type: 'string', enum: ['auto', 'target', 'best_effort'], description: 'Suggestion mode' },
          max_suggestions: { type: 'integer', description: 'Maximum suggestions (default 5)' },
          difficulty_filter: { type: 'array', items: { type: 'string' }, description: 'Difficulties to include' },
        },
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'query_play_data_tool',
      description: 'Query daily play stats: play counts, ratings, trends. Use for questions like "how many times did I play this week".',
      parameters: {
        type: 'object',
        properties: {
          query: { type: 'string', description: 'The question about play data' },
        },
        required: ['query'],
      },
    },
  },
];

/**
 * Execute a tool call locally.
 */
async function executeTool(name, args) {
  if (name === 'suggest_songs_tool') {
    const userData = await loadUserData();
    const songsData = await loadSongsData();

    if (!userData || !userData.best) {
      return JSON.stringify({ error: 'No player data available. Please run the song scraper first.' });
    }
    if (!songsData || songsData.length === 0) {
      return JSON.stringify({ error: 'No songs data available. Please run the song scraper first.' });
    }

    const result = suggestSongs(userData, songsData, {
      targetRating: args.target_rating || null,
      mode: args.mode || 'auto',
      maxSuggestions: args.max_suggestions || 5,
      difficultyFilter: args.difficulty_filter || null,
    });
    return JSON.stringify(result, null, 2);
  }

  if (name === 'query_play_data_tool') {
    const playHistory = await loadPlayHistory();
    const result = await queryPlayData(args.query, playHistory);
    return JSON.stringify(result, null, 2);
  }

  return JSON.stringify({ error: `Unknown tool: ${name}` });
}

/**
 * Call the OpenAI-compatible chat completions API.
 */
async function chatCompletion(messages, { apiKey, baseUrl, model }, useTools = true) {
  const body = { model, messages };
  if (useTools) body.tools = TOOLS;

  const res = await fetch(`${baseUrl}/chat/completions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`,
    },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }

  return res.json();
}

/**
 * Run the agent with a user message.
 *
 * @param {string} userMessage
 * @param {Array} [conversationHistory=[]] - Previous messages in OpenAI format
 * @returns {Promise<string>} Agent's text response
 */
export async function runAgent(userMessage, conversationHistory = []) {
  const config = getApiConfig();
  if (!config.apiKey) {
    return 'Please set your AI API key in Settings first.';
  }

  const messages = [
    { role: 'system', content: SYSTEM_PROMPT },
    ...conversationHistory,
    { role: 'user', content: userMessage },
  ];

  // First call: may return tool calls
  const response = await chatCompletion(messages, config);
  const choice = response.choices[0];

  if (choice.finish_reason === 'tool_calls' || choice.message.tool_calls) {
    const toolCalls = choice.message.tool_calls;

    // Execute all tool calls
    const toolMessages = [];
    for (const tc of toolCalls) {
      const args = JSON.parse(tc.function.arguments || '{}');
      const result = await executeTool(tc.function.name, args);
      toolMessages.push({
        role: 'tool',
        tool_call_id: tc.id,
        content: result,
      });
    }

    // Second call: format the tool results
    const formattingMessages = [
      ...messages,
      choice.message, // AI message with tool_calls
      ...toolMessages,
    ];

    const finalResponse = await chatCompletion(formattingMessages, config, false);
    return finalResponse.choices[0].message.content || '';
  }

  return choice.message.content || '';
}
