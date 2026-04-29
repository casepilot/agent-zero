import asyncio
import json
import os
import time
import uuid
from decimal import Decimal
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
RESOURCE_TABLE_ENV = {
    "users_table": "USERS_TABLE_NAME",
    "policy_table": "POLICY_TABLE_NAME",
    "customer_data": "CUSTOMER_DATA_TABLE_NAME",
    "analytics_data": "ANALYTICS_DATA_TABLE_NAME",
    "transactions": "TRANSACTIONS_TABLE_NAME",
    "account_data": "ACCOUNT_DATA_TABLE_NAME",
}
KNOWN_COGNITO_GROUPS = {"admin", "employee", "customer"}
RESOURCE_PURPOSES = {
    "users_table": "Principal directory for humans and agents.",
    "user_pool": "Cognito user pool for application users and groups.",
    "policy_table": "Free-text access policy store.",
    "customer_data": "Customer support records.",
    "analytics_data": "Aggregated company analytics.",
    "transactions": "Transaction records for company operations and reporting.",
    "account_data": "Account self-service records keyed by user_id.",
}


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


def resource_table_names() -> dict[str, str]:
    return {
        resource_key: os.environ.get(env_name, resource_key)
        for resource_key, env_name in RESOURCE_TABLE_ENV.items()
    }


def agent_instructions() -> str:
    resource_lines = "\n".join(
        f"- {resource_key}: DynamoDB table {table_name}. Purpose: {RESOURCE_PURPOSES[resource_key]}"
        for resource_key, table_name in resource_table_names().items()
    )

    return f"""You are UserAgent, an internal chat interface for company tasks.

You are the user's hands and feet. You do not know the user's access policy and
you do not decide authorization. AgentZero, the credentials broker, decides
whether a request is allowed.

Known resources:
{resource_lines}
- user_pool: Cognito user pool. Purpose: {RESOURCE_PURPOSES["user_pool"]}

Access request behavior:
- When the user asks to work with company or AWS data, use run_dynamodb_operation
  to attempt the requested operation against the most likely resource.
- If an AWS operation fails with an authorization error, ask the user for a
  clear business rationale if they have not already provided one.
- Then call request_aws_access with that rationale. If it is approved, retry the
  failed operation using the temporary credentials returned to you.
- If AgentZero denies access, stop. Tell the user you cannot complete the
  request because it is outside their scope. Do not reveal internal policy text.
- If required operation details are missing, ask a concise follow-up question.
- If the user asks to create an application user, use create_cognito_user after
  access has been approved. Required details are email and password; ask for
  missing details instead of guessing.
- Do not invent ticket IDs, resources, users, or reasons.
- Continue the loop until the user's task is complete or AgentZero denies it.
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


def decimal_safe(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: decimal_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [decimal_safe(child) for child in value]
    return value


def json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {key: json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [json_safe(child) for child in value]
    return value


def sanitize_broker_result(result: dict[str, Any]) -> dict[str, Any]:
    body = result.get("body") if isinstance(result.get("body"), dict) else {}
    sanitized_body = {
        key: value
        for key, value in body.items()
        if key not in {"credentials"}
    }
    return {
        "status_code": result.get("status_code"),
        "ok": result.get("ok"),
        "body": sanitized_body,
    }


def boto3_session_from_credentials(credentials: dict[str, Any] | None) -> boto3.Session:
    if not credentials:
        return boto3.Session()
    return boto3.Session(
        aws_access_key_id=credentials.get("access_key_id"),
        aws_secret_access_key=credentials.get("secret_access_key"),
        aws_session_token=credentials.get("session_token"),
        region_name=os.environ.get("AWS_REGION", "ap-southeast-2"),
    )


def run_dynamodb_call(
    *,
    resource_key: str,
    operation: str,
    credentials: dict[str, Any] | None = None,
    key: dict[str, Any] | None = None,
    item: dict[str, Any] | None = None,
    update_expression: str | None = None,
    expression_attribute_names: dict[str, str] | None = None,
    expression_attribute_values: dict[str, Any] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    table_names = resource_table_names()
    if resource_key not in table_names:
        return {
            "ok": False,
            "error": "unknown_resource",
            "message": f"Unknown resource_key: {resource_key}",
        }

    table = boto3_session_from_credentials(credentials).resource("dynamodb").Table(
        table_names[resource_key]
    )
    operation_name = operation.lower().strip()
    try:
        if operation_name == "get_item":
            response = table.get_item(Key=decimal_safe(key or {}))
        elif operation_name == "scan":
            kwargs = {}
            if limit:
                kwargs["Limit"] = max(1, min(int(limit), 25))
            response = table.scan(**kwargs)
        elif operation_name == "put_item":
            response = table.put_item(Item=decimal_safe(item or {}))
        elif operation_name == "delete_item":
            response = table.delete_item(Key=decimal_safe(key or {}))
        elif operation_name == "update_item":
            kwargs = {
                "Key": decimal_safe(key or {}),
                "UpdateExpression": update_expression,
                "ReturnValues": "ALL_NEW",
            }
            if expression_attribute_names:
                kwargs["ExpressionAttributeNames"] = expression_attribute_names
            if expression_attribute_values:
                kwargs["ExpressionAttributeValues"] = decimal_safe(
                    expression_attribute_values
                )
            if not update_expression:
                return {
                    "ok": False,
                    "error": "missing_update_expression",
                    "message": "update_expression is required for update_item.",
                }
            response = table.update_item(**kwargs)
        else:
            return {
                "ok": False,
                "error": "unsupported_operation",
                "message": (
                    "operation must be one of get_item, scan, put_item, "
                    "update_item, delete_item."
                ),
            }
    except ClientError as error:
        error_info = error.response.get("Error", {})
        return {
            "ok": False,
            "error": error_info.get("Code", type(error).__name__),
            "message": error_info.get("Message", str(error)),
            "resource_key": resource_key,
            "operation": operation_name,
        }
    except Exception as error:
        return {
            "ok": False,
            "error": type(error).__name__,
            "message": str(error),
            "resource_key": resource_key,
            "operation": operation_name,
        }

    return {
        "ok": True,
        "resource_key": resource_key,
        "operation": operation_name,
        "response": json_safe(response),
    }


def create_cognito_user_record(
    *,
    email: str,
    password: str,
    name: str | None,
    group: str,
    role: str | None,
    is_human: bool,
    credentials: dict[str, Any] | None = None,
) -> dict[str, Any]:
    email_value = email.strip().lower()
    group_value = group.strip().lower()
    if not email_value or not password:
        return {
            "ok": False,
            "error": "missing_required_fields",
            "message": "email and password are required.",
        }
    if group_value not in KNOWN_COGNITO_GROUPS:
        return {
            "ok": False,
            "error": "invalid_group",
            "message": f"group must be one of {sorted(KNOWN_COGNITO_GROUPS)}.",
        }

    session = boto3_session_from_credentials(credentials)
    cognito = session.client("cognito-idp")
    dynamodb = session.resource("dynamodb")
    user_pool_id = os.environ["USER_POOL_ID"]
    display_name = (name or email_value).strip()
    try:
        try:
            cognito.admin_create_user(
                UserPoolId=user_pool_id,
                Username=email_value,
                UserAttributes=[
                    {"Name": "email", "Value": email_value},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "name", "Value": display_name},
                ],
                TemporaryPassword=password,
                MessageAction="SUPPRESS",
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "UsernameExistsException":
                raise
            cognito.admin_update_user_attributes(
                UserPoolId=user_pool_id,
                Username=email_value,
                UserAttributes=[
                    {"Name": "email", "Value": email_value},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "name", "Value": display_name},
                ],
            )

        cognito.admin_set_user_password(
            UserPoolId=user_pool_id,
            Username=email_value,
            Password=password,
            Permanent=True,
        )
        cognito.admin_add_user_to_group(
            UserPoolId=user_pool_id,
            Username=email_value,
            GroupName=group_value,
        )
        response = cognito.admin_get_user(
            UserPoolId=user_pool_id,
            Username=email_value,
        )
        attributes = {
            attribute["Name"]: attribute["Value"]
            for attribute in response.get("UserAttributes", [])
        }
        user_id = attributes.get("sub")
        if not user_id:
            raise RuntimeError("Cognito user did not include sub")

        item = {
            "user_id": user_id,
            "username": email_value,
            "name": display_name,
            "role": (role or group_value).strip().lower(),
            "is_human": bool(is_human),
        }
        dynamodb.Table(os.environ["USERS_TABLE_NAME"]).put_item(Item=item)
    except ClientError as error:
        error_info = error.response.get("Error", {})
        return {
            "ok": False,
            "error": error_info.get("Code", type(error).__name__),
            "message": error_info.get("Message", str(error)),
            "email": email_value,
            "group": group_value,
        }
    except Exception as error:
        return {
            "ok": False,
            "error": type(error).__name__,
            "message": str(error),
            "email": email_value,
            "group": group_value,
        }

    return {
        "ok": True,
        "user_id": user_id,
        "username": email_value,
        "name": display_name,
        "group": group_value,
        "role": item["role"],
        "is_human": item["is_human"],
    }


def stream_context_from_payload(
    *,
    payload: dict[str, Any],
    request_id: str,
) -> dict[str, str]:
    thread_id = payload.get("threadId")
    parent_id = payload.get("parentId") or payload.get("turnId")
    return {
        "threadId": thread_id if isinstance(thread_id, str) and thread_id else request_id,
        "parentId": parent_id if isinstance(parent_id, str) and parent_id else request_id,
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
                "threadId": self.thread_id,
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

    def send_tool_result(
        self,
        *,
        tool_name: str,
        status: MessageStatus,
        output: dict[str, Any],
    ) -> bool:
        self.next_order()
        message_id = f"tool-result-{uuid.uuid4()}"
        message = self.message_record(
            message_id=message_id,
            message_type=MessageType.TOOL_RESULT,
            status=status,
            order=self.order,
            tool_name=tool_name,
            output=json.dumps(output, default=str),
        )
        return self.send_full_event(message=message, operation=OperationType.ADD)

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

        if data_type == "ResponseReasoningSummaryDeltaEvent":
            item_id = getattr(data, "item_id", str(uuid.uuid4()))
            if not self.reasoning_active:
                self.reasoning_active = True
                self.next_order()
                self.send_delta_event(
                    message_id=item_id,
                    message_type=MessageType.REASONING,
                    operation=OperationType.ADD,
                    status=MessageStatus.IN_PROGRESS,
                )
            delta = getattr(data, "delta", "")
            content = delta if isinstance(delta, str) else json.dumps(delta, default=str)
            self.send_delta_event(
                message_id=item_id,
                message_type=MessageType.REASONING,
                operation=OperationType.APPEND,
                status=MessageStatus.IN_PROGRESS,
                content=content,
            )
            return

        if data_type == "ResponseReasoningSummaryDoneEvent" and self.reasoning_active:
            self.reasoning_active = False
            message = self.message_record(
                message_id=getattr(data, "item_id", str(uuid.uuid4())),
                message_type=MessageType.REASONING,
                status=MessageStatus.COMPLETED,
                summary=[getattr(data, "text", "")],
            )
            self.send_delta_completed_event(
                message=message,
                message_type=MessageType.REASONING,
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

    stream = WebSocketAgentStream(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        request_id=request_id,
        stream_context=stream_context,
    )
    turn_credentials: dict[str, Any] | None = None

    @function_tool
    def list_known_resources() -> dict[str, Any]:
        """List the company resources this chat agent can operate against."""
        result = {
            "ok": True,
            "resources": [
                {
                    "resource_key": resource_key,
                    "table_name": table_name,
                    "purpose": RESOURCE_PURPOSES[resource_key],
                }
                for resource_key, table_name in resource_table_names().items()
            ],
        }
        stream.send_tool_result(
            tool_name="list_known_resources",
            status=MessageStatus.COMPLETED,
            output=result,
        )
        return result

    @function_tool
    def request_aws_access(reason: str) -> dict[str, Any]:
        """Request just-in-time AWS access from AgentZero.

        Use this only after the user gives a clear business reason. It returns
        an approval review and stores scoped STS credentials internally for
        later tool retries when approved.
        """
        nonlocal turn_credentials
        if not isinstance(reason, str) or not reason.strip():
            result = {
                "ok": False,
                "status_code": 400,
                "body": {
                    "error": "missing_reason",
                    "message": "A clear business reason is required.",
                },
            }
            stream.send_tool_result(
                tool_name="request_aws_access",
                status=MessageStatus.ERROR,
                output=result,
            )
            return result

        broker_result = call_broker_credentials(
            user_id=user_id,
            reason=reason.strip(),
            is_staff=is_staff,
        )
        body = broker_result.get("body") if isinstance(broker_result.get("body"), dict) else {}
        credentials = body.get("credentials")
        if broker_result["ok"] and isinstance(credentials, dict):
            turn_credentials = credentials
        sanitized = sanitize_broker_result(broker_result)
        stream.send_tool_result(
            tool_name="request_aws_access",
            status=MessageStatus.COMPLETED if broker_result["ok"] else MessageStatus.ERROR,
            output=sanitized,
        )
        return sanitized

    @function_tool
    def run_dynamodb_operation(
        resource_key: str,
        operation: str,
        key: dict[str, Any] | None = None,
        item: dict[str, Any] | None = None,
        update_expression: str | None = None,
        expression_attribute_names: dict[str, str] | None = None,
        expression_attribute_values: dict[str, Any] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Run a constrained DynamoDB operation for the user.

        Use this for get_item, scan, put_item, update_item, and delete_item
        against known resource_key values only. The tool first uses the
        worker's current AWS credentials. After request_aws_access approves
        temporary credentials, this tool uses those credentials on retry. For
        account_data get_item requests, omit key to use the signed-in user's
        own account row.
        """
        operation_name = operation.lower().strip()
        effective_key = key
        if resource_key == "account_data" and operation_name == "get_item" and not key:
            effective_key = {"user_id": user_id}
        result = run_dynamodb_call(
            resource_key=resource_key,
            operation=operation_name,
            credentials=turn_credentials,
            key=effective_key,
            item=item,
            update_expression=update_expression,
            expression_attribute_names=expression_attribute_names,
            expression_attribute_values=expression_attribute_values,
            limit=limit,
        )
        stream.send_tool_result(
            tool_name="run_dynamodb_operation",
            status=MessageStatus.COMPLETED if result["ok"] else MessageStatus.ERROR,
            output=result,
        )
        return result

    @function_tool
    def write_user_policy(
        target_user_id: str,
        policy_text: str,
        operation: str = "put_item",
    ) -> dict[str, Any]:
        """Create, replace, or delete a free-text policy for a target user_id.

        target_user_id is required. If the user has not provided one, ask a
        follow-up question or list users first. Authorization is still decided
        by AgentZero through the credentials loop.
        """
        if not target_user_id.strip():
            result = {
                "ok": False,
                "error": "missing_target_user_id",
                "message": "target_user_id is required.",
            }
            stream.send_tool_result(
                tool_name="write_user_policy",
                status=MessageStatus.ERROR,
                output=result,
            )
            return result
        if operation == "delete_item":
            result = run_dynamodb_call(
                resource_key="policy_table",
                operation="delete_item",
                credentials=turn_credentials,
                key={"user_id": target_user_id},
            )
        else:
            result = run_dynamodb_call(
                resource_key="policy_table",
                operation="put_item",
                credentials=turn_credentials,
                item={"user_id": target_user_id, "policy": policy_text},
            )
        stream.send_tool_result(
            tool_name="write_user_policy",
            status=MessageStatus.COMPLETED if result["ok"] else MessageStatus.ERROR,
            output=result,
        )
        return result

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
        tools=[
            list_known_resources,
            run_dynamodb_operation,
            request_aws_access,
            write_user_policy,
        ],
    )
    result = Runner.run_streamed(agent, input=prompt, max_turns=10)

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
