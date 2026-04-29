import json
from typing import Any
from urllib.parse import urlencode, quote
from urllib.request import urlopen


FEDERATION_ENDPOINT = "https://signin.aws.amazon.com/federation"
CONSOLE_DESTINATION = "https://console.aws.amazon.com/"


def build_console_login_url(credentials: dict[str, Any]) -> str:
    session = {
        "sessionId": credentials["access_key_id"],
        "sessionKey": credentials["secret_access_key"],
        "sessionToken": credentials["session_token"],
    }
    token_query = urlencode(
        {"Action": "getSigninToken", "Session": json.dumps(session)},
        quote_via=quote,
    )
    with urlopen(f"{FEDERATION_ENDPOINT}?{token_query}", timeout=10) as response:
        signin_token = json.loads(response.read().decode("utf-8"))["SigninToken"]

    return (
        f"{FEDERATION_ENDPOINT}?"
        f"{urlencode({'Action': 'login', 'Issuer': 'agent-zero', 'Destination': CONSOLE_DESTINATION, 'SigninToken': signin_token}, quote_via=quote)}"
    )
