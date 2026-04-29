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
) -> dict[str, Any]:
    safe_user_id = "".join(
        character if character.isalnum() or character in ("-", "_") else "-"
        for character in user_id
    )[:48]
    response = get_sts_client().assume_role(
        RoleArn=os.environ["BROKER_CREDENTIALS_ROLE_ARN"],
        RoleSessionName=f"agent-zero-{safe_user_id}",
        DurationSeconds=decision.duration_seconds,
        Policy=json.dumps(session_policy),
    )
    credentials = response["Credentials"]
    return {
        "access_key_id": credentials["AccessKeyId"],
        "secret_access_key": credentials["SecretAccessKey"],
        "session_token": credentials["SessionToken"],
        "expiration": credentials["Expiration"].isoformat(),
    }
