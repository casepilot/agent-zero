import pytest

from broker_api.data.resource_catalog import Resource
from broker_api.policy.build_session_policy import build_session_policy
from broker_api.policy.schemas import AccessDecision
from broker_api.policy.validate_decision import validate_decision


SUPPORT_POLICY = (
    "Employee One is an IT support engineer. Their job is to investigate "
    "assigned IT support tickets, customer authorisation problems, account "
    "access issues, and operational incidents."
)
ANALYST_POLICY = (
    "Dana is a company analyst. They may use analytics data for business "
    "reporting but should not get general customer data."
)
ADMIN_POLICY = (
    "Admin User is an administrator. They may read and write policy-table "
    "for policy management work."
)
HR_POLICY = (
    "Helen works in human resources. They create employee accounts and maintain "
    "basic user records for onboarding."
)


def test_support_can_get_bank_customer_profiles_read_access():
    decision = AccessDecision(
        approved=True,
        reason="Support case is specific and allowed.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[
            {
                "resource_key": "bank_customer_profiles",
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


def test_external_customer_cannot_get_bank_operational_metrics():
    decision = AccessDecision(
        approved=True,
        reason="Customer wants analytics.",
        risk="high",
        authorization="low",
        duration_seconds=900,
        grants=[{"resource_key": "bank_operational_metrics", "actions": ["dynamodb:Scan"]}],
    )

    with pytest.raises(ValueError, match="bank_operational_metrics"):
        validate_decision(
            decision=decision,
            policy_text="Riley is an external customer using the customer portal.",
            reason="End customer asks to see company churn metrics.",
        )


def test_analyst_cannot_get_general_bank_customer_profiles():
    decision = AccessDecision(
        approved=True,
        reason="Analyst wants customer data.",
        risk="high",
        authorization="low",
        duration_seconds=900,
        grants=[{"resource_key": "bank_customer_profiles", "actions": ["dynamodb:Scan"]}],
    )

    with pytest.raises(ValueError, match="bank_customer_profiles"):
        validate_decision(
            decision=decision,
            policy_text=ANALYST_POLICY,
            reason="Scan customers for a company report.",
        )


def test_non_admin_cannot_write_policy_table():
    decision = AccessDecision(
        approved=True,
        reason="Support wants to edit a policy.",
        risk="high",
        authorization="low",
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
        risk="medium",
        authorization="high",
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


def test_bank_transactions_read_access_is_valid():
    decision = AccessDecision(
        approved=True,
        reason="Transaction reporting request.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[{"resource_key": "bank_transactions", "actions": ["dynamodb:Scan"]}],
    )

    validated = validate_decision(
        decision=decision,
        policy_text=ANALYST_POLICY,
        reason="Review transaction rows for reporting.",
    )

    assert validated is decision


def test_analyst_operational_metrics_read_access_is_valid():
    decision = AccessDecision(
        approved=True,
        reason="Analyst aggregate metrics request.",
        risk="low",
        authorization="high",
        duration_seconds=900,
        grants=[
            {
                "resource_key": "bank_operational_metrics",
                "actions": ["dynamodb:Scan"],
            }
        ],
    )

    validated = validate_decision(
        decision=decision,
        policy_text=ANALYST_POLICY,
        reason="Review aggregate fraud, liquidity, branch, card, and deposit metrics.",
    )

    assert validated is decision


def test_support_requests_read_and_update_access_is_valid():
    decision = AccessDecision(
        approved=True,
        reason="Support ticket request.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[
            {
                "resource_key": "support_requests",
                "actions": ["dynamodb:Query", "dynamodb:UpdateItem"],
            }
        ],
    )

    validated = validate_decision(
        decision=decision,
        policy_text=SUPPORT_POLICY,
        reason="Update ticket SR-2026-1001-002 after customer authorisation check.",
    )

    assert validated is decision


def test_non_admin_or_hr_cannot_write_users_table():
    decision = AccessDecision(
        approved=True,
        reason="Policy admin wants to edit the user directory.",
        risk="high",
        authorization="low",
        duration_seconds=900,
        grants=[{"resource_key": "users_table", "actions": ["dynamodb:UpdateItem"]}],
    )

    with pytest.raises(ValueError, match="users_table"):
        validate_decision(
            decision=decision,
            policy_text=SUPPORT_POLICY,
            reason="Update a user directory row.",
        )


def test_hr_can_create_cognito_user_and_users_table_row():
    decision = AccessDecision(
        approved=True,
        reason="HR onboarding request.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[
            {
                "resource_key": "user_pool",
                "actions": [
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminGetUser",
                ],
            },
            {"resource_key": "users_table", "actions": ["dynamodb:PutItem"]},
        ],
    )

    validated = validate_decision(
        decision=decision,
        policy_text=HR_POLICY,
        reason="Create a user account for new hire onboarding.",
    )

    assert validated is decision


def test_non_admin_or_hr_cannot_manage_user_pool():
    decision = AccessDecision(
        approved=True,
        reason="Support wants to create a user.",
        risk="high",
        authorization="low",
        duration_seconds=900,
        grants=[
            {
                "resource_key": "user_pool",
                "actions": ["cognito-idp:AdminCreateUser"],
            }
        ],
    )

    with pytest.raises(ValueError, match="user_pool"):
        validate_decision(
            decision=decision,
            policy_text=SUPPORT_POLICY,
            reason="Create a user account.",
        )


def test_schema_rejects_unknown_resource_and_excess_duration():
    with pytest.raises(Exception):
        AccessDecision(
            approved=True,
            reason="Invalid resource.",
            risk="medium",
            authorization="low",
            duration_seconds=7200,
            grants=[{"resource_key": "unknown", "actions": ["dynamodb:GetItem"]}],
        )


def test_session_policy_uses_exact_catalog_arns():
    catalog = {
        "bank_customer_profiles": Resource(
            key="bank_customer_profiles",
            table_name="bank_customer_profiles",
            table_arn="arn:aws:dynamodb:ap-southeast-2:123:table/bank_customer_profiles",
            purpose="customer data",
        )
    }
    decision = AccessDecision(
        approved=True,
        reason="Specific support request.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[{"resource_key": "bank_customer_profiles", "actions": ["dynamodb:GetItem"]}],
    )

    policy = build_session_policy(decision, catalog)

    assert policy["Statement"] == [
        {
            "Effect": "Allow",
            "Action": ["dynamodb:DescribeTable", "dynamodb:GetItem"],
            "Resource": [
                "arn:aws:dynamodb:ap-southeast-2:123:table/bank_customer_profiles",
                "arn:aws:dynamodb:ap-southeast-2:123:table/bank_customer_profiles/index/*",
            ],
        }
    ]


def test_session_policy_can_add_list_tables_for_employee_console_demo():
    catalog = {
        "bank_customer_profiles": Resource(
            key="bank_customer_profiles",
            table_name="bank_customer_profiles",
            table_arn="arn:aws:dynamodb:ap-southeast-2:123:table/bank_customer_profiles",
            purpose="customer data",
        )
    }
    decision = AccessDecision(
        approved=True,
        reason="Specific support request.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[{"resource_key": "bank_customer_profiles", "actions": ["dynamodb:GetItem"]}],
    )

    policy = build_session_policy(
        decision,
        catalog,
        include_dynamodb_list_tables=True,
    )

    assert policy["Statement"][-1] == {
        "Effect": "Allow",
        "Action": ["dynamodb:ListTables"],
        "Resource": "*",
    }


def test_session_policy_can_add_scan_for_staff_console_demo():
    catalog = {
        "bank_customer_profiles": Resource(
            key="bank_customer_profiles",
            table_name="bank_customer_profiles",
            table_arn="arn:aws:dynamodb:ap-southeast-2:123:table/bank_customer_profiles",
            purpose="customer data",
        )
    }
    decision = AccessDecision(
        approved=True,
        reason="Specific support request.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[{"resource_key": "bank_customer_profiles", "actions": ["dynamodb:GetItem"]}],
    )

    policy = build_session_policy(decision, catalog, include_dynamodb_scan=True)

    assert policy["Statement"][0]["Action"] == [
        "dynamodb:DescribeTable",
        "dynamodb:GetItem",
        "dynamodb:Scan",
    ]


def test_bank_balances_session_policy_scopes_leading_key_to_user():
    catalog = {
        "bank_balances": Resource(
            key="bank_balances",
            table_name="bank_balances",
            table_arn="arn:aws:dynamodb:ap-southeast-2:123:table/bank_balances",
            purpose="account data",
        )
    }
    decision = AccessDecision(
        approved=True,
        reason="Own account lookup.",
        risk="low",
        authorization="high",
        duration_seconds=900,
        grants=[{"resource_key": "bank_balances", "actions": ["dynamodb:GetItem"]}],
    )

    policy = build_session_policy(decision, catalog, user_id="user-123")

    assert policy["Statement"][0]["Condition"] == {
        "ForAllValues:StringEquals": {
            "dynamodb:LeadingKeys": ["user-123"],
        }
    }


def test_support_requests_session_policy_scopes_leading_key_to_user():
    catalog = {
        "support_requests": Resource(
            key="support_requests",
            table_name="support-requests",
            table_arn="arn:aws:dynamodb:ap-southeast-2:123:table/support-requests",
            purpose="support request data",
        )
    }
    decision = AccessDecision(
        approved=True,
        reason="Own support request lookup.",
        risk="low",
        authorization="high",
        duration_seconds=900,
        grants=[{"resource_key": "support_requests", "actions": ["dynamodb:Query"]}],
    )

    policy = build_session_policy(decision, catalog, user_id="user-123")

    assert policy["Statement"][0]["Condition"] == {
        "ForAllValues:StringEquals": {
            "dynamodb:LeadingKeys": ["user-123"],
        }
    }


def test_cognito_session_policy_uses_user_pool_arn_only():
    catalog = {
        "user_pool": Resource(
            key="user_pool",
            table_name="ap-southeast-2_pool",
            table_arn="arn:aws:cognito-idp:ap-southeast-2:123:userpool/pool",
            purpose="user pool",
        )
    }
    decision = AccessDecision(
        approved=True,
        reason="Create user.",
        risk="medium",
        authorization="high",
        duration_seconds=900,
        grants=[
            {
                "resource_key": "user_pool",
                "actions": ["cognito-idp:AdminCreateUser"],
            }
        ],
    )

    policy = build_session_policy(decision, catalog)

    assert policy["Statement"][0] == {
        "Effect": "Allow",
        "Action": ["cognito-idp:AdminCreateUser"],
        "Resource": ["arn:aws:cognito-idp:ap-southeast-2:123:userpool/pool"],
    }
