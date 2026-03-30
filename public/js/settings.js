/**
 * Settings modal for user configuration.
 * STUB — Member B will implement
 *
 * Should provide UI to configure:
 * - AI API key, base URL, model (stored in localStorage)
 * - Game selection (maimai only, chunithm only, both)
 * - Currency per credit
 */

export function getSettings() {
  return {
    apiKey: localStorage.getItem('ai_api_key') || '',
    baseUrl: localStorage.getItem('ai_base_url') || 'https://api.openai.com/v1',
    model: localStorage.getItem('ai_model') || 'gpt-4',
  };
}

export function openSettings() {
  console.warn('Settings modal not yet implemented');
}
