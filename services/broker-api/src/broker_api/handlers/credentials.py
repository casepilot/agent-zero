import json
import os
from typing import Any

import boto3

from broker_api.aws.console_url import build_console_login_url
from broker_api.aws.sts import assume_scoped_role
from broker_api.data.resource_catalog import get_resource_catalog
from broker_api.llm.reviewer import ApprovalFailed, approve_user_request
from broker_api.policy.build_session_policy import build_session_policy


_dynamodb_resource: Any | None = None
_openai_key: str | None = None
_secretsmanager_client: Any | None = None


def get_dynamodb_resource() -> Any:
    global _dynamodb_resource
    if _dynamodb_resource is None:
        _dynamodb_resource = boto3.resource("dynamodb")
    return _dynamodb_resource


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
    response = get_secretsmanager_client().get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString")
    if secret_string is None:
        raise RuntimeError(f"Secret {secret_name} did not contain SecretString")

    try:
        secret_json = json.loads(secret_string)
    except json.JSONDecodeError:
        _openai_key = secret_string
    else:
        _openai_key = (
            secret_json.get("OPENAI_API_KEY")
            or secret_json.get("openai_api_key")
            or secret_json.get("api_key")
            or secret_json.get("api-key")
            or secret_json.get("apiKey")
            or secret_string
        )
    return _openai_key


def log(message: str, **fields: Any) -> None:
    print(json.dumps({"message": message, **fields}, default=str))


def request_id(context: Any) -> str | None:
    return getattr(context, "aws_request_id", None)


def response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def bool_param(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes"}


def safe_error_message(error: Exception) -> str:
    message = str(error).splitlines()[0]
    if "Incorrect API key provided" in message:
        return "OpenAI authentication failed."
    return message


def load_policy(user_id: str) -> str | None:
    table = get_dynamodb_resource().Table(os.environ["POLICY_TABLE_NAME"])
    item = table.get_item(Key={"user_id": user_id}).get("Item")
    if not item:
        return None
    policy = item.get("policy")
    if not isinstance(policy, str) or not policy.strip():
        return None
    return policy.strip()


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    aws_request_id = request_id(context)
    request_context = event.get("requestContext", {})
    identity = request_context.get("identity", {})
    query = event.get("queryStringParameters") or {}

    log(
        "broker_request_started",
        aws_request_id=aws_request_id,
        http_method=event.get("httpMethod"),
        path=event.get("path"),
        request_context_request_id=request_context.get("requestId"),
        query_keys=sorted(query.keys()),
    )

    if event.get("httpMethod") != "GET":
        log("broker_request_rejected", aws_request_id=aws_request_id, reason="method")
        return response(405, {"error": "method_not_allowed"})

    caller_arn = identity.get("userArn") or identity.get("caller")
    if not caller_arn and not identity.get("accessKey"):
        log(
            "broker_request_rejected",
            aws_request_id=aws_request_id,
            reason="missing_iam_identity",
            identity_keys=sorted(identity.keys()),
        )
        return response(401, {"error": "missing_iam_identity"})

    if "resource" in query:
        log(
            "broker_request_rejected",
            aws_request_id=aws_request_id,
            reason="caller_supplied_resource",
        )
        return response(
            400,
            {
                "error": "resource_not_allowed",
                "message": "Resource is chosen by the broker, not by the caller.",
            },
        )

    user_id = query.get("user_id")
    reason = query.get("reason")
    if not user_id or not reason:
        log(
            "broker_request_rejected",
            aws_request_id=aws_request_id,
            reason="missing_required_query",
            has_user_id=bool(user_id),
            has_reason=bool(reason),
        )
        return response(
            400,
            {"error": "bad_request", "message": "user_id and reason are required."},
        )

    policy_text = load_policy(user_id)
    if policy_text is None:
        log(
            "broker_request_denied",
            aws_request_id=aws_request_id,
            user_id=user_id,
            reason="no_policy_found",
        )
        return response(
            403,
            {
                "error": "no_policy_found",
                "message": f"No policy found for {user_id}.",
            },
        )

    catalog = get_resource_catalog()
    try:
        decision = approve_user_request(
            openai_api_key=get_openai_key(),
            catalog=catalog,
            policy_text=policy_text,
            reason=reason,
        )
    except ApprovalFailed as error:
        log(
            "broker_llm_validation_failed",
            aws_request_id=aws_request_id,
            user_id=user_id,
            error=str(error),
        )
        return response(500, {"error": "decision_failed", "message": str(error)})
    except Exception as error:
        log(
            "broker_llm_failed",
            aws_request_id=aws_request_id,
            user_id=user_id,
            error_type=type(error).__name__,
            error=safe_error_message(error),
        )
        return response(500, {"error": "llm_failed", "message": safe_error_message(error)})

    if not decision.approved:
        log(
            "broker_request_denied",
            aws_request_id=aws_request_id,
            user_id=user_id,
            reason="llm_denied",
            decision_reason=decision.reason,
        )
        return response(
            403,
            {
                "error": "access_denied",
                "decision": decision.model_dump(),
            },
        )

    session_policy = build_session_policy(decision, catalog)
    try:
        credentials = assume_scoped_role(
            user_id=user_id,
            decision=decision,
            session_policy=session_policy,
        )
        body: dict[str, Any] = {
            "status": "approved",
            "user_id": user_id,
            "decision": decision.model_dump(),
            "session_policy": session_policy,
            "credentials": credentials,
        }
        if bool_param(query.get("is_staff")):
            body["console_login_url"] = build_console_login_url(credentials)
    except Exception as error:
        log(
            "broker_sts_failed",
            aws_request_id=aws_request_id,
            user_id=user_id,
            error_type=type(error).__name__,
            error=str(error),
        )
        return response(500, {"error": "credential_issue_failed", "message": str(error)})

    log(
        "broker_request_approved",
        aws_request_id=aws_request_id,
        user_id=user_id,
        caller_arn=caller_arn,
        is_staff=bool_param(query.get("is_staff")),
        grant_count=len(decision.grants),
    )
    return response(200, body)
