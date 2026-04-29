import json
import os
from typing import Any

import jwt
from jwt import PyJWKClient


_jwks_client: PyJWKClient | None = None


def get_jwks_client() -> PyJWKClient:
    global _jwks_client

    if _jwks_client is None:
        issuer = cognito_issuer()
        _jwks_client = PyJWKClient(f"{issuer}/.well-known/jwks.json")
    return _jwks_client


def cognito_issuer() -> str:
    return (
        f"https://cognito-idp.{os.environ['AWS_REGION']}.amazonaws.com/"
        f"{os.environ['USER_POOL_ID']}"
    )


def deny(method_arn: str, reason: str) -> dict[str, Any]:
    print(json.dumps({"message": "websocket_auth_denied", "reason": reason}))
    return policy("anonymous", "Deny", method_arn, {"reason": reason})


def policy(
    principal_id: str,
    effect: str,
    method_arn: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": method_arn,
                }
            ],
        },
        "context": {
            key: str(value)
            for key, value in context.items()
            if value is not None
        },
    }


def token_from_event(event: dict[str, Any]) -> str | None:
    query = event.get("queryStringParameters") or {}
    token = query.get("token")
    if isinstance(token, str) and token.strip():
        return token.strip()
    return None


def verify_token(token: str) -> dict[str, Any]:
    signing_key = get_jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=cognito_issuer(),
        options={"verify_aud": False},
    )

    if claims.get("token_use") != "access":
        raise ValueError("Expected a Cognito access token")
    if claims.get("client_id") != os.environ["USER_POOL_CLIENT_ID"]:
        raise ValueError("Token client_id did not match this app client")
    if not claims.get("sub"):
        raise ValueError("Token did not contain sub")
    return claims


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    method_arn = event.get("methodArn", "*")
    token = token_from_event(event)
    if token is None:
        return deny(method_arn, "missing_token")

    try:
        claims = verify_token(token)
    except Exception as error:
        return deny(method_arn, type(error).__name__)

    groups = claims.get("cognito:groups") or []
    if isinstance(groups, list):
        groups_value = ",".join(str(group) for group in groups)
    else:
        groups_value = str(groups)

    return policy(
        principal_id=claims["sub"],
        effect="Allow",
        method_arn=method_arn,
        context={
            "user_id": claims["sub"],
            "username": claims.get("username"),
            "client_id": claims.get("client_id"),
            "groups": groups_value,
        },
    )
