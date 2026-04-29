import json
import os
from datetime import UTC, datetime
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


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def clean_audit_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        cleaned = {
            key: clean_audit_value(child)
            for key, child in value.items()
            if child is not None
        }
        return {key: child for key, child in cleaned.items() if child is not None}
    if isinstance(value, list):
        return [
            child
            for child in (clean_audit_value(child) for child in value)
            if child is not None
        ]
    return value


def get_request_logs_table() -> Any:
    return get_dynamodb_resource().Table(os.environ["REQUEST_LOGS_TABLE_NAME"])


def build_audit_context(
    *,
    event: dict[str, Any],
    context: Any,
    request_context: dict[str, Any],
    identity: dict[str, Any],
    query: dict[str, Any],
) -> dict[str, Any]:
    audit_request_id = (
        request_id(context)
        or request_context.get("requestId")
        or "unknown-request"
    )
    caller_arn = identity.get("userArn") or identity.get("caller")
    return {
        "request_id": audit_request_id,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "http_method": event.get("httpMethod"),
        "path": event.get("path"),
        "api_gateway_request_id": request_context.get("requestId"),
        "lambda_request_id": request_id(context),
        "caller_arn": caller_arn,
        "identity_keys": sorted(identity.keys()),
        "user_id": query.get("user_id"),
        "request_reason": query.get("reason"),
        "requested_console_url": bool_param(query.get("is_staff")),
    }


def put_audit_record(item: dict[str, Any], *, required: bool = False) -> bool:
    audit_item = clean_audit_value(item)
    try:
        get_request_logs_table().put_item(Item=audit_item)
        return True
    except Exception as error:
        log(
            "broker_audit_log_failed",
            request_id=item.get("request_id"),
            status=item.get("status"),
            error_type=type(error).__name__,
            error=safe_error_message(error),
        )
        if required:
            raise
        return False


def audit_terminal(
    base: dict[str, Any],
    *,
    status: str,
    required: bool = False,
    **fields: Any,
) -> bool:
    item = {
        **base,
        **fields,
        "status": status,
        "updated_at": utc_now(),
    }
    return put_audit_record(item, required=required)


def load_policy(user_id: str) -> str | None:
    table = get_dynamodb_resource().Table(os.environ["POLICY_TABLE_NAME"])
    item = table.get_item(Key={"user_id": user_id}).get("Item")
    if not item:
        return None
    policy = item.get("policy")
    if not isinstance(policy, str) or not policy.strip():
        return None
    return policy.strip()


def load_user_role(user_id: str) -> str | None:
    table = get_dynamodb_resource().Table(os.environ["USERS_TABLE_NAME"])
    item = table.get_item(Key={"user_id": user_id}).get("Item")
    if not item:
        return None
    role = item.get("role")
    if not isinstance(role, str):
        return None
    return role


def load_user_profile(user_id: str) -> dict[str, Any]:
    table = get_dynamodb_resource().Table(os.environ["USERS_TABLE_NAME"])
    item = table.get_item(Key={"user_id": user_id}).get("Item") or {}
    if not isinstance(item, dict):
        return {}
    return item


def user_audit_fields(user_profile: dict[str, Any]) -> dict[str, Any]:
    role = user_profile.get("role")
    is_human = user_profile.get("is_human")
    if isinstance(is_human, bool):
        principal_type = "human" if is_human else "agent"
    else:
        principal_type = None
    return {
        "principal_type": principal_type,
        "principal_role": role if isinstance(role, str) else None,
        "principal_name": user_profile.get("name"),
        "principal_username": user_profile.get("username"),
    }


def safe_session_name(user_id: str, audit_request_id: str) -> str:
    safe_user_id = "".join(
        character if character.isalnum() or character in ("-", "_") else "-"
        for character in user_id
    )[:32]
    safe_request_id = "".join(
        character if character.isalnum() or character in ("-", "_") else "-"
        for character in audit_request_id
    )[-20:]
    return f"agent-zero-{safe_user_id}-{safe_request_id}"[:64]


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    aws_request_id = request_id(context)
    request_context = event.get("requestContext", {})
    identity = request_context.get("identity", {})
    query = event.get("queryStringParameters") or {}
    audit_base = build_audit_context(
        event=event,
        context=context,
        request_context=request_context,
        identity=identity,
        query=query,
    )

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
        audit_terminal(
            audit_base,
            status="rejected",
            error_code="method_not_allowed",
            error_message="Only GET is allowed.",
        )
        return response(405, {"error": "method_not_allowed"})

    caller_arn = identity.get("userArn") or identity.get("caller")
    if not caller_arn and not identity.get("accessKey"):
        log(
            "broker_request_rejected",
            aws_request_id=aws_request_id,
            reason="missing_iam_identity",
            identity_keys=sorted(identity.keys()),
        )
        audit_terminal(
            audit_base,
            status="rejected",
            error_code="missing_iam_identity",
            error_message="IAM identity was missing from the request.",
        )
        return response(401, {"error": "missing_iam_identity"})

    if "resource" in query:
        log(
            "broker_request_rejected",
            aws_request_id=aws_request_id,
            reason="caller_supplied_resource",
        )
        audit_terminal(
            audit_base,
            status="rejected",
            error_code="resource_not_allowed",
            error_message="Resource is chosen by the broker, not by the caller.",
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
        audit_terminal(
            audit_base,
            status="rejected",
            error_code="bad_request",
            error_message="user_id and reason are required.",
            has_user_id=bool(user_id),
            has_reason=bool(reason),
        )
        return response(
            400,
            {"error": "bad_request", "message": "user_id and reason are required."},
        )

    user_profile = load_user_profile(user_id)
    audit_base = {
        **audit_base,
        **user_audit_fields(user_profile),
    }
    policy_text = load_policy(user_id)
    if policy_text is None:
        log(
            "broker_request_denied",
            aws_request_id=aws_request_id,
            user_id=user_id,
            reason="no_policy_found",
        )
        audit_terminal(
            audit_base,
            status="denied",
            error_code="no_policy_found",
            error_message=f"No policy found for {user_id}.",
            policy_snapshot=None,
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
        audit_terminal(
            audit_base,
            status="error",
            error_code="decision_failed",
            error_type=type(error).__name__,
            error_message=str(error),
            policy_snapshot=policy_text,
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
        audit_terminal(
            audit_base,
            status="error",
            error_code="llm_failed",
            error_type=type(error).__name__,
            error_message=safe_error_message(error),
            policy_snapshot=policy_text,
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
        audit_terminal(
            audit_base,
            status="denied",
            error_code="access_denied",
            error_message=decision.reason,
            policy_snapshot=policy_text,
            decision=decision.model_dump(),
            validator_result="passed",
            grants=[],
            duration_seconds=decision.duration_seconds,
        )
        return response(
            403,
            {
                "error": "access_denied",
                "decision": decision.model_dump(),
            },
        )

    user_role = load_user_role(user_id)
    session_policy = build_session_policy(
        decision,
        catalog,
        user_id=user_id,
        include_dynamodb_list_tables=user_role == "employee",
        include_dynamodb_scan=bool_param(query.get("is_staff")),
    )
    role_session_name = safe_session_name(user_id, audit_base["request_id"])
    target_role_arn = os.environ["BROKER_CREDENTIALS_ROLE_ARN"]
    try:
        audit_terminal(
            audit_base,
            status="approved_pending_sts",
            required=True,
            policy_snapshot=policy_text,
            decision=decision.model_dump(),
            validator_result="passed",
            grants=[grant.model_dump() for grant in decision.grants],
            duration_seconds=decision.duration_seconds,
            session_policy=session_policy,
            target_role_arn=target_role_arn,
            role_session_name=role_session_name,
        )
    except Exception as error:
        return response(
            500,
            {
                "error": "audit_log_failed",
                "message": safe_error_message(error),
            },
        )

    try:
        credentials = assume_scoped_role(
            user_id=user_id,
            decision=decision,
            session_policy=session_policy,
            role_session_name=role_session_name,
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
        audit_terminal(
            audit_base,
            status="error",
            error_code="credential_issue_failed",
            error_type=type(error).__name__,
            error_message=safe_error_message(error),
            policy_snapshot=policy_text,
            decision=decision.model_dump(),
            validator_result="passed",
            grants=[grant.model_dump() for grant in decision.grants],
            duration_seconds=decision.duration_seconds,
            session_policy=session_policy,
            target_role_arn=target_role_arn,
            role_session_name=role_session_name,
        )
        return response(500, {"error": "credential_issue_failed", "message": str(error)})

    audit_terminal(
        audit_base,
        status="approved",
        policy_snapshot=policy_text,
        decision=decision.model_dump(),
        validator_result="passed",
        grants=[grant.model_dump() for grant in decision.grants],
        duration_seconds=decision.duration_seconds,
        session_policy=session_policy,
        target_role_arn=target_role_arn,
        role_session_name=role_session_name,
        assumed_role_arn=credentials.get("assumed_role_arn"),
        assumed_role_id=credentials.get("assumed_role_id"),
        credentials_expiration=credentials.get("expiration"),
    )
    log(
        "broker_request_approved",
        aws_request_id=aws_request_id,
        user_id=user_id,
        caller_arn=caller_arn,
        is_staff=bool_param(query.get("is_staff")),
        grant_count=len(decision.grants),
    )
    return response(200, body)
