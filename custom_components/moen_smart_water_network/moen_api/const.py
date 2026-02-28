"""Constants for the Moen Smart Water Network API."""

# REST API base URLs
API_BASE_URL_V1 = "https://api.prod.iot.moen.com/v1"
API_BASE_URL_V3 = "https://api.prod.iot.moen.com/v3"

# Legacy user endpoint
API_USER_URL = (
    "https://4j1gkf0vji.execute-api.us-east-2.amazonaws.com/prod/v1/users/me"
)

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
