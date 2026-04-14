DOMAIN = "elife"

# Config entry keys
CONF_USERNAME     = "username"
CONF_PASSWORD     = "password"
CONF_DEVICE_UUID  = "device_uuid"
CONF_AC_UIDS      = "ac_uids"       # JSON array string
CONF_LIGHT_UIDS   = "light_uids"    # JSON array string
CONF_HEAT_UIDS    = "heat_uids"     # JSON array string
CONF_VENT_UID     = "vent_uid"
CONF_ELEVATOR_UID = "elevator_uid"
CONF_EV_ROOM_KEY  = "ev_room_key"
CONF_EV_USER_KEY  = "ev_user_key"

DEFAULT_SCAN_INTERVAL = 30  # seconds

# ELIFE API
BASE_URL = "https://smartelife.apt.co.kr"
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 9_2 like Mac OS X) "
    "AppleWebKit/601.1.46 (KHTML, like Gecko) Mobile/13C75 DAELIM/IOS"
)
CSRF_USER_AGENT = (
    "elife2021/1.1.4 (kr.co.daelimcorp.elife; build:5; iOS 26.1.0) "
    "Alamofire/4.9.1"
)

# HA storage
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.tokens"

# Services
SERVICE_CLEAR_TOKEN = "clear_token"
