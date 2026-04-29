import json
import os
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest


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


def sign_headers(method: str, url: str) -> dict[str, str]:
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        raise RuntimeError("Lambda execution credentials were not available")

    aws_request = AWSRequest(method=method, url=url)
    SigV4Auth(credentials.get_frozen_credentials(), "execute-api", os.environ["AWS_REGION"]).add_auth(
        aws_request
    )
    return dict(aws_request.headers.items())


def call_credentials_endpoint(payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    query = {
        "action": payload.get("action", ""),
        "resource": payload.get("resource", ""),
        "reason": payload.get("reason", ""),
    }
    credentials_url = f"{os.environ['CREDENTIALS_URL']}?{urlencode(query)}"
    request = Request(
        credentials_url,
        method="GET",
        headers=sign_headers("GET", credentials_url),
    )

    with urlopen(request, timeout=10) as result:
        body = result.read().decode("utf-8")
        return result.status, json.loads(body)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if event.get("httpMethod") != "POST":
        return response(
            405,
            {
                "error": "method_not_allowed",
                "message": "Agent endpoint only supports POST.",
            },
        )

    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    human_user_id = claims.get("sub")
    payload = parse_body(event)

    try:
        status_code, broker_body = call_credentials_endpoint(payload)
    except Exception as error:
        return response(
            502,
            {
                "error": "broker_call_failed",
                "message": str(error),
            },
        )

    return response(
        status_code,
        {
            "status": "ok",
            "service": "agent-api",
            "human_user_id": human_user_id,
            "broker_response": broker_body,
        },
    )
