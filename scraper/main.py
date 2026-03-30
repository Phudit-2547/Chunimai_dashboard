"""
Daily scraper entry point.
Reads play-history.json → scrapes SEGA → calculates deltas → appends → writes.
Discord notifications for daily/weekly/monthly reports.
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from scraper import scrape
from discord import send_daily, send_weekly, send_monthly

# Load .env from repo root
_repo_root = Path(__file__).parent.parent
load_dotenv(_repo_root / ".env")

# Paths relative to repo root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_PATH = os.path.join(REPO_ROOT, "public", "data", "play-history.json")
CONFIG_PATH = os.path.join(REPO_ROOT, "config.json")


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_history():
    if not os.path.exists(HISTORY_PATH):
        return []
    with open(HISTORY_PATH) as f:
        return json.load(f)


def save_history(history):
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
        f.write("\n")


def get_previous_entry(history, exclude_date=None):
    """Get the immediately previous entry from history (excluding exclude_date)."""
    for entry in reversed(history):
        if exclude_date and entry.get("play_date") == exclude_date:
            continue
        return entry
    return None


def main():
    config = load_config()
    games = config.get("games", ["maimai", "chunithm"])

    # Get credentials from environment
    sid = os.environ.get("SEGA_USERNAME", "")
    password = os.environ.get("SEGA_PASSWORD", "")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    if not sid or not password:
        print("ERROR: SEGA_USERNAME and SEGA_PASSWORD must be set")
        sys.exit(1)

    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")

    print(f"Scraping for {today}...")
    print(f"Games: {games}")

    # Scrape SEGA portals
    results = scrape(games, sid, password)

    # Build new entry
    entry = {
        "play_date": today,
        "scrape_failed": False,
        "failure_reason": None,
    }

    for game in ["maimai", "chunithm"]:
        if game not in games:
            entry[f"{game}_play_count"] = 0
            entry[f"{game}_cumulative"] = 0
            entry[f"{game}_rating"] = None
            continue

        data = results.get(game, {})

        if data.get("failed"):
            reason = data.get("failure_reason", "unknown")
            print(f"WARNING: {game} scrape failed: {reason}")
            entry["scrape_failed"] = True
            entry["failure_reason"] = reason
            # Carry forward previous values (excluding today's partial entry)
            prev_entry = get_previous_entry(history, exclude_date=today)
            prev_cum = prev_entry.get(f"{game}_cumulative", 0) if prev_entry else 0
            prev_rating = prev_entry.get(f"{game}_rating") if prev_entry else None
            entry[f"{game}_play_count"] = 0
            entry[f"{game}_cumulative"] = prev_cum
            entry[f"{game}_rating"] = prev_rating
            continue

        cumulative = data.get("cumulative", 0)
        rating = data.get("rating")
        prev_entry = get_previous_entry(history, exclude_date=today)
        prev_cumulative = prev_entry.get(f"{game}_cumulative", 0) if prev_entry else 0

        # Calculate daily delta
        if prev_cumulative == 0:
            new_plays = 0  # First run, don't count all historical plays
        else:
            new_plays = max(0, cumulative - prev_cumulative)

        entry[f"{game}_play_count"] = new_plays
        entry[f"{game}_cumulative"] = cumulative
        entry[f"{game}_rating"] = rating

        print(f"{game}: {new_plays} new plays (cumulative: {cumulative}, rating: {rating})")

        # Send daily Discord notification
        if webhook_url and new_plays > 0:
            send_daily(webhook_url, game, new_plays)

    # Upsert: replace existing entry for today, otherwise prepend
    existing_idx = next((i for i, e in enumerate(history) if e.get("play_date") == today), None)
    if existing_idx is not None:
        history[existing_idx] = entry
        print(f"Updated existing entry for {today}")
    else:
        history.insert(0, entry)
    save_history(history)
    print(f"Saved to {HISTORY_PATH}")

    # Weekly report (Monday)
    if datetime.now().weekday() == 0 and webhook_url:
        print("Sending weekly report...")
        send_weekly(webhook_url, history)

    # Monthly report (1st of month)
    if datetime.now().day == 1 and webhook_url:
        print("Sending monthly report...")
        send_monthly(webhook_url, history)


if __name__ == "__main__":
    main()
