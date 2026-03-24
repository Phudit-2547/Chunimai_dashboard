"""
LangChain agent with tools for maimai rating assistant.
"""
import os
import json

from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from rating import get_full_player_data, get_all_songs
from tools.suggest_songs import suggest_songs

load_dotenv()


# Initialize LLM
def get_llm():
    """Get LLM instance."""
    api_key = os.getenv("AI_API_KEY")
    if not api_key:
        raise ValueError("AI_API_KEY not set")
    
    base_url = os.getenv("AI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("AI_MODEL", "gpt-4")
    
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=0.7,
    )


@tool
def suggest_songs_tool(
    target_rating: int | None = None,
    mode: str = "auto",
    max_suggestions: int = 5,
    difficulty_filter: list[str] | None = None,
) -> str:
    """
    Suggest songs to improve player rating.
    
    Use this when player wants song recommendations to improve their rating.
    Examples: "What songs should I play to improve?", "Recommend some songs"
    
    Args:
        target_rating: Target rating to reach (optional). If not provided, uses best_effort mode.
        mode: "auto" = best_effort if target_rating None, "target" = target mode, "best_effort" = max suggestions
        max_suggestions: Maximum number of songs to suggest (default 5)
        difficulty_filter: List of difficulties to include (default: ["master", "expert", "advanced"])
    
    Returns:
        JSON string with song suggestions
    """
    # Get player data (full history)
    player_data = get_full_player_data()
    if isinstance(player_data, dict) and "error" in player_data:
        return json.dumps(player_data, ensure_ascii=False)
    
    # Get all songs
    all_songs = get_all_songs()
    
    # Call suggest_songs
    result = suggest_songs(
        player_data=player_data,
        all_songs=all_songs,
        target_rating=target_rating,
        mode=mode,
        max_suggestions=max_suggestions,
        difficulty_filter=difficulty_filter,
    )
    
    return json.dumps(result, ensure_ascii=False, indent=2)


# Create tools list
TOOLS = [suggest_songs_tool]


def create_agent():
    """Create LangChain agent with tools."""
    llm = get_llm()
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(TOOLS)
    
    return llm_with_tools


def run_agent(user_message: str, conversation_history: list | None = None) -> str:
    """
    Run the agent with a user message.
    
    Args:
        user_message: User's message
        conversation_history: Optional list of previous messages
    
    Returns:
        Agent's response
    """
    llm = get_llm()
    llm_with_tools = llm.bind_tools(TOOLS)
    
    # Build messages
    system_prompt = """You are a helpful AI assistant for a maimai (rhythm game) player.

You have access to these tools:
- suggest_songs_tool: Suggest songs to improve rating
- query_play_data: Query daily play stats (play_date, maimai_play_count, chunithm_play_count, maimai_rating, chunithm_rating) - can answer "how many times did I play this week/month", "my rating trend this month", etc. - NOT YET IMPLEMENTED

Use the appropriate tool based on what the user asks.
NOTE: query_play_data is not yet available. It cannot answer per-song history questions.

IMPORTANT FORMATTING RULES:
- Show ALL songs from tool response, do not skip any
- Show score as percentage with 4 decimal places (e.g., 99.5000%, 100.5000%), NEVER show raw numbers like 1005000
- NEVER omit current_rank or current_score - they are REQUIRED fields
- Keep it concise but complete
- In target mode: 'gain_needed' shows how much rating is needed from you to reach the target. 'max_gain' shows the maximum rating you could actually gain if you achieve SSS+. ALWAYS show BOTH when available.

Format for suggest_songs response (target mode):

IMPROVE SONGS:
[title] by [artist] | [level] (.constant) | [current_score%] ([current_rank]) → [target_rank] [target_score%] | need +[gain_needed] (max +[max_gain])

EXAMPLE:
IMPROVE SONGS:
Geranium by Osanzi feat.藍月なくる | 13+ (13.7) | 99.5780% (SS+) → SSS+ 100.5000% | need +3 (max +21)

Format for suggest_songs response (best_effort mode):

IMPROVE SONGS:
[title] by [artist] | [level] (.constant) | [current_score%] ([current_rank]) → [target_rank] [target_score%] | +[rating_gain] rating

EXAMPLE:
IMPROVE SONGS:
BOKUTO by じーざすP feat.kradness | 13 (13.4) | 99.5000% (SS+) → SSS 100.0000% | +7 rating
宙天 by t+pazolite vs かねこちはる | 13 (13.5) | 100.0000% (SSS) → SSS+ 100.5000% | +12 rating
"""
    
    messages = [SystemMessage(content=system_prompt)]
    
    # Add conversation history
    if conversation_history:
        for msg in conversation_history:
            messages.append(msg)
    
    # Add user message
    messages.append(HumanMessage(content=user_message))
    
    # Invoke LLM
    response = llm_with_tools.invoke(messages)
    
    # Check if LLM wants to call a tool
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_call = response.tool_calls[0]
        tool_name = tool_call["name"]
        tool_args = tool_call.get("args", {})
        tool_call_id = tool_call.get("id", "")
        
        # Execute tool
        if tool_name == "suggest_songs_tool":
            tool_result = suggest_songs_tool.invoke(tool_args)
        elif tool_name == "query_play_data":
            # tool_result = query_play_data_tool.invoke(tool_args)
            pass
        else:
            tool_result = f"Unknown tool: {tool_name}"
        
        # Build messages for formatting pass
        # Include the original response as AIMessage
        formatted_messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
            response,  # AIMessage with tool_calls
            ToolMessage(content=str(tool_result), tool_call_id=tool_call_id),
        ]
        
        # Get formatted response
        final_response = llm.invoke(formatted_messages)
        return final_response.content if hasattr(final_response, "content") else str(final_response)
    
    # No tool call, return direct response
    return response.content if hasattr(response, "content") else str(response)


if __name__ == "__main__":
    # Test the agent
    test_queries = [
        # "Suggest songs to improve my rating",
        "I want to get my rating to 15K what songs should I play?",
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"User: {query}")
        print(f"{'='*60}")
        try:
            response = run_agent(query)
            print(f"Agent: {response}")
        except Exception as e:
            print(f"Error: {e}")
