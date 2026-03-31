# ⚠️ ARCHIVED

**This project has been archived (March 2026).**

- Development continues in a new repository: **[new-repo-link]**
- This version uses plaintext JSON files (no encryption)
- New version uses encrypted SQLite + client-side decryption

---

# Chunimai Dashboard

A static web dashboard that visualizes your **maimai** and **CHUNITHM** arcade play history as GitHub-style contribution heatmaps. No backend, no database server — everything runs in the browser.

![Static](https://img.shields.io/badge/GitHub%20Pages-static-brightgreen?logo=github)

## Features

- **Heatmap visualization** — daily play counts for maimai (orange) and CHUNITHM (green)
- **Year selector** — browse play history by year
- **Tooltip & tap support** — hover or tap a cell to see play count, date, and rating
- **Dark theme** — styled to match GitHub's dark UI
- **AI chat** — ask questions about your play history and get song suggestions (bring your own API key)
- **Self-hosting** — Docker image available for those who prefer it

## How It Works

```
GitHub Actions (daily, 22:00 Bangkok)
  → Playwright scrapes SEGA portal
  → Appends to public/data/play-history.json
  → Commits to git

GitHub Actions (weekly)
  → maimai-scraper Docker fetches user.json + songs.json
  → Commits to git

GitHub Actions (on push to main)
  → Deploys public/ to GitHub Pages

Browser
  → Fetches data/*.json directly (no backend)
  → AI agent calls OpenAI-compatible API with your key (BYOK)
```

## Quick Start for Friends

### 1. Fork this repository

### 2. Enable GitHub Pages

Go to **Settings → Pages → Source** and select **GitHub Actions**.

### 3. Add SEGA credentials

Go to **Settings → Secrets → Actions** and add:
- `SEGA_USERNAME` — your SEGA ID
- `SEGA_PASSWORD` — your SEGA password
- `DISCORD_WEBHOOK_URL` *(optional)* — for daily Discord notifications

### 4. Seed your data

Go to **Actions → Daily Scrape → Run workflow** — run it once to populate `play-history.json`.

### 5. Open your GitHub Pages URL

Your heatmaps will load from the committed JSON files.

### 6. (Optional) AI chat

Click **Settings** and enter your OpenAI-compatible API key. The AI can answer questions about your play history and suggest songs to improve your rating.

## Local Development

```bash
# Serve the static site
python3 -m http.server -d public 8000
# Open http://localhost:8000

# Run the scraper locally (requires SEGA credentials)
cd scraper
uv sync && uv run playwright install firefox
SEGA_USERNAME=... SEGA_PASSWORD=... python main.py
```

## Configuration

Edit `config.json` in the repository root:

```json
{
  "games": ["maimai", "chunithm"],   // which games to track
  "currency": { "symbol": "THB", "perCredit": 40 },
  "version": "CiRCLE"
}
```

## GitHub Actions

| Workflow | Schedule | What it does |
|---|---|---|
| `scrape-daily.yml` | Daily at 22:00 Bangkok | Scrapes SEGA, appends to `play-history.json` |
| `scrape-songs.yml` | Weekly (Sunday) | Updates `user.json` + `songs.json` |
| `deploy.yml` | On push to `main` | Deploys `public/` to GitHub Pages |

All three can also be triggered manually from the **Actions** tab.

## Self-Hosting with Docker

```bash
# Serve static files via nginx
docker run --rm -v $(pwd)/public:/usr/share/nginx/html -p 8080:80 nginx:alpine
```

## License

[MIT](LICENSE)
