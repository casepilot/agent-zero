import pytest

from broker_api.data.resource_catalog import Resource
from broker_api.policy.build_session_policy import build_session_policy
from broker_api.policy.schemas import AccessDecision
from broker_api.policy.validate_decision import validate_decision


SUPPORT_POLICY = (
    "Employee One is a customer support employee. They may read customer_data "
    "for specific support requests. They must not access analytics_data."
)
ANALYST_POLICY = (
    "Dana is a company analyst. They may use analytics data for business "
    "reporting but should not get general customer data."
)
ADMIN_POLICY = (
    "Admin User is an administrator. They may read and write policy-table "
    "for policy management work."
)


def test_support_can_get_customer_data_read_access():
    decision = AccessDecision(
        approved=True,
        reason="Support case is specific and allowed.",
        duration_seconds=900,
        grants=[
            {
                "resource_key": "customer_data",
                "actions": ["dynamodb:GetItem", "dynamodb:Query"],
            }
        ],
    )

    validated = validate_decision(
        decision=decision,
        policy_text=SUPPORT_POLICY,
        reason="Investigate ticket ABC-123 for one customer.",
    )

    assert validated is decision


def test_support_cannot_get_analytics_data():
    decision = AccessDecision(
        approved=True,
        reason="Support wants analytics.",
        duration_seconds=900,
        grants=[{"resource_key": "analytics_data", "actions": ["dynamodb:Scan"]}],
    )

    with pytest.raises(ValueError, match="analytics_data"):
        validate_decision(
            decision=decision,
            policy_text=SUPPORT_POLICY,
            reason="Check company churn metrics.",
        )


def test_analyst_cannot_get_general_customer_data():
    decision = AccessDecision(
        approved=True,
        reason="Analyst wants customer data.",
        duration_seconds=900,
        grants=[{"resource_key": "customer_data", "actions": ["dynamodb:Scan"]}],
    )

    with pytest.raises(ValueError, match="customer_data"):
        validate_decision(
            decision=decision,
            policy_text=ANALYST_POLICY,
            reason="Scan customers for a company report.",
        )


def test_non_admin_cannot_write_policy_table():
    decision = AccessDecision(
        approved=True,
        reason="Support wants to edit a policy.",
        duration_seconds=900,
        grants=[
            {"resource_key": "policy_table", "actions": ["dynamodb:UpdateItem"]}
        ],
    )

    with pytest.raises(ValueError, match="admin"):
        validate_decision(
            decision=decision,
            policy_text=SUPPORT_POLICY,
            reason="Update another user's access policy.",
        )


def test_admin_can_write_policy_table():
    decision = AccessDecision(
        approved=True,
        reason="Admin needs to update a user policy.",
        duration_seconds=900,
        grants=[
            {"resource_key": "policy_table", "actions": ["dynamodb:UpdateItem"]}
        ],
    )

    validate_decision(
        decision=decision,
        policy_text=ADMIN_POLICY,
        reason="Update employee policy for a new role.",
    )


def test_schema_rejects_unknown_resource_and_excess_duration():
    with pytest.raises(Exception):
        AccessDecision(
            approved=True,
            reason="Invalid resource.",
            duration_seconds=7200,
            grants=[{"resource_key": "unknown", "actions": ["dynamodb:GetItem"]}],
        )


def test_session_policy_uses_exact_catalog_arns():
    catalog = {
        "customer_data": Resource(
            key="customer_data",
            table_name="customer_data",
            table_arn="arn:aws:dynamodb:ap-southeast-2:123:table/customer_data",
            purpose="customer data",
        )
    }
    decision = AccessDecision(
        approved=True,
        reason="Specific support request.",
        duration_seconds=900,
        grants=[{"resource_key": "customer_data", "actions": ["dynamodb:GetItem"]}],
    )

    policy = build_session_policy(decision, catalog)

    assert policy["Statement"] == [
        {
            "Effect": "Allow",
            "Action": ["dynamodb:GetItem"],
            "Resource": [
                "arn:aws:dynamodb:ap-southeast-2:123:table/customer_data",
                "arn:aws:dynamodb:ap-southeast-2:123:table/customer_data/index/*",
            ],
        }
    ]
