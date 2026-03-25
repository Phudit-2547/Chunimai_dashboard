"""
Tests for suggest_songs function.
"""
import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools.suggest_songs import (
    suggest_songs,
    get_rank_info,
    get_next_rank,
    calculate_song_rating,
    get_all_songs,
)

# Import from rating directly for functions not re-exported
from rating import get_rank_factor, PLAYER_DATA_FILE


# Load real player data for testing
def get_sample_player_data():
    """Load sample player data from file."""
    with open(PLAYER_DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def test_get_rank_info():
    """Test rank info extraction."""
    assert get_rank_info(1005000) == ("SSS+", 100.5)
    assert get_rank_info(1000000) == ("SSS", 100.0)
    assert get_rank_info(995000) == ("SS+", 99.5)
    assert get_rank_info(990000) == ("SS", 99.0)
    assert get_rank_info(980000) == ("S+", 98.0)
    assert get_rank_info(800000) == ("A", 80.0)
    print("✓ test_get_rank_info passed")


def test_get_rank_factor():
    """Test rank factor retrieval."""
    assert get_rank_factor(1005000) == 0.224
    assert get_rank_factor(1000000) == 0.216
    assert get_rank_factor(995000) == 0.211
    assert get_rank_factor(990000) == 0.208
    print("✓ test_get_rank_factor passed")


def test_get_next_rank():
    """Test next rank calculation."""
    assert get_next_rank(1005000) == ("SSS+", 1005000)  # Already max
    assert get_next_rank(1000000) == ("SSS+", 1005000)
    assert get_next_rank(995000) == ("SSS", 1000000)
    assert get_next_rank(990000) == ("SS+", 995000)
    assert get_next_rank(980000) == ("SS", 990000)
    print("✓ test_get_next_rank passed")


def test_calculate_song_rating():
    """Test song rating calculation."""
    # SSS+ cap test
    rating = calculate_song_rating(14.3, 1005000, 0)
    expected = int(14.3 * 100.5 * 0.224)  # 321
    assert rating == expected, f"Expected {expected}, got {rating}"
    
    # Normal calculation
    rating = calculate_song_rating(13.0, 1000000, 0)
    expected = int(13.0 * 100.0 * 0.216)  # 280
    assert rating == expected, f"Expected {expected}, got {rating}"
    
    print("✓ test_calculate_song_rating passed")


def test_suggest_songs_best_effort_mode():
    """Test suggest_songs in best_effort mode.
    
    Note: This test requires the API to be available.
    Run with: uv run python tests/test_suggest_songs.py
    """
    try:
        all_songs = get_all_songs()
        player_data = get_sample_player_data()
    except Exception as e:
        print(f"⚠ Skipping test - API not available: {e}")
        return
    
    result = suggest_songs(
        player_data=player_data,
        all_songs=all_songs,
        mode="best_effort",
    )
    
    assert result["mode"] == "best_effort"
    assert "improvements" in result
    assert "new_songs" in result
    assert result["current_rating"] > 0
    
    # Print FULL debug output
    print(f"\n{'='*80}")
    print("=== BEST EFFORT MODE - FULL DEBUG OUTPUT ===")
    print(f"{'='*80}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"{'='*80}")
    
    print("✓ test_suggest_songs_best_effort_mode passed")


def test_suggest_songs_target_mode():
    """Test suggest_songs in target mode.
    
    Note: This test requires the API to be available.
    """
    try:
        all_songs = get_all_songs()
        player_data = get_sample_player_data()
    except Exception as e:
        print(f"⚠ Skipping test - API not available: {e}")
        return
    
    result = suggest_songs(
        player_data=player_data,
        all_songs=all_songs,
        target_rating=16000,
        mode="target",
    )
    
    assert result["mode"] == "target"
    assert result["target_rating"] == 16000
    assert result["rating_needed"] == result["target_rating"] - result["current_rating"]
    assert "songs" in result
    assert result["projected_rating"] > 0  # Just check it calculates something
    
    # Print FULL debug output
    print(f"\n{'='*80}")
    print("=== TARGET MODE (16000) - FULL DEBUG OUTPUT ===")
    print(f"{'='*80}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"{'='*80}")
    
    print("✓ test_suggest_songs_target_mode passed")


def test_new_songs_from_latest_versions():
    """Test that new_songs only includes latest versions.
    
    Note: This test requires the API to be available.
    """
    try:
        all_songs = get_all_songs()
        player_data = get_sample_player_data()
    except Exception as e:
        print(f"⚠ Skipping test - API not available: {e}")
        return
    
    result = suggest_songs(
        player_data=player_data,
        all_songs=all_songs,
        mode="best_effort",
    )
    
    # Check that new songs are from CiRCLE or PRiSM+
    for song in result.get("new_songs", []):
        assert song.get("version") in ["CiRCLE", "PRiSM+"], f"Invalid version: {song.get('version')}"
    
    print("✓ test_new_songs_from_latest_versions passed")


def test_improvements_sorted_by_gain():
    """Test that improvements are sorted by easiest first (lowest gain).
    
    Note: This test requires the API to be available.
    """
    try:
        all_songs = get_all_songs()
        player_data = get_sample_player_data()
    except Exception as e:
        print(f"⚠ Skipping test - API not available: {e}")
        return
    
    result = suggest_songs(
        player_data=player_data,
        all_songs=all_songs,
        mode="best_effort",
    )
    
    improvements = result.get("improvements", [])
    if len(improvements) > 1:
        # Check ascending order
        gains = [i["rating_gain"] for i in improvements]
        assert gains == sorted(gains), f"Not sorted: {gains}"
    
    print("✓ test_improvements_sorted_by_gain passed")


def test_new_songs_structure():
    """Test that new_songs has all required fields.
    
    Note: This test requires the API to be available.
    """
    try:
        all_songs = get_all_songs()
        player_data = get_sample_player_data()
    except Exception as e:
        print(f"⚠ Skipping test - API not available: {e}")
        return
    
    result = suggest_songs(
        player_data=player_data,
        all_songs=all_songs,
        mode="best_effort",
    )
    
    required_fields = [
        "title", "artist", "chartType", "difficulty", "level",
        "constant", "version", "target_rank", "target_score",
        "potential_rating", "rating_gain", "type", "image", "cover_url"
    ]
    
    for song in result.get("new_songs", []):
        for field in required_fields:
            assert field in song, f"Missing field: {field}"
        # Verify cover_url format
        if song.get("cover_url"):
            assert song["cover_url"].startswith("https://maimai.wonderhoy.me/api/imageProxy?img=")
    
    print("✓ test_new_songs_structure passed")


def test_improvements_structure():
    """Test that improvements has all required fields.
    
    Note: This test requires the API to be available.
    """
    try:
        all_songs = get_all_songs()
        player_data = get_sample_player_data()
    except Exception as e:
        print(f"⚠ Skipping test - API not available: {e}")
        return
    
    result = suggest_songs(
        player_data=player_data,
        all_songs=all_songs,
        mode="best_effort",
    )
    
    required_fields = [
        "title", "artist", "chartType", "difficulty", "level",
        "constant", "current_score", "current_rank", "target_rank",
        "target_score", "potential_rating", "rating_gain", "type", "image", "cover_url"
    ]
    
    for song in result.get("improvements", []):
        for field in required_fields:
            assert field in song, f"Missing field: {field}"
        # Verify cover_url format
        if song.get("cover_url"):
            assert song["cover_url"].startswith("https://maimai.wonderhoy.me/api/imageProxy?img=")
    
    print("✓ test_improvements_structure passed")


if __name__ == "__main__":
    print("Running tests...\n")
    
    test_get_rank_info()
    test_get_rank_factor()
    test_get_next_rank()
    test_calculate_song_rating()
    test_suggest_songs_best_effort_mode()
    test_suggest_songs_target_mode()
    test_new_songs_from_latest_versions()
    test_improvements_sorted_by_gain()
    test_new_songs_structure()
    test_improvements_structure()
    
    print("\n✓ All tests passed!")
