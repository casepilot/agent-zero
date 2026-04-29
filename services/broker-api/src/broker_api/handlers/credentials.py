import json
import os
from typing import Any

import boto3


_openai_key: str | None = None
_secretsmanager_client: Any | None = None


def get_secretsmanager_client() -> Any:
    global _secretsmanager_client

    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager")
    return _secretsmanager_client


def get_openai_key() -> str:
    global _openai_key

    if _openai_key is not None:
        return _openai_key

    secret_name = os.environ["OPENAI_SECRET_NAME"]
    client = get_secretsmanager_client()
    response = client.get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString")
    if secret_string is None:
        raise RuntimeError(f"Secret {secret_name} did not contain SecretString")

    _openai_key = secret_string
    return _openai_key


def log(message: str, **fields: Any) -> None:
    print(json.dumps({"message": message, **fields}, default=str))


def request_id(context: Any) -> str | None:
    return getattr(context, "aws_request_id", None)


def response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_context = event.get("requestContext", {})
    identity = request_context.get("identity", {})
    openai_secret_loaded = False
    aws_request_id = request_id(context)

    log(
        "broker_request_started",
        aws_request_id=aws_request_id,
        http_method=event.get("httpMethod"),
        path=event.get("path"),
        request_context_request_id=request_context.get("requestId"),
        has_query=bool(event.get("queryStringParameters")),
    )

    if event.get("httpMethod") != "GET":
        log(
            "broker_request_rejected",
            aws_request_id=aws_request_id,
            reason="method_not_allowed",
            http_method=event.get("httpMethod"),
        )
        return response(
            405,
            {
                "error": "method_not_allowed",
                "message": "Credentials endpoint only supports GET.",
            },
        )

    caller_arn = identity.get("userArn") or identity.get("caller")
    access_key = identity.get("accessKey")

    if not caller_arn and not access_key:
        log(
            "broker_request_rejected",
            aws_request_id=aws_request_id,
            reason="missing_iam_identity",
            identity_keys=sorted(identity.keys()),
        )
        return response(
            401,
            {
                "error": "missing_iam_identity",
                "message": "Credentials endpoint requires IAM-authenticated caller context.",
            },
        )

    try:
        openai_secret_loaded = bool(get_openai_key())
    except Exception as error:
        log(
            "broker_secret_check_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        return response(
            500,
            {
                "error": "openai_secret_check_failed",
                "service": "broker-api",
                "openai_secret_loaded": False,
                "message": str(error),
            },
        )

    query = event.get("queryStringParameters") or {}
    log(
        "broker_request_succeeded",
        aws_request_id=aws_request_id,
        caller_arn=caller_arn,
        has_access_key=bool(access_key),
        openai_secret_loaded=openai_secret_loaded,
        requested_action=query.get("action"),
        requested_resource=query.get("resource"),
    )

    return response(
        200,
        {
            "status": "ok",
            "service": "broker-api",
            "caller_type": "agent",
            "trusted_identity": {
                "iam_user_arn": caller_arn,
                "access_key": access_key,
            },
            "openai_secret_loaded": openai_secret_loaded,
            "request": {
                "action": query.get("action"),
                "resource": query.get("resource"),
                "reason": query.get("reason"),
            },
            "note": "Broker plumbing only. LLM review and STS issuance are not implemented yet.",
        },
    )
