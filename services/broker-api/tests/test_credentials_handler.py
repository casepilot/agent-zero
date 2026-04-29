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
        _event({"user_id": "u1", "reason": "support", "resource": "bank_customer_profiles"}),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 400
    assert json.loads(result["body"])["error"] == "resource_not_allowed"


def test_handler_returns_403_when_policy_missing(monkeypatch):
    monkeypatch.setattr(credentials, "load_policy", lambda user_id: None)
    monkeypatch.setattr(credentials, "load_user_profile", lambda user_id: {})
    audit_records = []
    monkeypatch.setattr(
        credentials,
        "put_audit_record",
        lambda item, **kwargs: audit_records.append(item) or True,
    )

    result = credentials.handler(
        _event({"user_id": "missing-user", "reason": "support"}),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 403
    assert json.loads(result["body"])["error"] == "no_policy_found"
    assert audit_records[-1]["status"] == "denied"
    assert audit_records[-1]["error_code"] == "no_policy_found"
    assert audit_records[-1]["user_id"] == "missing-user"


def test_handler_logs_llm_denial(monkeypatch):
    monkeypatch.setattr(credentials, "load_policy", lambda user_id: "Support only.")
    monkeypatch.setattr(
        credentials,
        "load_user_profile",
        lambda user_id: {"role": "employee", "is_human": True, "name": "User"},
    )
    monkeypatch.setattr(credentials, "get_openai_key", lambda: "sk-test")
    monkeypatch.setattr(credentials, "get_resource_catalog", lambda: {})
    monkeypatch.setattr(
        credentials,
        "approve_user_request",
        lambda **kwargs: AccessDecision(
            approved=False,
            reason="Request does not match policy.",
            risk="high",
            authorization="low",
            duration_seconds=900,
            grants=[],
        ),
    )
    audit_records = []
    monkeypatch.setattr(
        credentials,
        "put_audit_record",
        lambda item, **kwargs: audit_records.append(item) or True,
    )

    result = credentials.handler(
        _event({"user_id": "employee-user", "reason": "Delete all records."}),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    body = json.loads(result["body"])
    assert result["statusCode"] == 403
    assert body["error"] == "access_denied"
    assert audit_records[-1]["status"] == "denied"
    assert audit_records[-1]["error_code"] == "access_denied"
    assert audit_records[-1]["decision"]["approved"] is False
    assert audit_records[-1]["principal_type"] == "human"


def test_handler_returns_credentials_and_console_url_for_staff(monkeypatch):
    monkeypatch.setenv(
        "BROKER_CREDENTIALS_ROLE_ARN",
        "arn:aws:iam::123:role/BrokerCredentialsRole",
    )
    monkeypatch.setattr(credentials, "load_policy", lambda user_id: "Admin is admin.")
    monkeypatch.setattr(
        credentials,
        "load_user_profile",
        lambda user_id: {
            "role": "admin",
            "is_human": True,
            "name": "Admin User",
            "username": "admin@example.com",
        },
    )
    monkeypatch.setattr(credentials, "load_user_role", lambda user_id: "admin")
    monkeypatch.setattr(credentials, "get_openai_key", lambda: "sk-test")
    monkeypatch.setattr(credentials, "get_resource_catalog", lambda: {})
    monkeypatch.setattr(
        credentials,
        "approve_user_request",
        lambda **kwargs: AccessDecision(
            approved=True,
            reason="Admin policy update is allowed.",
            risk="medium",
            authorization="high",
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
        lambda decision, catalog, **kwargs: {"Version": "2012-10-17", "Statement": []},
    )
    monkeypatch.setattr(
        credentials,
        "assume_scoped_role",
        lambda **kwargs: {
            "access_key_id": "AKIA",
            "secret_access_key": "secret",
            "session_token": "token",
            "expiration": "2026-04-29T00:00:00+00:00",
            "assumed_role_arn": "arn:aws:sts::123:assumed-role/Broker/session",
            "assumed_role_id": "ARO123:session",
        },
    )
    monkeypatch.setattr(
        credentials,
        "build_console_login_url",
        lambda creds: "https://signin.aws.amazon.com/federation?Action=login",
    )
    audit_records = []
    monkeypatch.setattr(
        credentials,
        "put_audit_record",
        lambda item, **kwargs: audit_records.append(item) or True,
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
    assert body["decision"]["risk"] == "medium"
    assert body["decision"]["authorization"] == "high"
    assert body["console_login_url"].startswith("https://signin.aws.amazon.com")
    assert [record["status"] for record in audit_records] == [
        "approved_pending_sts",
        "approved",
    ]
    final_audit = audit_records[-1]
    assert final_audit["target_role_arn"] == "arn:aws:iam::123:role/BrokerCredentialsRole"
    assert final_audit["role_session_name"].startswith("agent-zero-admin-user-")
    assert final_audit["assumed_role_arn"] == "arn:aws:sts::123:assumed-role/Broker/session"
    assert "credentials" not in final_audit
    assert "console_login_url" not in final_audit
    assert "secret_access_key" not in json.dumps(final_audit)


def test_handler_blocks_approval_when_required_audit_write_fails(monkeypatch):
    monkeypatch.setenv(
        "BROKER_CREDENTIALS_ROLE_ARN",
        "arn:aws:iam::123:role/BrokerCredentialsRole",
    )
    monkeypatch.setattr(credentials, "load_policy", lambda user_id: "Admin is admin.")
    monkeypatch.setattr(credentials, "load_user_profile", lambda user_id: {})
    monkeypatch.setattr(credentials, "load_user_role", lambda user_id: "admin")
    monkeypatch.setattr(credentials, "get_openai_key", lambda: "sk-test")
    monkeypatch.setattr(credentials, "get_resource_catalog", lambda: {})
    monkeypatch.setattr(
        credentials,
        "approve_user_request",
        lambda **kwargs: AccessDecision(
            approved=True,
            reason="Allowed.",
            risk="medium",
            authorization="high",
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
        lambda decision, catalog, **kwargs: {"Version": "2012-10-17", "Statement": []},
    )
    assume_called = False

    def fail_audit(item, **kwargs):
        if kwargs.get("required"):
            raise RuntimeError("audit table unavailable")
        return True

    def assume(**kwargs):
        nonlocal assume_called
        assume_called = True
        return {}

    monkeypatch.setattr(credentials, "put_audit_record", fail_audit)
    monkeypatch.setattr(credentials, "assume_scoped_role", assume)

    result = credentials.handler(
        _event({"user_id": "admin-user", "reason": "Update employee policy."}),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 500
    assert json.loads(result["body"])["error"] == "audit_log_failed"
    assert assume_called is False


def test_handler_logs_sts_failure(monkeypatch):
    monkeypatch.setenv(
        "BROKER_CREDENTIALS_ROLE_ARN",
        "arn:aws:iam::123:role/BrokerCredentialsRole",
    )
    monkeypatch.setattr(credentials, "load_policy", lambda user_id: "Admin is admin.")
    monkeypatch.setattr(credentials, "load_user_profile", lambda user_id: {})
    monkeypatch.setattr(credentials, "load_user_role", lambda user_id: "admin")
    monkeypatch.setattr(credentials, "get_openai_key", lambda: "sk-test")
    monkeypatch.setattr(credentials, "get_resource_catalog", lambda: {})
    monkeypatch.setattr(
        credentials,
        "approve_user_request",
        lambda **kwargs: AccessDecision(
            approved=True,
            reason="Allowed.",
            risk="medium",
            authorization="high",
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
        lambda decision, catalog, **kwargs: {"Version": "2012-10-17", "Statement": []},
    )
    monkeypatch.setattr(
        credentials,
        "assume_scoped_role",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("sts unavailable")),
    )
    audit_records = []
    monkeypatch.setattr(
        credentials,
        "put_audit_record",
        lambda item, **kwargs: audit_records.append(item) or True,
    )

    result = credentials.handler(
        _event({"user_id": "admin-user", "reason": "Update employee policy."}),
        SimpleNamespace(aws_request_id="aws-1"),
    )

    assert result["statusCode"] == 500
    assert json.loads(result["body"])["error"] == "credential_issue_failed"
    assert [record["status"] for record in audit_records] == [
        "approved_pending_sts",
        "error",
    ]
    assert audit_records[-1]["error_code"] == "credential_issue_failed"
