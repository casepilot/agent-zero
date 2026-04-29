import json
from typing import Any


def response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_context = event.get("requestContext", {})
    identity = request_context.get("identity", {})

    if event.get("httpMethod") != "GET":
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
        return response(
            401,
            {
                "error": "missing_iam_identity",
                "message": "Credentials endpoint requires IAM-authenticated caller context.",
            },
        )

    query = event.get("queryStringParameters") or {}

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
            "request": {
                "action": query.get("action"),
                "resource": query.get("resource"),
                "reason": query.get("reason"),
            },
            "note": "Broker plumbing only. LLM review and STS issuance are not implemented yet.",
        },
    )
