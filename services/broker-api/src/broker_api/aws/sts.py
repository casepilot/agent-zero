import json
import os
from typing import Any

import boto3

from broker_api.policy.schemas import AccessDecision


_sts_client: Any | None = None


def get_sts_client() -> Any:
    global _sts_client
    if _sts_client is None:
        _sts_client = boto3.client("sts")
    return _sts_client


def assume_scoped_role(
    *,
    user_id: str,
    decision: AccessDecision,
    session_policy: dict[str, Any],
    role_session_name: str | None = None,
) -> dict[str, Any]:
    safe_user_id = "".join(
        character if character.isalnum() or character in ("-", "_") else "-"
        for character in user_id
    )[:48]
    session_name = role_session_name or f"agent-zero-{safe_user_id}"
    response = get_sts_client().assume_role(
        RoleArn=os.environ["BROKER_CREDENTIALS_ROLE_ARN"],
        RoleSessionName=session_name,
        DurationSeconds=decision.duration_seconds,
        Policy=json.dumps(session_policy),
    )
    credentials = response["Credentials"]
    result = {
        "access_key_id": credentials["AccessKeyId"],
        "secret_access_key": credentials["SecretAccessKey"],
        "session_token": credentials["SessionToken"],
        "expiration": credentials["Expiration"].isoformat(),
    }
    assumed_role_user = response.get("AssumedRoleUser")
    if assumed_role_user:
        result["assumed_role_arn"] = assumed_role_user.get("Arn")
        result["assumed_role_id"] = assumed_role_user.get("AssumedRoleId")
    return result
