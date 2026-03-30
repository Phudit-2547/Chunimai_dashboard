"""
Constants for SEGA portal scraping.
Adapted from Chunimai-tracker play_counter/constants.py and scraper.py.
"""

# SEGA Aime gateway login URLs
CHUNITHM_LOGIN_URL = (
    "https://lng-tgk-aime-gw.am-all.net/common_auth/login"
    "?site_id=chuniex"
    "&redirect_url=https://chunithm-net-eng.com/mobile/home/"
    "&back_url=https://chunithm.sega.com/"
)

MAIMAI_LOGIN_URL = (
    "https://lng-tgk-aime-gw.am-all.net/common_auth/login"
    "?site_id=maimaidxex"
    "&redirect_url=https://maimaidx-eng.com/maimai-mobile/home/"
    "&back_url=https://maimai.sega.com/"
)

# Home page URLs (to check if logged in)
CHUNITHM_HOME_URL = "https://chunithm-net-eng.com/mobile/home/"
MAIMAI_HOME_URL = "https://maimaidx-eng.com/maimai-mobile/home/"

# Player data page URLs
CHUNITHM_PLAYER_DATA_URL = "https://chunithm-net-eng.com/mobile/home/playerData"
MAIMAI_PLAYER_DATA_URL = "https://maimaidx-eng.com/maimai-mobile/playerData/"

# CSS selectors
MAIMAI_RATING_SELECTOR = ".rating_block"
CHUNITHM_RATING_SELECTOR = ".player_rating_num_block"
CHUNITHM_PLAY_COUNT_SELECTOR = "div.user_data_play_count div.user_data_text"

# Regex for maimai play count
MAIMAI_PLAY_COUNT_REGEX = r"maimaiDX total play count[：:](\d+)"

# Discord notification config
NOTIFICATION_CONFIG = {
    "maimai": {
        "username": "毎日みのり",
        "message": "**maimai**: You played **{new_plays}** credit(s) today!",
    },
    "chunithm": {
        "username": "毎日みのり",
        "message": "**CHUNITHM**: You played **{new_plays}** credit(s) today!",
    },
}
