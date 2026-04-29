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


def stream_context_from_payload(
    *,
    payload: dict[str, Any],
    request_id: str,
    user_id: str,
) -> dict[str, str]:
    thread_id = payload.get("threadId")
    parent_id = payload.get("parentId") or payload.get("turnId")
    tenant_id = payload.get("tenantId")
    case_id = payload.get("caseId")
    return {
        "threadId": thread_id if isinstance(thread_id, str) and thread_id else request_id,
        "parentId": parent_id if isinstance(parent_id, str) and parent_id else request_id,
        "tenantId": tenant_id if isinstance(tenant_id, str) and tenant_id else user_id,
        "caseId": case_id if isinstance(case_id, str) and case_id else "agent-zero-demo",
    }


class WebSocketAgentStream:
    def __init__(
        self,
        *,
        connection_id: str,
        domain_name: str,
        stage: str,
        request_id: str,
        stream_context: dict[str, str],
    ) -> None:
        self.connection_id = connection_id
        self.domain_name = domain_name
        self.stage = stage
        self.request_id = request_id
        self.thread_id = stream_context["threadId"]
        self.parent_id = stream_context["parentId"]
        self.tenant_id = stream_context["tenantId"]
        self.case_id = stream_context["caseId"]
        self.sequence_id = 0
        self.order = 0
        self.stream_started = False
        self.reasoning_active = False
        self.final_message_id: str | None = None
        self.final_answer_content = ""
        self.final_answer_started = False
        self.tool_call_ids_by_call_id: dict[str, str] = {}

    def next_sequence_id(self) -> int:
        self.sequence_id += 1
        return self.sequence_id

    def next_order(self) -> int:
        self.order += 1
        return self.order

    def send_stream(self, stream_type: StreamMessageType, data: Any) -> bool:
        if isinstance(data, dict):
            data = [data]
        return send_ws_message(
            connection_id=self.connection_id,
            domain_name=self.domain_name,
            stage=self.stage,
            payload={
                "type": "stream",
                "requestId": self.request_id,
                "tenantId": self.tenant_id,
                "threadId": self.thread_id,
                "caseId": self.case_id,
                "parentId": self.parent_id,
                "streamType": stream_type.value,
                "timestamp": int(time.time() * 1000),
                "sequenceId": self.next_sequence_id(),
                "data": data,
            },
        )

    def send_message_marker(self, marker: MarkerType) -> bool:
        return self.send_stream(
            StreamMessageType.MESSAGE_MARKER,
            {"marker": marker.value},
        )

    def send_delta_event(
        self,
        *,
        message_id: str,
        message_type: MessageType,
        operation: OperationType,
        status: MessageStatus,
        content: str | None = None,
        role: Role | None = None,
    ) -> bool:
        payload = {
            "type": message_type.value,
            "operation": operation.value,
            "id": message_id,
            "order": self.order,
            "status": status.value,
            "content": content,
        }
        if role is not None:
            payload["role"] = role.value
        return self.send_stream(StreamMessageType.DELTA_MSG, payload)

    def message_record(
        self,
        *,
        message_id: str,
        message_type: MessageType,
        status: MessageStatus,
        group_id: str | None = None,
        order: int | None = None,
        role: Role | None = None,
        content: str | None = None,
        summary: list[str] | None = None,
        arguments: str | None = None,
        tool_name: str | None = None,
        call_id: str | None = None,
        output: str | None = None,
    ) -> dict[str, Any]:
        return {
            "id": message_id,
            "caseId": self.case_id,
            "tenantId": self.tenant_id,
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "itemType": "assistantMessage",
            "data": {
                "threadId": self.thread_id,
                "groupId": group_id or self.parent_id,
                "parentId": self.parent_id,
                "order": order if order is not None else self.order,
                "type": message_type.value,
                "role": role.value if role is not None else None,
                "status": status.value,
                "summary": summary,
                "arguments": arguments,
                "tool_name": tool_name,
                "call_id": call_id,
                "output": output,
                "content": content,
                "thoughtFor": 0 if message_type == MessageType.ASSISTANT_MESSAGE else None,
                "taggedEvidence": [],
                "annotations": [],
            },
        }

    def send_delta_completed_event(
        self,
        *,
        message: dict[str, Any],
        message_type: MessageType,
    ) -> bool:
        return self.send_stream(
            StreamMessageType.DELTA_MSG,
            [
                {
                    "operation": OperationType.PATCH.value,
                    "message": message,
                },
                {
                    "operation": None,
                    "id": message["id"],
                    "type": message_type.value,
                    "status": MessageStatus.COMPLETED.value,
                },
            ],
        )

    def send_full_event(
        self,
        *,
        message: dict[str, Any],
        operation: OperationType,
    ) -> bool:
        return self.send_stream(
            StreamMessageType.COMPLETED_MSG,
            {
                "message": message,
                "operation": operation.value,
                "id": message["id"],
            },
        )

    def complete_tool_call(self, *, call_id: str | None) -> bool:
        if not call_id:
            return True
        message_id = self.tool_call_ids_by_call_id.get(call_id)
        if not message_id:
            return True
        return self.send_delta_event(
            message_id=message_id,
            message_type=MessageType.TOOL_CALL,
            operation=OperationType.REPLACE,
            status=MessageStatus.COMPLETED,
        )

    async def handle_stream_event(self, event: Any) -> None:
        event_type = getattr(event, "type", None)
        if event_type == "agent_updated_stream_event":
            if not self.stream_started:
                self.stream_started = True
                self.send_message_marker(MarkerType.COT)
            return

        if event_type == "run_item_stream_event":
            item = getattr(event, "item", None)
            raw_item = getattr(item, "raw_item", None)
            if getattr(event, "name", None) == "message_output_created" and raw_item is not None:
                self.final_message_id = getattr(raw_item, "id", None) or str(uuid.uuid4())
            if item is not None and item.__class__.__name__ == "ToolCallOutputItem":
                if isinstance(raw_item, dict):
                    call_id = raw_item.get("call_id")
                else:
                    call_id = getattr(raw_item, "call_id", None)
                self.complete_tool_call(call_id=call_id)
            return

        if event_type != "raw_response_event":
            return

        data = getattr(event, "data", None)
        data_type = data.__class__.__name__

        if data_type == "ResponseReasoningSummaryPartAddedEvent":
            self.reasoning_active = True
            self.next_order()
            self.send_delta_event(
                message_id=getattr(data, "item_id", str(uuid.uuid4())),
                message_type=MessageType.REASONING,
                operation=OperationType.ADD,
                status=MessageStatus.IN_PROGRESS,
            )
            return

        if data_type == "ResponseReasoningSummaryTextDeltaEvent":
            self.send_delta_event(
                message_id=getattr(data, "item_id", str(uuid.uuid4())),
                message_type=MessageType.REASONING,
                operation=OperationType.APPEND,
                status=MessageStatus.IN_PROGRESS,
                content=getattr(data, "delta", ""),
            )
            return

        item = getattr(data, "item", None)
        item_type = item.__class__.__name__ if item is not None else ""

        if data_type == "ResponseOutputItemDoneEvent" and item_type == "ResponseReasoningItem" and self.reasoning_active:
            self.reasoning_active = False
            summary = []
            for part in getattr(item, "summary", []) or []:
                text = getattr(part, "text", None)
                if text:
                    summary.append(text)
            message = self.message_record(
                message_id=getattr(item, "id", str(uuid.uuid4())),
                message_type=MessageType.REASONING,
                status=MessageStatus.COMPLETED,
                summary=summary,
            )
            self.send_delta_completed_event(
                message=message,
                message_type=MessageType.REASONING,
            )
            return

        if data_type == "ResponseOutputItemDoneEvent" and item_type == "ResponseFunctionToolCall":
            self.next_order()
            message_id = getattr(item, "id", str(uuid.uuid4()))
            call_id = getattr(item, "call_id", None)
            if call_id:
                self.tool_call_ids_by_call_id[call_id] = message_id
            message = self.message_record(
                message_id=message_id,
                message_type=MessageType.TOOL_CALL,
                status=MessageStatus.IN_PROGRESS,
                arguments=getattr(item, "arguments", None),
                tool_name=getattr(item, "name", None),
                call_id=call_id,
            )
            self.send_full_event(message=message, operation=OperationType.ADD)
            return

        if data_type == "ResponseOutputItemAddedEvent" and item_type == "ResponseOutputMessage":
            self.final_message_id = getattr(item, "id", None) or self.final_message_id
            self.send_message_marker(MarkerType.GENERATING_SUMMARY)
            return

        delta = getattr(data, "delta", None)
        if data_type == "ResponseTextDeltaEvent" and isinstance(delta, str) and delta:
            self.final_answer_content += delta
            if self.final_message_id is None:
                self.final_message_id = getattr(data, "item_id", None) or str(uuid.uuid4())
            if not self.final_answer_started:
                self.final_answer_started = True
                self.next_order()
                self.send_message_marker(MarkerType.USER_VISIBLE_TOKEN)
                self.send_delta_event(
                    message_id=self.final_message_id,
                    message_type=MessageType.ASSISTANT_MESSAGE,
                    operation=OperationType.ADD,
                    status=MessageStatus.IN_PROGRESS,
                    content=delta,
                    role=Role.ASSISTANT,
                )
            else:
                self.send_delta_event(
                    message_id=self.final_message_id,
                    message_type=MessageType.ASSISTANT_MESSAGE,
                    operation=OperationType.APPEND,
                    status=MessageStatus.IN_PROGRESS,
                    content=delta,
                    role=Role.ASSISTANT,
                )

    def finish(self) -> None:
        if self.final_message_id:
            message = self.message_record(
                message_id=self.final_message_id,
                message_type=MessageType.ASSISTANT_MESSAGE,
                status=MessageStatus.COMPLETED,
                role=Role.ASSISTANT,
                content=self.final_answer_content,
            )
            self.send_delta_completed_event(
                message=message,
                message_type=MessageType.ASSISTANT_MESSAGE,
            )
        self.send_message_marker(MarkerType.END_TURN)


async def stream_rich_agent_response(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    request_id: str,
    stream_context: dict[str, str],
    prompt: str,
    openai_api_key: str,
    user_id: str,
    is_staff: bool,
) -> None:
    from agents import Agent, ModelSettings, Runner, function_tool, set_default_openai_key
    from openai.types.shared import Reasoning

    @function_tool
    def check_agent_employee_access(reason: str) -> dict[str, Any]:
        """Demo access check tool for the streaming UI.

        Always call this once before the final answer. It returns a small
        policy-check result so the UI can render the tool-call lifecycle.
        """
        log(
            "agent_demo_tool_called",
            user_id=user_id,
            request_id=request_id,
            is_staff=is_staff,
        )
        return {
            "ok": True,
            "user_id": user_id,
            "is_staff": is_staff,
            "tool": "check_agent_employee_access",
            "reason": reason,
            "authorization": "demo_allow",
            "message": "Demo tool call completed. No live broker credentials were requested.",
        }

    set_default_openai_key(openai_api_key)
    agent = Agent(
        name="UserAgent",
        instructions=agent_instructions(),
        model=os.environ.get("AGENT_MODEL", DEFAULT_AGENT_MODEL),
        model_settings=ModelSettings(
            store=False,
            response_include=["reasoning.encrypted_content"],
            parallel_tool_calls=True,
            reasoning=Reasoning(
                effort=os.environ.get(
                    "AGENT_REASONING_EFFORT",
                    DEFAULT_AGENT_REASONING_EFFORT,
                ),
                summary="auto",
            ),
        ),
        tools=[check_agent_employee_access],
    )
    result = Runner.run_streamed(agent, input=prompt, max_turns=10)
    stream = WebSocketAgentStream(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        request_id=request_id,
        stream_context=stream_context,
    )

    async for event in result.stream_events():
        await stream.handle_stream_event(event)
    stream.finish()


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
    stream_context = stream_context_from_payload(
        payload=payload,
        request_id=request_id_value,
        user_id=human_user_id,
    )

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
            stream_rich_agent_response(
                connection_id=connection_id,
                domain_name=domain_name,
                stage=stage,
                request_id=request_id_value,
                stream_context=stream_context,
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
