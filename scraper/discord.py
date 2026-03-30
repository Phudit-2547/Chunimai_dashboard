"""
Discord webhook notifications for play data.
Adapted from Chunimai-tracker play_counter/daily_play_notifier.py and reports/.
"""
import json
import os
from datetime import datetime, timedelta

import requests

from constants import NOTIFICATION_CONFIG

MAX_RETRIES = 3
RETRY_DELAY = 2


def _load_config():
    """Load config.json from repo root."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    with open(config_path) as f:
        return json.load(f)


def _post_webhook(webhook_url: str, content: str, username: str = "毎日みのり"):
    """Post a message to Discord webhook with retries."""
    for attempt in range(MAX_RETRIES):
        try:
            res = requests.post(
                webhook_url,
                json={"content": content, "username": username},
                timeout=10,
            )
            res.raise_for_status()
            return
        except Exception:
            if attempt < MAX_RETRIES - 1:
                import time
                time.sleep(RETRY_DELAY)


def send_daily(webhook_url: str, game: str, new_plays: int):
    """Send daily play count notification."""
    if not webhook_url or new_plays <= 0:
        return

    cfg = NOTIFICATION_CONFIG.get(game, {})
    message = cfg.get("message", f"**{game}**: You played **{new_plays}** credit(s) today!")
    message = message.format(new_plays=new_plays)
    username = cfg.get("username", "毎日みのり")
    _post_webhook(webhook_url, message, username)


def send_weekly(webhook_url: str, history: list):
    """Send weekly play report (call on Mondays)."""
    if not webhook_url:
        return

    config = _load_config()
    currency = config.get("currency", {})
    symbol = currency.get("symbol", "THB")
    per_credit = currency.get("perCredit", 40)

    # Sum last 7 days
    today = datetime.now().date()
    week_start = today - timedelta(days=7)
    week_start_str = week_start.isoformat()

    maimai_total = 0
    chunithm_total = 0
    for entry in history:
        if entry["date"] >= week_start_str:
            maimai_total += entry.get("maimai", 0)
            chunithm_total += entry.get("chunithm", 0)

    total_plays = maimai_total + chunithm_total
    total_cost = total_plays * per_credit

    lines = ["📊 **Last Week Play Report**"]
    if maimai_total > 0:
        cost = maimai_total * per_credit
        lines.append(f"🎵 **maimai**: {maimai_total} plays → **{cost} {symbol}**")
    if chunithm_total > 0:
        cost = chunithm_total * per_credit
        lines.append(f"🎶 **CHUNITHM**: {chunithm_total} plays → **{cost} {symbol}**")
    lines.append(f"💰 **Total**: {total_plays} plays → **{total_cost} {symbol}**")

    _post_webhook(webhook_url, "\n".join(lines), "毎週みのり")


def send_monthly(webhook_url: str, history: list):
    """Send monthly play report (call on 1st of month)."""
    if not webhook_url:
        return

    config = _load_config()
    currency = config.get("currency", {})
    symbol = currency.get("symbol", "THB")
    per_credit = currency.get("perCredit", 40)

    today = datetime.now().date()
    # Previous month
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    month_name = last_month_end.strftime("%B %Y")

    start_str = last_month_start.isoformat()
    end_str = last_month_end.isoformat()

    maimai_total = 0
    chunithm_total = 0
    for entry in history:
        if start_str <= entry["date"] <= end_str:
            maimai_total += entry.get("maimai", 0)
            chunithm_total += entry.get("chunithm", 0)

    total_plays = maimai_total + chunithm_total
    total_cost = total_plays * per_credit

    lines = [f"📊 **Monthly Play Report ({month_name})**"]
    if maimai_total > 0:
        cost = maimai_total * per_credit
        lines.append(f"🎵 **maimai**: {maimai_total} plays → **{cost} {symbol}**")
    if chunithm_total > 0:
        cost = chunithm_total * per_credit
        lines.append(f"🎶 **CHUNITHM**: {chunithm_total} plays → **{cost} {symbol}**")
    lines.append(f"💰 **Total**: {total_plays} plays → **{total_cost} {symbol}**")

    _post_webhook(webhook_url, "\n".join(lines), "桃井 愛莉")
