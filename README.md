# Chunimai Dashboard

A lightweight web dashboard that visualizes your **maimai** and **CHUNITHM** arcade play history as GitHub-style contribution heatmaps. Built with [Bun](https://bun.sh) + [Elysia](https://elysiajs.com) and [Cal-Heatmap](https://cal-heatmap.com).

![Dashboard Preview](https://img.shields.io/badge/bun-%E2%89%A51.0-f472b6?logo=bun&logoColor=white) ![Elysia](https://img.shields.io/badge/elysia-1.2-blue) ![Docker](https://img.shields.io/badge/docker-ready-2496ED?logo=docker&logoColor=white)

## Features

- **Heatmap visualization** — daily play counts for maimai (orange) and CHUNITHM (green)
- **Year selector** — browse play history by year
- **Tooltip & tap support** — hover or tap a cell to see play count, date, and rating
- **Dark theme** — styled to match GitHub's dark UI
- **Docker & CI/CD** — multi-arch Docker image auto-published to GHCR on push

## Prerequisites

- [Bun](https://bun.sh) ≥ 1.0 (or Docker)
- A PostgreSQL database with a `play_data` table (provided by a separate scraper service)

### Expected `play_data` schema

| Column                | Type    |
| --------------------- | ------- |
| `play_date`           | `date`  |
| `maimai_play_count`   | `int`   |
| `chunithm_play_count` | `int`   |
| `maimai_rating`       | `numeric` |
| `chunithm_rating`     | `numeric` |

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/phudit-2547/chunimai-dashboard.git
cd chunimai-dashboard
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your PostgreSQL password:

```dotenv
POSTGRES_PASSWORD=your_password_here
DATABASE_URL=postgresql://chunimai:your_password_here@db:5432/chunimai
```

### 3. Run locally (with Bun)

```bash
bun install
bun run dev        # hot-reload mode
# or
bun run start      # production mode
```

The dashboard will be available at **http://localhost:3000**.

### 4. Run with Docker Compose

> **Note:** The dashboard expects to join an existing Docker network (`chunimai_spend_tracker_default`) where the PostgreSQL container is running.

```bash
docker compose up -d
```

## API Endpoints

| Method | Path              | Description                              |
| ------ | ----------------- | ---------------------------------------- |
| `GET`  | `/`               | Serves the dashboard UI                  |
| `GET`  | `/api/years`      | Returns available years in the database  |
| `GET`  | `/api/play-data`  | Returns play data (optional `?year=` and `&spillover=1` query params) |

## Project Structure

```
├── public/
│   └── index.html          # Single-page dashboard (HTML + JS + CSS)
├── src/
│   └── index.ts            # Elysia server with API routes
├── .github/
│   └── workflows/
│       └── docker-publish.yml  # CI: build & push multi-arch image to GHCR
├── Dockerfile              # Multi-stage Bun build
├── docker-compose.yml
├── .env.example
└── package.json
```

## CI/CD

Pushing to `main` triggers a GitHub Actions workflow that builds a multi-arch (`linux/amd64`, `linux/arm64`) Docker image and publishes it to:

```
ghcr.io/phudit-2547/chunimai-dashboard:latest
```

## License

This project is licensed under the [MIT License](LICENSE).
