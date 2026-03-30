# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chunimai Dashboard visualizes maimai and CHUNITHM arcade play history as GitHub-style contribution heatmaps. Fully static site deployed to GitHub Pages — no backend, no database.

- **Frontend**: Vanilla JavaScript with Cal-Heatmap and D3.js (`public/`)
- **AI Chat**: Browser-side agentic loop calling OpenAI-compatible API (`public/js/agent.js`)
- **Scraper**: Python + Playwright, runs in GitHub Actions only (`scraper/`)
- **Data**: JSON files committed to `public/data/` by GitHub Actions

## Commands

### Local Development
```bash
python3 -m http.server -d public 8000   # Serve static site at localhost:8000
```

### Scraper (runs in GitHub Actions, or locally with SEGA creds)
```bash
cd scraper
uv sync && uv run playwright install firefox
SEGA_USERNAME=... SEGA_PASSWORD=... uv run python main.py
```

## Architecture

### Data Flow
```
scrape-daily.yml (cron 22:00 BKK) → Playwright scrapes SEGA → appends to play-history.json → git push
scrape-songs.yml (weekly Sunday)   → ghcr.io/leomotors/maimai-scraper:v1 Docker → user.json
                                   → curl maimai.wonderhoy.me/api/musicData → songs.json → git push
deploy.yml (on push to public/**)  → deploy public/ to GitHub Pages

Browser → fetch("data/play-history.json") → Cal-Heatmap
Browser → fetch("data/user.json") + fetch("data/songs.json") → AI agent → OpenAI API (user's key)
```

### JSON Data Schema

**`public/data/play-history.json`** — Array of daily entries (newest first):
```json
[{"play_date":"2026-03-29","scrape_failed":false,"failure_reason":null,"maimai_play_count":0,"maimai_cumulative":628,"maimai_rating":14416,"chunithm_play_count":0,"chunithm_cumulative":306,"chunithm_rating":15.27}]
```
Note: Legacy entries use `date`/`maimai`/`chunithm` keys instead of `play_date`/`maimai_play_count`/`chunithm_play_count`.

**`public/data/user.json`** — Full player snapshot from maimai-scraper:
- `profile`: player name, rating, play count
- `best`: top 35 old songs (title, chartType, difficulty, score, dxScore, ...)
- `current`: top 15 new songs
- `allRecords`: all played songs history
- `history`: recent 50 plays with timestamps

**`public/data/songs.json`** — All songs from maimai API (musicData) with constants per difficulty.

### Module Structure (`public/js/`)
- **`rating.js`**: Rating math — `calculateSongRating(constant, score)` uses `Math.trunc()` (truncation, not rounding). `calcRating()` computes total locally (no external API). Map keys: `"title|chartType|difficulty"`.
- **`tools/suggest-songs.js`**: Two modes: `best_effort` (improvements + new songs) and `target` (path to reach target rating). Imports from `rating.js`.
- **`agent.js`**: Browser-side agentic loop. Direct `fetch()` to OpenAI-compatible API. BYOK pattern — API key in localStorage.
- **`tools/query-play-data.js`**: Queries play-history.json for stats (stub, WIP).
- **`settings.js`**: Settings modal for API key configuration (stub, WIP).

### Scraper (`scraper/`)
- **`scraper.py`**: Playwright Firefox scraping SEGA portals (login, extract cumulative + rating)
- **`main.py`**: Reads play-history.json → scrapes → calculates delta → appends → writes
- **`discord.py`**: Discord webhook notifications (daily/weekly/monthly)
- **`constants.py`**: SEGA URLs and CSS selectors

### `config.json` (repo root)
User configuration: which games to track, currency for cost calculation, game version.

## GitHub Secrets (for Actions)

| Secret | Required | Purpose |
|---|---|---|
| `SEGA_USERNAME` | Yes | SEGA ID login |
| `SEGA_PASSWORD` | Yes | SEGA password |
| `DISCORD_WEBHOOK_URL` | No | Discord notifications |

## Key Implementation Notes

- No bundler, no build step. Native ES modules in the browser.
- Rating formula: `Math.trunc(constant * achievement * factor)` — must match Python `int()` truncation.
- `calcRating()` in `rating.js` replaces the external API call (`maimai.wonderhoy.me/api/calcRating`) because the API has discrepancies (e.g., unrevealed songs like 7 wonders).
- Spillover logic for heatmap year boundaries is in `index.html` (client-side filtering).
- The scraper calculates daily play deltas: `max(0, today_cumulative - prev_cumulative)`.
