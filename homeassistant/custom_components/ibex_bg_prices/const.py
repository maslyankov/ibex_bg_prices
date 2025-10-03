"""Constants for the IBEX BG integration."""

DOMAIN = "ibex_bg"
DEFAULT_NAME = "IBEX BG"
DEFAULT_SCAN_INTERVAL = 300  # 5 minutes

# API Configuration
API_URL = "https://ibex.bg/Ext/IDM_Homepage/fetch_dam.php"
API_PARAMS = {"lang": "bg", "num": "73"}

# Headers to mimic browser request
API_HEADERS = {
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://ibex.bg/",
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
}

# Cookies
API_COOKIES = {
    "__wpdm_client": "fe1f4c32205edf6d6f93d2d060e8bcbd",
    "_ga": "GA1.1.1071599757.1759405313",
    "pll_language": "bg",
    "_ga_5LBFZ1MK81": "GS2.1.s1759453610$o2$g1$t1759453626$j44$l0$h0"
}
