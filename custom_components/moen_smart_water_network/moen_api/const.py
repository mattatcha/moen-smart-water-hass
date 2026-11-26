"""Constants for the Moen Smart Water Network API."""

# REST API base URLs
API_BASE_URL_V1 = "https://api.prod.iot.moen.com/v1"
API_BASE_URL_V3 = "https://api.prod.iot.moen.com/v3"

# Legacy user endpoint
API_USER_URL = "https://4j1gkf0vji.execute-api.us-east-2.amazonaws.com/prod/v1/users/me"

# Lambda invoke endpoint (for app shadow)
LAMBDA_INVOKE_URL = (
    "https://exo9f857n8.execute-api.us-east-2.amazonaws.com/prod/v1/invoker"
)

# OAuth2
OAUTH_URL = (
    "https://4j1gkf0vji.execute-api.us-east-2.amazonaws.com/prod/v1/oauth2/token"
)
OAUTH_CLIENT_ID = "6qn9pep31dglq6ed4fvlq6rp5t"

# AWS IoT / Cognito
COGNITO_ENDPOINT = "cognito-identity.us-east-2.amazonaws.com"
MQTT_REGION = "us-east-2"
MQTT_ENDPOINT = "a1r2q5ic87novc-ats.iot.us-east-2.amazonaws.com"

# HTTP client
USER_AGENT = "Moen/3 CFNetwork/1408.0.4 Darwin/22.5.0"

# MQTT topic templates ({thing_name} = clientId, {duid} = device unique id)
SHADOW_GET_TOPIC = "$aws/things/{thing_name}/shadow/get"
SHADOW_GET_ACCEPTED_TOPIC = "$aws/things/{thing_name}/shadow/get/accepted"
SHADOW_UPDATE_ACCEPTED_TOPIC = "$aws/things/{thing_name}/shadow/update/accepted"
SHADOW_UPDATE_DOCUMENTS_TOPIC = "$aws/things/{thing_name}/shadow/update/documents"
ASYNC_TOPIC = "/async/{duid}"

# Device types (the "type" field of GET /v3/devices)
DEVICE_TYPE_HYD = "hyd"  # Smart Sprinkler Controller
DEVICE_TYPE_NAB = "nab"  # Smart Sump Pump Monitor

# Lambda invoker function names. All sump pump functions take the numeric clientId
# *as a string*; integer or UUID forms return errors or empty results.
FN_DEVICE_LIST = "smartwater-app-device-api-prod-list"
FN_SHADOW_GET = "smartwater-app-shadow-api-prod-get"
FN_SHADOW_UPDATE = "smartwater-app-shadow-api-prod-update"
FN_SUMP_PUMP_ENVIRONMENT = "fbgpg_usage_v1_get_device_environment_latest_prod"
FN_SUMP_PUMP_LAST_USAGE = "fbgpg_usage_v1_get_last_usage_prod"
FN_SUMP_PUMP_SESSIONS = "fbgpg_usage_v1_get_my_usage_device_history_prod"
FN_SUMP_PUMP_CAPACITY = "fbgpg_usage_v1_get_my_usage_device_history_top10_prod"
FN_LATEST_FIRMWARE = "fbgpg_device_v1_device_get_latest_firmware_prod"
FN_ALERTS_ACTIVE = "fbgpg_alerts_v2_get_alerts_active_by_user_prod"

# Sump pump shadow commands this integration is allowed to send.
SUMP_PUMP_COMMAND_STREAM_ON = "drop_on"
SUMP_PUMP_COMMAND_STREAM_OFF = "updates_off"
SUMP_PUMP_COMMANDS = frozenset(
    {SUMP_PUMP_COMMAND_STREAM_ON, SUMP_PUMP_COMMAND_STREAM_OFF}
)
