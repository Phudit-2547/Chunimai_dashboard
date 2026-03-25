import glob
import json
import os
import requests
from typing import Optional

# Base URL for cover images
COVER_BASE_URL = "https://maimai.wonderhoy.me/api/imageProxy?img="

# Player data paths (relative to project root)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _find_json_file(pattern: str) -> str:
    """Find the most recent JSON file matching the pattern."""
    files = glob.glob(os.path.join(PROJECT_ROOT, pattern))
    if not files:
        raise FileNotFoundError(f"No file found matching pattern: {pattern}")
    return max(files, key=os.path.getmtime)


PLAYER_DATA_FILE = _find_json_file("*T*.json")
FULL_PLAYER_DATA_FILE = _find_json_file("full-*.json")

def get_cover_url(image_filename: str) -> str:
    """Get full cover image URL from filename."""
    if not image_filename:
        return ""
    return f"{COVER_BASE_URL}{image_filename}"

API_BASE_URL = "https://maimai.wonderhoy.me/api"

# Rank factor table: (min_score, factor, name)
RANK_FACTORS = [
    (1005000, 0.224, "SSS+"),  # 100.5%+
    (1000000, 0.216, "SSS"),   # 100%
    (995000, 0.211, "SS+"),    # 99.5%
    (990000, 0.208, "SS"),     # 99%
    (980000, 0.203, "S+"),    # 98%
    (970000, 0.200, "S"),     # 97%
    (940000, 0.168, "AAA"),   # 94%
    (900000, 0.152, "AA"),    # 90%
    (800000, 0.136, "A"),     # 80%
]


def get_rank_info(score: int) -> tuple[str, float]:
    """Get rank name and percentage from score. Faster: multiply instead of divide."""
    rank_name = "Below A"
    rank_pct = score / 10000  # e.g., 100.7471%
    for min_score, factor, name in RANK_FACTORS:
        if score >= min_score:
            rank_name = name
            break
    return rank_name, rank_pct


def get_rank_factor(score: int) -> float:
    """Get factor based on score. Faster: multiply instead of divide."""
    for min_score, factor, _ in RANK_FACTORS:
        if score >= min_score:
            return factor
    return 0.0  # Below A


def get_next_rank(score: int) -> tuple[str, int]:
    """
    Get the next rank up from current score.
    Returns (rank_name, min_score_needed)
    e.g., 981696 (S+) → ("SS", 990000)
    e.g., 994854 (SS) → ("SS+", 995000)
    """
    # Find current rank index (list is ordered high to low: SSS+, SSS, SS+, SS, S+, S, AAA, AA, A)
    current_idx = -1
    for i, (min_score, _, _) in enumerate(RANK_FACTORS):
        if score >= min_score:
            current_idx = i
            break
    
    # Get next rank (lower index = higher rank since list is ordered high to low)
    if current_idx > 0:
        next_min_score, _, next_name = RANK_FACTORS[current_idx - 1]
        return next_name, next_min_score
    
    return "SSS+", 1005000  # Already at max


def calculate_average_rating(player_data: dict, all_songs: list) -> float:
    """
    Calculate average rating per song from player's best (35) + current (15).
    This helps determine realistic rank the player can achieve.
    """
    # Build constants lookup
    constants = {}
    for song in all_songs:
        for diff in ["basic", "advanced", "expert", "master", "remaster"]:
            if diff in song:
                key = (song["title"], song["chartType"], diff)
                constants[key] = song[diff].get("constant", 0)
    
    all_ratings = []
    for song in list(player_data.get("best", [])) + list(player_data.get("current", [])):
        key = (song.get("title"), song.get("chartType"), song.get("difficulty"))
        constant = constants.get(key, 0)
        if constant > 0:
            rating = calculate_song_rating(
                constant, 
                song.get("score", 0), 
                song.get("dxScore", 0)
            )
            all_ratings.append(rating)
    
    if not all_ratings:
        return 0
    return sum(all_ratings) / len(all_ratings)


def calculate_song_rating(constant: float, score: int, _dx_score: int = 0) -> float:
    """
    Calculate rating for a single song.
    rating = int(constant × achievement × factor)
    
    Achievement is capped at 100.5% for scores >= 1005000 (SSS+).
    
    Args:
        constant: Song difficulty constant (e.g., 13.4)
        score: Base score (e.g., 1007471)
        dx_score: DX score bonus (reserved for future use)
    
    Returns:
        Rating value
    """
    # Cap achievement at 100.5% for SSS+ scores
    if score >= 1005000:
        achievement = 100.5
        factor = 0.224
    else:
        achievement = score / 10000
        factor = get_rank_factor(score)
    
    # Use int() (truncation) to match API
    rating = int(constant * achievement * factor)
    
    return rating


def load_data_from_json(json_path: str) -> dict:
    """Load player data from JSON file."""
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


# Docker command to scrape player data
SCRAPER_DOCKER_COMMAND = """docker run --rm \
  -v ./outputs:/app/outputs \
  -e USERNAME=YOUR_SEGA_ID \
  -e PASSWORD=YOUR_SEGA_PASSWORD \
  -e VERSION=CiRCLE \
  -e TZ=Asia/Bangkok \
  -e LANG=th_TH.UTF-8 \
  ghcr.io/leomotors/maimai-scraper:v1"""


def get_player_data():
    """
    Load player data or return error with instructions.
    
    Returns:
        dict: Player data if exists
        dict: Error with instructions if not
    """
    if not os.path.exists(PLAYER_DATA_FILE):
        return {
            "error": "Player data not found",
            "instructions": [
                "Run the scraper to get your player data:",
                SCRAPER_DOCKER_COMMAND,
                "",
                "Then upload the resulting JSON file to the dashboard.",
            ],
            "docker_command": SCRAPER_DOCKER_COMMAND,
        }
    return load_data_from_json(PLAYER_DATA_FILE)


def get_full_player_data():
    """
    Load full player data (all history) or return error with instructions.
    
    Returns:
        dict: Full player data if exists
        dict: Error with instructions if not
    """
    if not os.path.exists(FULL_PLAYER_DATA_FILE):
        return {
            "error": "Full player data not found",
            "instructions": [
                "Run the scraper with full history enabled to get your data:",
                SCRAPER_DOCKER_COMMAND,
                "",
                "Then upload the resulting JSON file to the dashboard.",
            ],
            "docker_command": SCRAPER_DOCKER_COMMAND,
        }
    return load_data_from_json(FULL_PLAYER_DATA_FILE)


def get_all_songs(version: str = "CiRCLE", local_path: str = None) -> list:
    """Get all songs from maimai API or local file."""
    if local_path and os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    try:
        response = requests.get(f"{API_BASE_URL}/musicData", params={"version": version}, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Try local fallback 
        local_files = [
            os.path.join(os.path.dirname(__file__), "songs.json"),
        ]
        for local_file in local_files:
            if os.path.exists(local_file):
                with open(local_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        raise e


def calc_rating(data: dict, version: str = "CiRCLE") -> dict:
    """
    Calculate rating from play data.
    
    Args:
        data: Dictionary with profile, best, current, scraperVersion
        version: Game version (default: "CiRCLE")
    
    Returns:
        Dictionary with rating breakdown
    """
    payload = {
        "data": data,
        "version": version
    }
    
    response = requests.post(f"{API_BASE_URL}/calcRating", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def calculate_total_rating(songs: list, constants: dict) -> int:
    """Calculate total rating from a list of songs using local formula."""
    total = 0
    for song in songs:
        title = song.get("title", "")
        chart_type = song.get("chartType", "")
        difficulty = song.get("difficulty", "")
        score = song.get("score", 0)
        dx_score = song.get("dxScore", 0)
        
        # Get constant from music data
        key = (title, chart_type, difficulty)
        constant = constants.get(key, 0)
        
        if constant > 0:
            rating = calculate_song_rating(constant, score, dx_score)
            total += rating
    
    return total


def suggest_songs(
    player_data: dict,
    all_songs: list,
    target_rating: Optional[int] = None,
    mode: str = "auto",  # "auto" = best_effort if target_rating is None, "target" = target mode, "best_effort" = max suggestions
    max_suggestions: int = 5,
    difficulty_filter: Optional[list[str]] = None,
    version: str = "CiRCLE"
) -> dict:
    """
    Suggest songs to improve player rating.
    
    Args:
        player_data: Player data with profile, best, current
        all_songs: All songs from maimai API (musicData)
        target_rating: Target rating to reach (None = maximize)
        max_suggestions: Maximum number of songs to suggest
        difficulty_filter: List of difficulties to include
        version: Game version
    
    Returns:
        Dictionary with suggestions and calculations
    """
    # Build constants lookup
    constants = {}
    for song in all_songs:
        for diff in ["basic", "advanced", "expert", "master", "remaster"]:
            if diff in song:
                key = (song["title"], song["chartType"], diff)
                constants[key] = song[diff].get("constant", 0)
    
    # Get current rating using API
    current_result = calc_rating(player_data, version)
    current_rating = current_result["rating"]["total"]
    
    # Calculate player's current max constant (hardest song they play)
    max_player_constant = 0
    min_player_constant = 999
    for s in player_data.get("best", []) + player_data.get("current", []):
        key = (s.get("title"), s.get("chartType"), s.get("difficulty"))
        c = constants.get(key, 0)
        if c > 0:
            if c > max_player_constant:
                max_player_constant = c
            if c < min_player_constant:
                min_player_constant = c
    
    # Filter new songs to be within player's current difficulty range
    min_constant = min_player_constant  # Same or easier
    max_constant = min(max_player_constant, 15.0)  # Up to player's max, capped at 15.0
    
    # Get existing songs (title + chartType + difficulty)
    existing = set()
    for song in player_data.get("best", []):
        existing.add((song.get("title"), song.get("chartType"), song.get("difficulty")))
    for song in player_data.get("current", []):
        existing.add((song.get("title"), song.get("chartType"), song.get("difficulty")))
    
    # Get songs player can improve (score < SSS+)
    improvable = {}
    for song in list(player_data.get("best", [])) + list(player_data.get("current", [])):
        key = (song.get("title"), song.get("chartType"), song.get("difficulty"))
        score = song.get("score", 0)
        if score < 1005000:  # Not SSS+ yet
            improvable[key] = score
    
    # Candidate difficulties
    difficulties = difficulty_filter or ["master", "expert", "advanced"]
    
    # Latest versions (new songs to suggest)
    latest_versions = ["CiRCLE", "PRiSM+"]
    
    # Find new songs (from latest versions, not in best/current)
    candidates = []
    new_song_count = 0  # Track how many new songs added
    
    # Get current section song ratings sorted (new songs replace from current section)
    rating_songs = []
    for s in player_data.get("current", []):
        key = (s.get("title"), s.get("chartType"), s.get("difficulty"))
        const = constants.get(key, 0)
        if const > 0:
            rating = calculate_song_rating(const, s.get("score", 0))
            rating_songs.append(rating)
    rating_songs.sort()
    
    for song in all_songs:
        # Only include songs from latest versions
        version = song.get("releasedVersion", "")
        if version not in latest_versions:
            continue
            
        for diff in difficulties:
            if diff not in song:
                continue
            
            key = (song["title"], song["chartType"], diff)
            if key in existing:
                continue  # Already played
            
            constant = song[diff].get("constant", 0)
            if constant <= 0:
                continue
            
            # Filter by constant to match player's current difficulty range
            if constant < min_constant or constant > max_constant:
                continue
            
            # Calculate potential rating at SSS+ (max)
            max_rating = calculate_song_rating(constant, 1005000, 0)
            
            # Find which song this would replace (each new song replaces next lowest from current section)
            replace_idx = new_song_count if new_song_count < len(rating_songs) else len(rating_songs) - 1
            rating_replaced = rating_songs[replace_idx] if replace_idx < len(rating_songs) else 0
            
            # Find minimum rating needed to beat the song being replaced
            min_rating_needed = rating_replaced + 1
            
            # Find minimum score/rank needed to achieve min_rating_needed
            # Go from lowest rank to highest to find MINIMUM needed
            min_score_needed = 0
            min_rank_needed = ""
            for ms, factor, rank_name in reversed(RANK_FACTORS):
                potential = int(constant * (ms / 10000) * factor)
                if potential >= min_rating_needed:
                    min_score_needed = ms
                    min_rank_needed = rank_name
                    break
            
            # If can't reach minimum with any rank, use max
            if min_score_needed == 0:
                min_score_needed = 1005000
                min_rank_needed = "SSS+"
            
            # Calculate rating at target rank
            target_rank_rating = calculate_song_rating(constant, min_score_needed, 0)
            
            candidates.append({
                "title": song["title"],
                "artist": song.get("artist", ""),
                "chartType": song["chartType"],
                "difficulty": diff,
                "level": song[diff].get("level", ""),
                "constant": constant,
                "version": version,
                "image": song.get("image", ""),
                "cover_url": get_cover_url(song.get("image", "")),
                "max_rating": max_rating,
                "min_rating_needed": min_rating_needed,
                "target_rank": min_rank_needed,
                "target_score": min_score_needed,
                "potential_rating": target_rank_rating,
                "rating_gain": target_rank_rating - rating_replaced,
                "replaces": rating_replaced,
                "type": "new"
            })
            new_song_count += 1
    
    # Find improvement candidates (already played but can improve score)
    improvements = []
    for song in all_songs:
        for diff in difficulties:
            if diff not in song:
                continue
            
            key = (song["title"], song["chartType"], diff)
            if key not in improvable:
                continue
            
            constant = song[diff].get("constant", 0)
            if constant <= 0:
                continue
            
            current_score = improvable[key]
            current_rank, current_pct = get_rank_info(current_score)
            current_rating_song = calculate_song_rating(constant, current_score)
            
            # Get next rank up (smallest improvement)
            target_rank, target_score = get_next_rank(current_score)
            potential_rating = calculate_song_rating(constant, target_score, int(constant * 100))
            rating_gain = potential_rating - current_rating_song
            
            if rating_gain > 0:
                improvements.append({
                    "title": song["title"],
                    "artist": song.get("artist", ""),
                    "chartType": song["chartType"],
                    "difficulty": diff,
                    "level": song[diff].get("level", ""),
                    "constant": constant,
                    "image": song.get("image", ""),
                    "cover_url": get_cover_url(song.get("image", "")),
                    "current_score": current_score,
                    "current_rank": current_rank,
                    "current_pct": current_pct,
                    "target_rank": target_rank,
                    "target_score": target_score,
                    "potential_rating": potential_rating,
                    "rating_gain": rating_gain,
                    "type": "improve"
                })
    
    # Sort by potential rating (new songs) or rating gain (improvements)
    candidates.sort(key=lambda x: x["potential_rating"], reverse=True)
    improvements.sort(key=lambda x: x["rating_gain"], reverse=True)
    
    # Determine mode: target or best_effort
    is_target_mode = mode == "target" or (mode == "auto" and target_rating is not None)
    
    suggestions = {
        "mode": "target" if is_target_mode else "best_effort",
        "current_rating": current_rating,
        "target_rating": target_rating,
    }
    
    if is_target_mode:
        # Target mode: find the EASIEST path (lowest constant songs) to reach target rating
        # Use best + current (50 songs) as the pool that new songs replace
        rating_needed = target_rating - current_rating
        
        # Get best + current ratings (these are the songs that count toward rating)
        rating_songs = []
        for s in player_data.get("best", []) + player_data.get("current", []):
            key = (s.get("title"), s.get("chartType"), s.get("difficulty"))
            const = constants.get(key, 0)
            if const > 0:
                rating = calculate_song_rating(const, s.get("score", 0))
                rating_songs.append(rating)
        rating_songs.sort()  # Lowest first (these can be replaced by new songs)
        
        # Build all song options sorted by CONSTANT (lowest = easiest first)
        all_song_options = []
        
        # Add improvements (already played songs) - sorted by constant (lowest first)
        for s in improvements:
            constant = s.get("constant", 0)
            if constant <= 0:
                continue
            max_rating = calculate_song_rating(constant, 1005000, 0)
            current_rating_song = s.get("potential_rating", 0) - s.get("rating_gain", 0)
            all_song_options.append({
                "title": s["title"],
                "artist": s.get("artist", ""),
                "level": s.get("level", ""),
                "image": s.get("image", ""),
                "constant": constant,
                "difficulty": s.get("difficulty", ""),
                "chartType": s.get("chartType", ""),
                "current_rating": current_rating_song,
                "max_rating": max_rating,
                "type": "improve"
            })
        
        # Add new songs (from latest versions)
        for s in candidates:
            constant = s.get("constant", 0)
            if constant <= 0:
                continue
            max_rating = calculate_song_rating(constant, 1005000, 0)
            # For new songs, they replace lowest rated songs in current section
            idx = len([x for x in all_song_options if x["type"] == "new"]) % len(rating_songs) if rating_songs else 0
            replace_rating = rating_songs[idx] if idx < len(rating_songs) else 0
            all_song_options.append({
                "title": s.get("title", ""),
                "artist": s.get("artist", ""),
                "level": s.get("level", ""),
                "image": s.get("image", ""),
                "version": s.get("version", ""),
                "constant": constant,
                "difficulty": s.get("difficulty", ""),
                "chartType": s.get("chartType", ""),
                "current_rating": replace_rating,
                "max_rating": max_rating,
                "type": "new"
            })
        
        # Calculate: target / 50 songs = average gain per song needed
        songs_to_replace = 50
        gain_per_song_needed = rating_needed / songs_to_replace
        
        # Use the AVERAGE current rating for filter (not min)
        avg_current = sum(rating_songs) / len(rating_songs) if rating_songs else 0
        
        # Filter: songs that can give at least the needed gain when replacing avg song
        min_gain_needed = max(10, int(gain_per_song_needed))
        all_song_options = [s for s in all_song_options if s["max_rating"] - avg_current >= min_gain_needed]
        
        # Sort by CONSTANT (lowest first), then by gain
        all_song_options.sort(key=lambda x: (x["constant"], -(x["max_rating"] - x["current_rating"])))
        
        # Calculate exact rating needed per song to reach target
        selected = []
        remaining = rating_needed
        
        for song_opt in all_song_options:
            if remaining <= 0:
                break
            
            current_r = song_opt["current_rating"]
            max_r = song_opt["max_rating"]
            
            potential_gain = max_r - current_r
            
            if potential_gain <= 0:
                continue
            
            actual_gain = min(potential_gain, remaining)
            target_r = current_r + actual_gain
            
            # Find the MINIMUM rank/score to achieve at least target_r
            min_score = 0
            min_rank = ""
            for ms, factor, rank_name in RANK_FACTORS:  # AAA -> SSS+
                potential = int(song_opt["constant"] * (ms / 10000) * factor)
                if potential >= target_r:
                    min_score = ms
                    min_rank = rank_name
                    break
            
            if min_score == 0:
                min_score = 1005000
                min_rank = "SSS+"
            
            selected.append({
                "song": {
                    "title": song_opt["title"],
                    "artist": song_opt.get("artist", ""),
                    "level": song_opt.get("level", ""),
                    "image": song_opt.get("image", ""),
                    "cover_url": get_cover_url(song_opt.get("image", "")),
                    "version": song_opt.get("version", ""),
                    "difficulty": song_opt["difficulty"],
                    "chartType": song_opt["chartType"],
                    "constant": song_opt["constant"],
                    "target_rank": min_rank,
                    "target_score": min_score,
                    "achievement": round(min_score / 10000, 2),  # e.g., 100.50%
                    "potential_rating": target_r,
                },
                "gain": actual_gain,
                "type": song_opt["type"]
            })
            
            remaining -= actual_gain
        
        projected = current_rating + sum(s["gain"] for s in selected)
        
        suggestions["rating_needed"] = rating_needed
        suggestions["songs"] = selected
        suggestions["projected_rating"] = projected
        suggestions["message"] = f"Here's the easiest path to reach {target_rating}! (+{sum(s['gain'] for s in selected)} rating from {len(selected)} songs)"
    else:
        # Best-effort mode: show improvements first (easiest), then new songs
        # Sort improvements by gain ascending (easiest improvements first)
        improvements_sorted = sorted(improvements, key=lambda x: x["rating_gain"])
        
        suggestions["improvements"] = improvements_sorted[:max_suggestions]
        suggestions["new_songs"] = candidates[:max_suggestions]
        suggestions["message"] = f"Found {len(candidates)} new songs and {len(improvements)} improvements"
    
    return suggestions



# Example usage
if __name__ == "__main__":
    # Load player data from JSON file
    data = load_data_from_json(PLAYER_DATA_FILE)
    
    result = calc_rating(data)
    
    # Print rating breakdown in table format
    print("\n=== BEST SONGS (Top 35) ===")
    print(f"{'#':<3} {'Title':<35} {'Chart':<6} {'Diff':<8} {'Score':<10} {'DX':<6} {'Rating':<7}")
    print("-" * 85)
    
    for i, song in enumerate(result["best"], 1):
        print(f"{i:<3} {song['title'][:34]:<35} {song['chartType']:<6} {song['difficulty']:<8} {song['score']:<10} {song.get('dxScore', '-'):<6} {song.get('rating', '-'):<7}")
    
    print(f"\n{'Best Sum: ' + str(result['rating']['bestSum']):>50}")
    
    print("\n=== CURRENT SONGS ===")
    print(f"{'#':<3} {'Title':<35} {'Chart':<6} {'Diff':<8} {'Score':<10} {'DX':<6} {'Rating':<7}")
    print("-" * 85)
    
    for i, song in enumerate(result["current"], 1):
        print(f"{i:<3} {song['title'][:34]:<35} {song['chartType']:<6} {song['difficulty']:<8} {song['score']:<10} {song.get('dxScore', '-'):<6} {song.get('rating', '-'):<7}")
    
    print(f"\n{'Current Sum: ' + str(result['rating']['currentSum']):>50}")
    print(f"{'=' * 50}")
    print(f"{'TOTAL RATING: ' + str(result['rating']['total']):>50}")
