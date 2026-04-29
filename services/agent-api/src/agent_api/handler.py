import json
import os
from typing import Any
from urllib.parse import quote, urlencode

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.httpsession import URLLib3Session


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


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if not body:
        return {}

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed
    return {}


def sign_request(method: str, url: str) -> AWSRequest:
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        raise RuntimeError("Lambda execution credentials were not available")

    aws_request = AWSRequest(method=method, url=url)
    SigV4Auth(credentials.get_frozen_credentials(), "execute-api", os.environ["AWS_REGION"]).add_auth(
        aws_request
    )
    return aws_request


def call_credentials_endpoint(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    query = {
        "action": payload.get("action", ""),
        "resource": payload.get("resource", ""),
        "reason": payload.get("reason", ""),
    }
    credentials_url = f"{os.environ['CREDENTIALS_URL']}?{urlencode(query, quote_via=quote)}"
    prepared_request = sign_request("GET", credentials_url).prepare()
    result = URLLib3Session(timeout=10).send(prepared_request)
    body = result.content.decode("utf-8")

    try:
        parsed_body = json.loads(body)
    except json.JSONDecodeError:
        parsed_body = {"raw_body": body}

    return result.status_code, parsed_body


def sanitize_broker_body(status_code: int, broker_body: dict[str, Any]) -> dict[str, Any]:
    if status_code < 400:
        return broker_body

    message = broker_body.get("message")
    safe_message = None
    if isinstance(message, str):
        safe_message = message.splitlines()[0]

    return {
        "error": broker_body.get("error", "broker_request_failed"),
        "message": safe_message or "Broker request failed.",
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    aws_request_id = request_id(context)
    request_context = event.get("requestContext", {})
    log(
        "agent_request_started",
        aws_request_id=aws_request_id,
        http_method=event.get("httpMethod"),
        path=event.get("path"),
        request_context_request_id=request_context.get("requestId"),
        has_authorizer=bool(request_context.get("authorizer")),
    )

    if event.get("httpMethod") != "POST":
        log(
            "agent_request_rejected",
            aws_request_id=aws_request_id,
            reason="method_not_allowed",
            http_method=event.get("httpMethod"),
        )
        return response(
            405,
            {
                "error": "method_not_allowed",
                "message": "Agent endpoint only supports POST.",
            },
        )

    claims = (
        request_context
        .get("authorizer", {})
        .get("claims", {})
    )
    human_user_id = claims.get("sub")
    payload = parse_body(event)
    log(
        "agent_payload_parsed",
        aws_request_id=aws_request_id,
        human_user_id=human_user_id,
        payload_keys=sorted(payload.keys()),
        requested_action=payload.get("action"),
        requested_resource=payload.get("resource"),
    )

    try:
        openai_secret_loaded = bool(get_openai_key())
    except Exception as error:
        log(
            "agent_secret_check_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        return response(
            500,
            {
                "error": "openai_secret_check_failed",
                "service": "agent-api",
                "openai_secret_loaded": False,
                "message": str(error),
            },
        )

    try:
        status_code, broker_body = call_credentials_endpoint(payload)
    except Exception as error:
        log(
            "agent_broker_call_exception",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        return response(
            502,
            {
                "error": "broker_call_failed",
                "message": str(error),
            },
        )

    safe_broker_body = sanitize_broker_body(status_code, broker_body)
    log(
        "agent_broker_call_completed",
        aws_request_id=aws_request_id,
        broker_status_code=status_code,
        broker_error=safe_broker_body.get("error"),
        broker_secret_loaded=safe_broker_body.get("openai_secret_loaded"),
    )

    return response(
        status_code,
        {
            "status": "ok",
            "service": "agent-api",
            "human_user_id": human_user_id,
            "openai_secret_loaded": openai_secret_loaded,
            "broker_response": safe_broker_body,
        },
    )
