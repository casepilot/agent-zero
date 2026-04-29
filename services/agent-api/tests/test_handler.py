import json
from types import SimpleNamespace

from agent_api import handler


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
                "authorizer": {"user_id": "trusted-cognito-sub"},
            },
        },
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 200
    assert len(fake_lambda.invocations) == 1
    worker_payload = json.loads(fake_lambda.invocations[0]["Payload"].decode("utf-8"))
    assert worker_payload["user_id"] == "trusted-cognito-sub"
    assert worker_payload["payload"]["user_id"] == "attacker-controlled"


def test_worker_streams_broker_result(monkeypatch):
    sent_messages = []
    monkeypatch.setattr(handler, "get_openai_key", lambda: "sk-test")
    monkeypatch.setattr(
        handler,
        "call_credentials_endpoint",
        lambda **kwargs: (
            200,
            {"status": "approved", "decision": {"reason": "Allowed."}},
        ),
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
            "payload": {"requestId": "req-1", "reason": "Support case ABC-123"},
        },
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 200
    assert [message["type"] for message in sent_messages] == [
        "ack",
        "delta",
        "broker_result",
        "done",
    ]
    assert sent_messages[2]["broker_response"]["status"] == "approved"
