import json
from types import SimpleNamespace

from broker_api.handlers import credentials
from broker_api.policy.schemas import AccessDecision


def _event(query):
    return {
        "httpMethod": "GET",
        "path": "/credentials",
        "queryStringParameters": query,
        "requestContext": {
            "requestId": "req-1",
            "identity": {"userArn": "arn:aws:sts::123:assumed-role/UserAgent/test"},
        },
    }


def test_handler_rejects_resource_param():
    result = credentials.handler(
        _event({"user_id": "u1", "reason": "support", "resource": "customer_data"}),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"] == "resource_not_allowed"


def test_handler_returns_403_when_policy_missing(monkeypatch):
    monkeypatch.setattr(credentials, "load_policy", lambda user_id: None)

    result = credentials.handler(
        _event({"user_id": "missing-user", "reason": "support"}),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 403
    assert json.loads(result["body"])["error"] == "no_policy_found"


def test_handler_returns_credentials_and_console_url_for_staff(monkeypatch):
    monkeypatch.setattr(credentials, "load_policy", lambda user_id: "Admin is admin.")
    monkeypatch.setattr(credentials, "get_openai_key", lambda: "sk-test")
    monkeypatch.setattr(credentials, "get_resource_catalog", lambda: {})
    monkeypatch.setattr(
        credentials,
        "approve_user_request",
        lambda **kwargs: AccessDecision(
            approved=True,
            reason="Admin policy update is allowed.",
            duration_seconds=900,
            grants=[
                {
                    "resource_key": "policy_table",
                    "actions": ["dynamodb:UpdateItem"],
                }
            ],
        ),
    )
    monkeypatch.setattr(
        credentials,
        "build_session_policy",
        lambda decision, catalog: {"Version": "2012-10-17", "Statement": []},
    )
    monkeypatch.setattr(
        credentials,
        "assume_scoped_role",
        lambda **kwargs: {
            "access_key_id": "AKIA",
            "secret_access_key": "secret",
            "session_token": "token",
            "expiration": "2026-04-29T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(
        credentials,
        "build_console_login_url",
        lambda creds: "https://signin.aws.amazon.com/federation?Action=login",
    )

    result = credentials.handler(
        _event(
            {
                "user_id": "admin-user",
                "reason": "Update employee policy.",
                "is_staff": "true",
            }
        ),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert body["credentials"]["access_key_id"] == "AKIA"
    assert body["console_login_url"].startswith("https://signin.aws.amazon.com")
