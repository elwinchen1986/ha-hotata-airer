"""Constants for Hotata Airer integration."""

POLL_INTERVAL = 5
API_BASE = "https://saas.keyoo.com/app-api/v2.0"
API_REFRESH_TOKEN = f"{API_BASE}/login/spLogin/refreshToken"
API_DEVICE_LIST = f"{API_BASE}/sp/device/getSpDeviceList"
API_PROPERTY_GET = f"{API_BASE}/device/property/get"
API_PROPERTY_SET = f"{API_BASE}/device/property/set2"
API_INVOKE2 = f"{API_BASE}/device/service/invoke2"
API_ONLINE_STATUS = f"{API_BASE}/device/synOnlineStatus"

# App fixed parameters (from APK/HAR analysis)
APP_KEY = "miniapp-hotata-prod"
APP_SECRET = "B322B40A-DBD2-26A2-F935-6E760917CB73"
APP_VERSION = "miniapp_4.4.6.1"
IMEI = "Windows Unknown x64_w4.1.10.53_s3.16.1"
PHONE_MODEL = "microsoft"
SYS_VERSION = "Windows Unknown x64"

DEFAULT_NAME = "好太太晾衣机"
DEFAULT_DESCENT_TIME = 10  # 从顶降到底的秒数，0=禁用模拟

# Config entry keys
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN = "access_token"
CONF_USER_ID = "userId"
CONF_IOT_ID = "iotId"
CONF_NAME = "name"
CONF_DESCENT_TIME = "descent_time"

DOMAIN = "hotata_airer"
