import json
import asyncio
from types import SimpleNamespace

from agent_api import handler


def test_agent_instructions_include_policy_table_context(monkeypatch):
    monkeypatch.setenv("POLICY_TABLE_NAME", "policy-table")
    monkeypatch.setenv(
        "POLICY_TABLE_ARN",
        "arn:aws:dynamodb:ap-southeast-2:338375260114:table/policy-table",
    )

    instructions = handler.agent_instructions()

    assert "DynamoDB table name: policy-table" in instructions
    assert (
        "arn:aws:dynamodb:ap-southeast-2:338375260114:table/policy-table"
        in instructions
    )
    assert "Ask for the target user_id if it is missing" in instructions
    assert "James Brown is an IT support engineer" in instructions
    assert "aws dynamodb put-item --table-name policy-table" in instructions
    assert '"user_id": {"S": "<target user id>"}' in instructions


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
            "tenantId": "tenant-1",
            "caseId": "case-1",
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
        name = "check_agent_employee_access"
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
        "check_agent_employee_access"
    )
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
