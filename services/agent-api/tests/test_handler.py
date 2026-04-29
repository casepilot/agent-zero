import json
import asyncio
from types import SimpleNamespace

from agent_api import handler


def test_agent_instructions_keep_authorization_in_broker(monkeypatch):
    monkeypatch.setenv("POLICY_TABLE_NAME", "policy-table")
    monkeypatch.setenv("TRANSACTIONS_TABLE_NAME", "transactions")

    instructions = handler.agent_instructions()

    assert "policy_table: DynamoDB table policy-table" in instructions
    assert "transactions: DynamoDB table transactions" in instructions
    assert "you do not decide authorization" in instructions
    assert "credentials broker, decides" in instructions
    assert "James Brown is an IT support engineer" not in instructions
    assert "administrator" not in instructions.lower()
    assert "analyst" not in instructions.lower()


class FakeLambdaClient:
    def __init__(self):
        self.invocations = []

    def invoke(self, **kwargs):
        self.invocations.append(kwargs)
        return {"StatusCode": 202}


def test_route_handler_invokes_worker_with_authorizer_user(monkeypatch):
    fake_lambda = FakeLambdaClient()
    monkeypatch.setenv("AGENT_WORKER_FUNCTION_NAME", "worker-name")
    monkeypatch.setattr(handler, "get_lambda_client", lambda: fake_lambda)

    result = handler.route_handler(
        {
            "body": json.dumps(
                {
                    "requestId": "req-1",
                    "reason": "Support case ABC-123",
                    "user_id": "attacker-controlled",
                }
            ),
            "requestContext": {
                "routeKey": "requestAccess",
                "connectionId": "conn-1",
                "domainName": "example.execute-api.ap-southeast-2.amazonaws.com",
                "stage": "prod",
                "requestId": "gateway-req-1",
                "authorizer": {
                    "user_id": "trusted-cognito-sub",
                    "groups": "employee",
                },
            },
        },
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 200
    assert len(fake_lambda.invocations) == 1
    worker_payload = json.loads(fake_lambda.invocations[0]["Payload"].decode("utf-8"))
    assert worker_payload["user_id"] == "trusted-cognito-sub"
    assert worker_payload["groups"] == "employee"
    assert worker_payload["payload"]["user_id"] == "attacker-controlled"


def test_worker_streams_agent_result(monkeypatch):
    sent_messages = []
    monkeypatch.setattr(handler, "get_openai_key", lambda: "sk-test")

    async def fake_stream_rich_agent_response(**kwargs):
        assert kwargs["user_id"] == "trusted-cognito-sub"
        assert kwargs["is_staff"] is True
        stream = handler.WebSocketAgentStream(
            connection_id=kwargs["connection_id"],
            domain_name=kwargs["domain_name"],
            stage=kwargs["stage"],
            request_id=kwargs["request_id"],
            stream_context=kwargs["stream_context"],
        )
        stream.send_message_marker(handler.MarkerType.COT)
        stream.send_delta_event(
            message_id="msg-1",
            message_type=handler.MessageType.ASSISTANT_MESSAGE,
            operation=handler.OperationType.ADD,
            status=handler.MessageStatus.IN_PROGRESS,
            content="Once",
            role=handler.Role.ASSISTANT,
        )
        stream.send_message_marker(handler.MarkerType.END_TURN)

    monkeypatch.setattr(
        handler,
        "stream_rich_agent_response",
        fake_stream_rich_agent_response,
    )
    monkeypatch.setattr(
        handler,
        "send_ws_message",
        lambda **kwargs: sent_messages.append(kwargs["payload"]) or True,
    )

    result = handler.worker_handler(
        {
            "connection_id": "conn-1",
            "domain_name": "example.execute-api.ap-southeast-2.amazonaws.com",
            "stage": "prod",
            "user_id": "trusted-cognito-sub",
            "groups": "employee",
            "payload": {
                "requestId": "req-1",
                "threadId": "thread-1",
                "parentId": "turn-1",
                "message": "tell a story about ducks",
            },
        },
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 200
    assert [message["type"] for message in sent_messages] == [
        "ack",
        "stream",
        "stream",
        "stream",
        "done",
    ]
    assert sent_messages[1]["streamType"] == "message_marker"
    assert sent_messages[1]["data"][0]["marker"] == "cot_token"
    assert sent_messages[2]["streamType"] == "delta"
    assert sent_messages[2]["data"][0]["content"] == "Once"
    assert sent_messages[3]["data"][0]["marker"] == "end_turn"


def test_stream_manager_maps_reasoning_tool_and_answer_events(monkeypatch):
    sent_messages = []
    monkeypatch.setattr(
        handler,
        "send_ws_message",
        lambda **kwargs: sent_messages.append(kwargs["payload"]) or True,
    )
    stream = handler.WebSocketAgentStream(
        connection_id="conn-1",
        domain_name="example.execute-api.ap-southeast-2.amazonaws.com",
        stage="prod",
        request_id="req-1",
        stream_context={
            "threadId": "thread-1",
            "parentId": "turn-1",
        },
    )

    class ResponseReasoningSummaryPartAddedEvent:
        item_id = "reasoning-1"

    class ResponseReasoningSummaryTextDeltaEvent:
        item_id = "reasoning-1"
        delta = "Checking policy. "

    class SummaryPart:
        text = "Checking policy."

    class ResponseReasoningItem:
        id = "reasoning-1"
        summary = [SummaryPart()]

    class ResponseOutputItemDoneEvent:
        def __init__(self, item):
            self.item = item

    class ResponseFunctionToolCall:
        id = "tool-1"
        name = "run_dynamodb_operation"
        arguments = '{"reason":"demo"}'
        call_id = "call-1"

    class ResponseOutputMessage:
        id = "assistant-1"

    class ResponseOutputItemAddedEvent:
        def __init__(self, item):
            self.item = item

    class ResponseTextDeltaEvent:
        item_id = "assistant-1"

        def __init__(self, delta):
            self.delta = delta

    class ToolCallOutputItem:
        raw_item = {"call_id": "call-1"}

    async def run_events():
        await stream.handle_stream_event(SimpleNamespace(type="agent_updated_stream_event"))
        await stream.handle_stream_event(
            SimpleNamespace(type="raw_response_event", data=ResponseReasoningSummaryPartAddedEvent())
        )
        await stream.handle_stream_event(
            SimpleNamespace(type="raw_response_event", data=ResponseReasoningSummaryTextDeltaEvent())
        )
        await stream.handle_stream_event(
            SimpleNamespace(type="raw_response_event", data=ResponseOutputItemDoneEvent(ResponseReasoningItem()))
        )
        await stream.handle_stream_event(
            SimpleNamespace(type="raw_response_event", data=ResponseOutputItemDoneEvent(ResponseFunctionToolCall()))
        )
        await stream.handle_stream_event(
            SimpleNamespace(type="run_item_stream_event", item=ToolCallOutputItem())
        )
        await stream.handle_stream_event(
            SimpleNamespace(type="raw_response_event", data=ResponseOutputItemAddedEvent(ResponseOutputMessage()))
        )
        await stream.handle_stream_event(
            SimpleNamespace(type="raw_response_event", data=ResponseTextDeltaEvent("Hello"))
        )
        await stream.handle_stream_event(
            SimpleNamespace(type="raw_response_event", data=ResponseTextDeltaEvent(" world"))
        )
        stream.finish()

    asyncio.run(run_events())

    markers = [
        message["data"][0]["marker"]
        for message in sent_messages
        if message["streamType"] == "message_marker"
    ]
    assert markers == [
        "cot_token",
        "generating_summary",
        "user_visible_token",
        "end_turn",
    ]
    stream_events = [message for message in sent_messages if message["streamType"] == "delta"]
    assert any(
        event["data"][0].get("type") == "reasoning"
        and event["data"][0].get("operation") == "append"
        and event["data"][0].get("content") == "Checking policy. "
        for event in stream_events
    )
    assert any(
        event["data"][0].get("type") == "tool_call"
        and event["data"][0].get("operation") == "replace"
        and event["data"][0].get("status") == "completed"
        for event in stream_events
    )
    assert any(
        event["data"][0].get("type") == "assistant_message"
        and event["data"][0].get("operation") == "append"
        and event["data"][0].get("content") == " world"
        for event in stream_events
    )
    completed_events = [
        message
        for message in sent_messages
        if message["streamType"] == "completed_message"
    ]
    assert completed_events[0]["data"][0]["message"]["data"]["tool_name"] == (
        "run_dynamodb_operation"
    )
    assert "tenantId" not in completed_events[0]["data"][0]["message"]
    assert "caseId" not in completed_events[0]["data"][0]["message"]
    assert [message["sequenceId"] for message in sent_messages] == list(
        range(1, len(sent_messages) + 1)
    )


def test_worker_returns_error_when_prompt_missing(monkeypatch):
    sent_messages = []
    monkeypatch.setattr(
        handler,
        "send_ws_message",
        lambda **kwargs: sent_messages.append(kwargs["payload"]) or True,
    )

    result = handler.worker_handler(
        {
            "connection_id": "conn-1",
            "domain_name": "example.execute-api.ap-southeast-2.amazonaws.com",
            "stage": "prod",
            "user_id": "trusted-cognito-sub",
            "payload": {"requestId": "req-1"},
        },
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 400
    assert [message["type"] for message in sent_messages] == ["ack", "error"]
    assert sent_messages[1]["error"] == "invalid_request"
    assert "message, prompt, or reason" in sent_messages[1]["missing"]


def test_worker_returns_error_when_request_id_missing(monkeypatch):
    sent_messages = []
    monkeypatch.setattr(
        handler,
        "send_ws_message",
        lambda **kwargs: sent_messages.append(kwargs["payload"]) or True,
    )

    result = handler.worker_handler(
        {
            "connection_id": "conn-1",
            "domain_name": "example.execute-api.ap-southeast-2.amazonaws.com",
            "stage": "prod",
            "user_id": "trusted-cognito-sub",
            "payload": {"message": "I need customer support access for ticket IT-123"},
        },
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 400
    assert [message["type"] for message in sent_messages] == ["ack", "error"]
    assert sent_messages[1]["error"] == "invalid_request"
    assert sent_messages[1]["missing"] == ["requestId"]


def test_staff_status_comes_from_cognito_groups():
    assert handler.is_staff_from_groups({"employee"}) is True
    assert handler.is_staff_from_groups({"admin"}) is True
    assert handler.is_staff_from_groups({"customer"}) is False


def test_call_broker_credentials_uses_expected_query(monkeypatch):
    captured = {}
    monkeypatch.setenv(
        "CREDENTIALS_URL",
        "https://broker.example.com/prod/credentials",
    )

    def fake_signed_get_json(url):
        captured["url"] = url
        return 200, {"status": "approved"}

    monkeypatch.setattr(handler, "signed_get_json", fake_signed_get_json)

    result = handler.call_broker_credentials(
        user_id="trusted-cognito-sub",
        reason="Support ticket IT-123 needs customer authorisation check",
        is_staff=True,
    )

    assert result == {
        "status_code": 200,
        "ok": True,
        "body": {"status": "approved"},
    }
    assert "user_id=trusted-cognito-sub" in captured["url"]
    assert "is_staff=true" in captured["url"]
    assert "reason=Support+ticket+IT-123" in captured["url"]
    assert "resource=" not in captured["url"]


def test_sanitize_broker_result_removes_raw_credentials():
    result = handler.sanitize_broker_result(
        {
            "status_code": 200,
            "ok": True,
            "body": {
                "decision": {"risk": "low", "authorization": "high"},
                "console_login_url": "https://signin.aws.amazon.com/federation",
                "credentials": {
                    "access_key_id": "AKIA",
                    "secret_access_key": "secret",
                    "session_token": "token",
                },
            },
        }
    )

    assert result["body"]["decision"]["risk"] == "low"
    assert "console_login_url" in result["body"]
    assert "credentials" not in result["body"]


def test_stream_manager_can_send_tool_result(monkeypatch):
    sent_messages = []
    monkeypatch.setattr(
        handler,
        "send_ws_message",
        lambda **kwargs: sent_messages.append(kwargs["payload"]) or True,
    )
    stream = handler.WebSocketAgentStream(
        connection_id="conn-1",
        domain_name="example.execute-api.ap-southeast-2.amazonaws.com",
        stage="prod",
        request_id="req-1",
        stream_context={"threadId": "thread-1", "parentId": "turn-1"},
    )

    stream.send_tool_result(
        tool_name="run_dynamodb_operation",
        status=handler.MessageStatus.ERROR,
        output={"ok": False, "error": "AccessDeniedException"},
    )

    message = sent_messages[0]["data"][0]["message"]
    assert sent_messages[0]["streamType"] == "completed_message"
    assert message["data"]["type"] == "tool_result"
    assert message["data"]["status"] == "error"
    assert message["data"]["tool_name"] == "run_dynamodb_operation"
    assert "AccessDeniedException" in message["data"]["output"]


def test_run_dynamodb_call_returns_access_denied(monkeypatch):
    from botocore.exceptions import ClientError

    class FakeTable:
        def scan(self, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": "not authorized",
                    }
                },
                "Scan",
            )

    class FakeResource:
        def Table(self, name):
            assert name == "customer_data"
            return FakeTable()

    class FakeSession:
        def resource(self, service_name):
            assert service_name == "dynamodb"
            return FakeResource()

    monkeypatch.setenv("CUSTOMER_DATA_TABLE_NAME", "customer_data")
    monkeypatch.setattr(handler, "boto3_session_from_credentials", lambda creds: FakeSession())

    result = handler.run_dynamodb_call(
        resource_key="customer_data",
        operation="scan",
    )

    assert result["ok"] is False
    assert result["error"] == "AccessDeniedException"
