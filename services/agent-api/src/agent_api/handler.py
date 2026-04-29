import asyncio
import json
import os
import time
import uuid
from enum import Enum
from typing import Any
from urllib.parse import urlencode

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError
from botocore.httpsession import URLLib3Session


_apigateway_management_clients: dict[str, Any] = {}
_lambda_client: Any | None = None
_openai_key: str | None = None
_secretsmanager_client: Any | None = None
_http_session: URLLib3Session | None = None
DEFAULT_AGENT_MODEL = "gpt-5.5"
DEFAULT_AGENT_REASONING_EFFORT = "medium"
STAFF_GROUPS = {"admin", "employee"}


class MarkerType(str, Enum):
    COT = "cot_token"
    GENERATING_SUMMARY = "generating_summary"
    USER_VISIBLE_TOKEN = "user_visible_token"
    END_TURN = "end_turn"


class StreamMessageType(str, Enum):
    MESSAGE_MARKER = "message_marker"
    DELTA_MSG = "delta"
    COMPLETED_MSG = "completed_message"


class OperationType(str, Enum):
    ADD = "add"
    APPEND = "append"
    REPLACE = "replace"
    PATCH = "patch"


class MessageType(str, Enum):
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ASSISTANT_MESSAGE = "assistant_message"


class MessageStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class Role(str, Enum):
    ASSISTANT = "assistant"


def agent_instructions() -> str:
    policy_table_name = os.environ.get("POLICY_TABLE_NAME", "policy-table")
    policy_table_arn = os.environ.get(
        "POLICY_TABLE_ARN",
        "arn:aws:dynamodb:ap-southeast-2:338375260114:table/policy-table",
    )

    return f"""You are UserAgent, an internal IAM access assistant.

Help company users request temporary AWS access and help identity admins create,
edit, read, or delete free-text access policies.

Policy table context:
- DynamoDB table name: {policy_table_name}
- DynamoDB table ARN: {policy_table_arn}
- Region: ap-southeast-2
- Account: 338375260114
- Partition key: user_id
- Policy attribute: policy
- Item shape: {{"user_id": "<target user id>", "policy": "<free-text role policy>"}}

When a user asks to create, edit, read, or delete a policy:
- Ask for the target user_id if it is missing. The target user_id is the
  principal whose policy should be created, edited, read, or deleted.
- Treat the free-text policy as the user's business role at the company, not as
  an AWS IAM JSON policy.
- Keep the policy plain language, scoped to the user's job, and explicit about
  what the user must not do.
- For policy-table write access, the requesting user must be an access
  administrator. Non-admin users should be told they cannot change policies.
- For create or edit, write one item in the policy table with user_id and
  policy.
- For delete, delete only the item for the requested user_id.

Example policy to create when requested:
James Brown is an IT support engineer. Their job is to investigate assigned IT
support tickets, customer authorisation problems, account access issues, and
operational incidents. They may request temporary access to relevant company
systems when the request is tied to a specific ticket and limited to support
work. They are not an access administrator and should not change access
policies.

Example CLI access after temporary policy-table credentials are approved:
- Read: aws dynamodb get-item --table-name {policy_table_name} --key '{{"user_id": {{"S": "<target user id>"}}}}'
- Create or replace: aws dynamodb put-item --table-name {policy_table_name} --item '{{"user_id": {{"S": "<target user id>"}}, "policy": {{"S": "<free-text policy>"}}}}'
- Edit policy text: aws dynamodb update-item --table-name {policy_table_name} --key '{{"user_id": {{"S": "<target user id>"}}}}' --update-expression 'SET #policy = :policy' --expression-attribute-names '{{"#policy": "policy"}}' --expression-attribute-values '{{":policy": {{"S": "<free-text policy>"}}}}'
- Delete: aws dynamodb delete-item --table-name {policy_table_name} --key '{{"user_id": {{"S": "<target user id>"}}}}'

Access request behavior:
- Use the request_aws_access tool to request just-in-time AWS credentials from
  AgentZero after the user gives a clear business reason.
- The tool can return scoped STS credentials and, for staff users, an AWS
  console login URL.
- If the user is vague, ask one concise follow-up question asking why they need
  the permissions before using the tool.
- Do not invent ticket IDs, resources, users, or reasons.
- After the tool returns, explain whether access was approved or denied and
  include the broker's risk, authorization, and reason fields when present.
- For this demo, call check_agent_employee_access exactly once before your final
  answer. Then answer the user's request normally.
"""


def get_lambda_client() -> Any:
    global _lambda_client

    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


def get_apigateway_management_client(domain_name: str, stage: str) -> Any:
    endpoint_url = f"https://{domain_name}/{stage}"
    if endpoint_url not in _apigateway_management_clients:
        _apigateway_management_clients[endpoint_url] = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=endpoint_url,
        )
    return _apigateway_management_clients[endpoint_url]


def get_secretsmanager_client() -> Any:
    global _secretsmanager_client

    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager")
    return _secretsmanager_client


def get_http_session() -> URLLib3Session:
    global _http_session

    if _http_session is None:
        _http_session = URLLib3Session()
    return _http_session


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


def prompt_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("message", "prompt", "reason"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def groups_from_value(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(group).strip() for group in value if str(group).strip()}
    if isinstance(value, str):
        return {group.strip() for group in value.split(",") if group.strip()}
    return set()


def is_staff_from_groups(groups: set[str]) -> bool:
    return bool(groups & STAFF_GROUPS)


def validate_worker_payload(payload: dict[str, Any]) -> list[str]:
    missing = []
    request_id_value = payload.get("requestId")
    if not isinstance(request_id_value, str) or not request_id_value.strip():
        missing.append("requestId")
    if prompt_from_payload(payload) is None:
        missing.append("message, prompt, or reason")
    return missing


def authorizer_context(request_context: dict[str, Any]) -> dict[str, Any]:
    authorizer = request_context.get("authorizer") or {}
    if "user_id" in authorizer:
        return authorizer
    return authorizer.get("claims") or {}


def websocket_response(status_code: int = 200) -> dict[str, Any]:
    return {"statusCode": status_code}


def send_ws_message(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    payload: dict[str, Any],
) -> bool:
    client = get_apigateway_management_client(domain_name, stage)
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload, default=str).encode("utf-8"),
        )
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "GoneException":
            log(
                "websocket_connection_gone",
                connection_id=connection_id,
                payload_type=payload.get("type"),
            )
            return False
        raise


def stream_text(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    request_id: str | None,
    text: str,
) -> bool:
    return send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={"type": "delta", "requestId": request_id, "text": text},
    )


def signed_get_json(url: str) -> tuple[int, dict[str, Any]]:
    region = os.environ.get("AWS_REGION", "ap-southeast-2")
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        raise RuntimeError("AWS credentials were not available for broker call")

    request = AWSRequest(method="GET", url=url)
    SigV4Auth(credentials.get_frozen_credentials(), "execute-api", region).add_auth(
        request
    )
    response = get_http_session().send(request.prepare())
    response_body = response.content.decode("utf-8")
    try:
        parsed = json.loads(response_body) if response_body else {}
    except json.JSONDecodeError:
        parsed = {"raw_body": response_body}
    return response.status_code, parsed


def call_broker_credentials(
    *,
    user_id: str,
    reason: str,
    is_staff: bool,
) -> dict[str, Any]:
    credentials_url = os.environ["CREDENTIALS_URL"]
    query = urlencode(
        {
            "user_id": user_id,
            "reason": reason,
            "is_staff": "true" if is_staff else "false",
        }
    )
    separator = "&" if "?" in credentials_url else "?"
    url = f"{credentials_url}{separator}{query}"
    status_code, body = signed_get_json(url)
    return {
        "status_code": status_code,
        "ok": 200 <= status_code < 300,
        "body": body,
    }


async def stream_friendly_agent_response(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    request_id: str | None,
    prompt: str,
    openai_api_key: str,
    user_id: str,
    is_staff: bool,
) -> None:
    from agents import Agent, ModelSettings, Runner, function_tool, set_default_openai_key

    @function_tool
    def request_aws_access(reason: str) -> dict[str, Any]:
        """Request just-in-time AWS access from AgentZero.

        Use this only after the user gives a clear business reason. It returns
        scoped STS credentials and, for staff users, an AWS console login URL.
        """
        if not isinstance(reason, str) or not reason.strip():
            return {
                "status_code": 400,
                "ok": False,
                "body": {
                    "error": "missing_reason",
                    "message": "A clear business reason is required.",
                },
            }

        log(
            "agent_broker_tool_started",
            user_id=user_id,
            request_id=request_id,
            is_staff=is_staff,
            reason_length=len(reason.strip()),
        )
        broker_result = call_broker_credentials(
            user_id=user_id,
            reason=reason.strip(),
            is_staff=is_staff,
        )
        log(
            "agent_broker_tool_completed",
            user_id=user_id,
            request_id=request_id,
            status_code=broker_result["status_code"],
            ok=broker_result["ok"],
            broker_error=broker_result["body"].get("error"),
        )
        send_ws_message(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            payload={
                "type": "broker_result",
                "requestId": request_id,
                "result": broker_result,
            },
        )
        return broker_result

    set_default_openai_key(openai_api_key)
    agent = Agent(
        name="UserAgent",
        instructions=agent_instructions(),
        model=os.environ.get("AGENT_MODEL", DEFAULT_AGENT_MODEL),
        model_settings=ModelSettings(
            reasoning={
                "effort": os.environ.get(
                    "AGENT_REASONING_EFFORT",
                    DEFAULT_AGENT_REASONING_EFFORT,
                )
            },
        ),
        tools=[request_aws_access],
    )
    result = Runner.run_streamed(agent, input=prompt)

    async for event in result.stream_events():
        if getattr(event, "type", None) != "raw_response_event":
            continue

        data = getattr(event, "data", None)
        delta = getattr(data, "delta", None)
        if not isinstance(delta, str) or not delta:
            continue

        if not stream_text(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            request_id=request_id,
            text=delta,
        ):
            break


def invoke_worker(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    user_id: str,
    groups: str | list[str] | None,
    payload: dict[str, Any],
) -> None:
    get_lambda_client().invoke(
        FunctionName=os.environ["AGENT_WORKER_FUNCTION_NAME"],
        InvocationType="Event",
        Payload=json.dumps(
            {
                "connection_id": connection_id,
                "domain_name": domain_name,
                "stage": stage,
                "user_id": user_id,
                "groups": groups,
                "payload": payload,
            }
        ).encode("utf-8"),
    )


def route_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    aws_request_id = request_id(context)
    request_context = event.get("requestContext", {})
    route_key = request_context.get("routeKey")
    log(
        "agent_websocket_event_started",
        aws_request_id=aws_request_id,
        route_key=route_key,
        request_context_request_id=request_context.get("requestId"),
        has_authorizer=bool(request_context.get("authorizer")),
    )

    if route_key in {"$connect", "$disconnect"}:
        return websocket_response(200)

    if route_key == "$default":
        log(
            "agent_websocket_rejected",
            aws_request_id=aws_request_id,
            reason="unknown_route",
        )
        return websocket_response(400)

    if route_key != "requestAccess":
        return websocket_response(400)

    auth_context = authorizer_context(request_context)
    human_user_id = auth_context.get("user_id") or auth_context.get("sub")
    groups = auth_context.get("groups") or auth_context.get("cognito:groups")
    payload = parse_body(event)
    log(
        "agent_websocket_payload_parsed",
        aws_request_id=aws_request_id,
        human_user_id=human_user_id,
        groups=sorted(groups_from_value(groups)),
        payload_keys=sorted(payload.keys()),
        has_reason=bool(payload.get("reason")),
    )

    try:
        if not human_user_id:
            raise RuntimeError("Cognito sub was missing from the request context")
        invoke_worker(
            connection_id=request_context["connectionId"],
            domain_name=request_context["domainName"],
            stage=request_context["stage"],
            user_id=human_user_id,
            groups=groups,
            payload=payload,
        )
    except Exception as error:
        log(
            "agent_worker_invoke_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        return websocket_response(500)

    return websocket_response(200)


def worker_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    aws_request_id = request_id(context)
    connection_id = event["connection_id"]
    domain_name = event["domain_name"]
    stage = event["stage"]
    human_user_id = event["user_id"]
    groups = groups_from_value(event.get("groups"))
    is_staff = is_staff_from_groups(groups)
    payload = event.get("payload") or {}
    request_id_value = payload.get("requestId")

    log(
        "agent_worker_started",
        aws_request_id=aws_request_id,
        human_user_id=human_user_id,
        groups=sorted(groups),
        is_staff=is_staff,
        request_id=request_id_value,
        payload_keys=sorted(payload.keys()),
    )

    if not send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={"type": "ack", "requestId": request_id_value},
    ):
        return {"statusCode": 410}

    missing_fields = validate_worker_payload(payload)
    if missing_fields:
        send_ws_message(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            payload={
                "type": "error",
                "requestId": request_id_value,
                "error": "invalid_request",
                "message": f"Missing required field(s): {', '.join(missing_fields)}.",
                "missing": missing_fields,
            },
        )
        return {"statusCode": 400}
    prompt = prompt_from_payload(payload)
    assert prompt is not None

    try:
        openai_api_key = get_openai_key()
    except Exception as error:
        log(
            "agent_secret_check_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        send_ws_message(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            payload={
                "type": "error",
                "requestId": request_id_value,
                "error": "openai_secret_check_failed",
                "message": str(error),
            },
        )
        return {"statusCode": 500}

    try:
        asyncio.run(
            stream_friendly_agent_response(
                connection_id=connection_id,
                domain_name=domain_name,
                stage=stage,
                request_id=request_id_value,
                prompt=prompt,
                openai_api_key=openai_api_key,
                user_id=human_user_id,
                is_staff=is_staff,
            )
        )
    except Exception as error:
        log(
            "agent_sdk_stream_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        send_ws_message(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            payload={
                "type": "error",
                "requestId": request_id_value,
                "error": "agent_stream_failed",
                "message": str(error),
            },
        )
        return {"statusCode": 502}

    log(
        "agent_sdk_stream_completed",
        aws_request_id=aws_request_id,
        human_user_id=human_user_id,
        request_id=request_id_value,
    )
    send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={"type": "done", "requestId": request_id_value},
    )
    return {"statusCode": 200}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if "routeKey" in event.get("requestContext", {}):
        return route_handler(event, context)
    return worker_handler(event, context)
