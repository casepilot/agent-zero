#!/usr/bin/env python3

import argparse
import sys
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError


ADMIN_GROUP = "admin"
EMPLOYEE_GROUP = "employee"
CUSTOMER_GROUP = "customer"
DEFAULT_PASSWORD = "Hackathon123!"

HUMAN_USERS = [
    {
        "username": "admin@example.com",
        "password": DEFAULT_PASSWORD,
        "group": ADMIN_GROUP,
        "role": ADMIN_GROUP,
        "name": "Admin User",
        "is_human": True,
    },
    {
        "username": "employee1@example.com",
        "password": DEFAULT_PASSWORD,
        "group": EMPLOYEE_GROUP,
        "role": EMPLOYEE_GROUP,
        "name": "Employee One",
        "is_human": True,
    },
    {
        "username": "analyst@example.com",
        "password": DEFAULT_PASSWORD,
        "group": EMPLOYEE_GROUP,
        "role": EMPLOYEE_GROUP,
        "name": "Analyst User",
        "is_human": True,
    },
    {
        "username": "customer@example.com",
        "password": DEFAULT_PASSWORD,
        "group": CUSTOMER_GROUP,
        "role": CUSTOMER_GROUP,
        "name": "Customer User",
        "is_human": True,
    },
]

AGENT_USER = {
    "user_id": "customer_support_agent",
    "role": EMPLOYEE_GROUP,
    "name": "customer_support_agent",
    "is_human": False,
}

CUSTOMER_ROWS = [
    {
        "customer_id": f"cust-{index:03d}",
        "name": name,
        "email": f"{name.lower().replace(' ', '.')}@example.com",
        "plan": plan,
        "account_status": status,
        "support_note": note,
    }
    for index, (name, plan, status, note) in enumerate(
        [
            ("Ava Johnson", "business", "active", "Asked about invoice timing."),
            ("Noah Smith", "starter", "active", "Needs address confirmation."),
            ("Mia Lee", "enterprise", "active", "VIP support route."),
            ("Leo Brown", "starter", "suspended", "Payment failed twice."),
            ("Zara Wilson", "business", "active", "Requested plan upgrade."),
            ("Ethan Taylor", "business", "active", "Open ticket on login issue."),
            ("Sofia Davis", "starter", "active", "Asked for receipt copy."),
            ("Liam Martin", "enterprise", "active", "Security contact updated."),
            ("Isla Anderson", "starter", "active", "Password reset completed."),
            ("Oliver Thomas", "business", "active", "Checking renewal date."),
            ("Amelia Moore", "enterprise", "active", "Contract owner changed."),
            ("Jack White", "starter", "closed", "Account closed by request."),
            ("Grace Harris", "business", "active", "Support escalation pending."),
            ("Henry Clark", "starter", "active", "Asked about data export."),
            ("Chloe Lewis", "enterprise", "active", "SLA review scheduled."),
            ("Lucas Walker", "business", "active", "Billing contact updated."),
            ("Ruby Hall", "starter", "active", "Trial extension approved."),
            ("Mason Young", "business", "suspended", "Fraud review hold."),
            ("Ella King", "enterprise", "active", "Dedicated CSM assigned."),
            ("James Wright", "starter", "active", "Asked about cancellation."),
            ("Harper Scott", "business", "active", "Feature request logged."),
            ("Archie Green", "enterprise", "active", "Data residency question."),
            ("Lily Baker", "starter", "active", "Email bounce resolved."),
            ("William Adams", "business", "active", "Upgrade quote sent."),
            ("Evie Nelson", "enterprise", "active", "Quarterly review booked."),
        ],
        start=1,
    )
]

ANALYTICS_ROWS = [
    {
        "metric_id": "mrr-2026-04",
        "metric_name": "monthly_recurring_revenue",
        "segment": "all",
        "value": 187500,
        "period": "2026-04",
    },
    {
        "metric_id": "churn-2026-04",
        "metric_name": "logo_churn_rate",
        "segment": "all",
        "value": "2.8%",
        "period": "2026-04",
    },
    {
        "metric_id": "support-csat-2026-04",
        "metric_name": "support_csat",
        "segment": "support",
        "value": "94%",
        "period": "2026-04",
    },
    {
        "metric_id": "enterprise-growth-2026-04",
        "metric_name": "enterprise_growth",
        "segment": "enterprise",
        "value": "11.4%",
        "period": "2026-04",
    },
    {
        "metric_id": "trial-conversion-2026-04",
        "metric_name": "trial_conversion",
        "segment": "starter",
        "value": "18.2%",
        "period": "2026-04",
    },
]

TRANSACTION_ROWS = [
    {
        "transaction_id": f"txn-{index:03d}",
        "customer_id": f"cust-{((index - 1) % 25) + 1:03d}",
        "amount": amount,
        "currency": "USD",
        "status": status,
        "created_at": f"2026-04-{((index - 1) % 28) + 1:02d}T10:00:00Z",
    }
    for index, (amount, status) in enumerate(
        [
            (49, "settled"),
            (199, "settled"),
            (29, "pending"),
            (499, "settled"),
            (99, "failed"),
            (149, "settled"),
            (19, "refunded"),
            (299, "settled"),
            (79, "pending"),
            (999, "settled"),
        ],
        start=1,
    )
]

DEMO_POLICIES = {
    "admin@example.com": (
        "Admin User is an identity and access administrator. Their job is to "
        "create, review, and edit access policies for employees and agents. "
        "They may request temporary access when doing policy administration "
        "work, but should receive only the minimum access needed."
    ),
    "employee1@example.com": (
        "Employee One is an IT support engineer. Their job is to investigate "
        "assigned IT support tickets, customer authorisation problems, account "
        "access issues, and operational incidents. They may request temporary "
        "access to relevant company systems when the request is tied to a "
        "specific ticket and the access is limited to support work. They are "
        "not an access administrator and should not change access policies."
    ),
    "analyst@example.com": (
        "Analyst User works in company operations analytics. Their job is to "
        "review transaction and business metric data for reporting, trend "
        "analysis, and operational finance questions. They are not an access "
        "administrator and should not change policies."
    ),
    "customer@example.com": (
        "Customer User is an end customer using the customer portal. They may "
        "request access only to their own account self-service information and "
        "must not access other customers, company analytics, transactions, or "
        "policy data."
    ),
    "customer_support_agent": (
        "customer_support_agent is a customer support AI agent. Its job is to "
        "help customers with account and support questions. It may request "
        "temporary access when helping with a specific customer support case. "
        "It is not an analyst and is not an access administrator."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap or teardown demo Cognito users and IAM Agent "
            "DynamoDB users."
        )
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("bootstrap", "teardown"),
        default="bootstrap",
        help="Action to run. Defaults to bootstrap for backwards compatibility.",
    )
    parser.add_argument("--profile", default="openai-hackathon")
    parser.add_argument("--region", default="ap-southeast-2")
    parser.add_argument("--stack-name", default="IamAgentStack")
    parser.add_argument(
        "--execute",
        action="store_true",
        help=(
            "Actually delete resources when running teardown. Teardown is "
            "dry-run by default."
        ),
    )
    return parser.parse_args()


def get_stack_outputs(cloudformation: Any, stack_name: str) -> dict[str, str]:
    response = cloudformation.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0].get("Outputs", [])
    return {output["OutputKey"]: output["OutputValue"] for output in outputs}


def find_output(outputs: dict[str, str], key_fragment: str) -> str:
    if key_fragment in outputs:
        return outputs[key_fragment]

    matches = [
        value
        for key, value in outputs.items()
        if key_fragment in key
    ]
    if len(matches) != 1:
        available = ", ".join(sorted(outputs))
        raise RuntimeError(
            f"Expected one CloudFormation output containing "
            f"{key_fragment!r}; found {len(matches)}. Available: {available}"
        )
    return matches[0]


def ensure_cognito_user(cognito: Any, user_pool_id: str, user: dict[str, Any]) -> str:
    username = user["username"]
    attributes = [
        {"Name": "email", "Value": username},
        {"Name": "email_verified", "Value": "true"},
        {"Name": "name", "Value": user["name"]},
    ]

    try:
        cognito.admin_create_user(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=attributes,
            TemporaryPassword=user["password"],
            MessageAction="SUPPRESS",
        )
    except ClientError as error:
        if error.response["Error"]["Code"] != "UsernameExistsException":
            raise
        cognito.admin_update_user_attributes(
            UserPoolId=user_pool_id,
            Username=username,
            UserAttributes=attributes,
        )

    cognito.admin_set_user_password(
        UserPoolId=user_pool_id,
        Username=username,
        Password=user["password"],
        Permanent=True,
    )
    cognito.admin_add_user_to_group(
        UserPoolId=user_pool_id,
        Username=username,
        GroupName=user["group"],
    )

    response = cognito.admin_get_user(UserPoolId=user_pool_id, Username=username)
    attributes_by_name = {
        attribute["Name"]: attribute["Value"]
        for attribute in response["UserAttributes"]
    }
    user_id = attributes_by_name.get("sub")
    if not user_id:
        raise RuntimeError(f"Cognito user {username} did not have a sub attribute")
    return user_id


def get_cognito_user_id(cognito: Any, user_pool_id: str, username: str) -> str | None:
    try:
        response = cognito.admin_get_user(
            UserPoolId=user_pool_id,
            Username=username,
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "UserNotFoundException":
            return None
        raise

    attributes_by_name = {
        attribute["Name"]: attribute["Value"]
        for attribute in response["UserAttributes"]
    }
    return attributes_by_name.get("sub")


def bootstrap_demo_users(
    cognito: Any,
    users_table: Any,
    policy_table: Any,
    customer_data_table: Any,
    analytics_data_table: Any,
    transactions_table: Any,
    account_data_table: Any,
    user_pool_id: str,
) -> None:
    account_rows = []
    for user in HUMAN_USERS:
        user_id = ensure_cognito_user(cognito, user_pool_id, user)
        users_table.put_item(
            Item={
                "user_id": user_id,
                "role": user["role"],
                "is_human": user["is_human"],
                "name": user["name"],
                "username": user["username"],
            }
        )
        print(f"Bootstrapped human user {user['username']} as {user_id}")
        policy_table.put_item(
            Item={
                "user_id": user_id,
                "policy": DEMO_POLICIES[user["username"]],
            }
        )
        print(f"Bootstrapped demo policy for {user['username']}")
        if user["role"] == CUSTOMER_GROUP:
            account_rows.append(
                {
                    "user_id": user_id,
                    "name": user["name"],
                    "account_balance": "128.42",
                    "currency": "USD",
                    "plan": "starter",
                    "account_status": "active",
                }
            )

    users_table.put_item(Item=AGENT_USER)
    print(f"Bootstrapped agent user {AGENT_USER['user_id']}")
    policy_table.put_item(
        Item={
            "user_id": AGENT_USER["user_id"],
            "policy": DEMO_POLICIES[AGENT_USER["user_id"]],
        }
    )
    print(f"Bootstrapped demo policy for {AGENT_USER['user_id']}")

    with customer_data_table.batch_writer() as batch:
        for row in CUSTOMER_ROWS:
            batch.put_item(Item=row)
    print(f"Bootstrapped {len(CUSTOMER_ROWS)} customer_data rows")

    with analytics_data_table.batch_writer() as batch:
        for row in ANALYTICS_ROWS:
            batch.put_item(Item=row)
    print(f"Bootstrapped {len(ANALYTICS_ROWS)} analytics_data rows")

    with transactions_table.batch_writer() as batch:
        for row in TRANSACTION_ROWS:
            batch.put_item(Item=row)
    print(f"Bootstrapped {len(TRANSACTION_ROWS)} transactions rows")

    with account_data_table.batch_writer() as batch:
        for row in account_rows:
            batch.put_item(Item=row)
    print(f"Bootstrapped {len(account_rows)} account_data rows")


def delete_users_table_item(users_table: Any, user_id: str, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN: would delete DynamoDB users-table item {user_id}")
        return

    users_table.delete_item(Key={"user_id": user_id})
    print(f"Deleted DynamoDB users-table item {user_id}")


def delete_table_item(
    table: Any,
    key: dict[str, str],
    description: str,
    dry_run: bool,
) -> None:
    if dry_run:
        print(f"DRY RUN: would delete {description} {key}")
        return

    table.delete_item(Key=key)
    print(f"Deleted {description} {key}")


def find_users_table_ids_by_username(users_table: Any, username: str) -> list[str]:
    response = users_table.scan(
        FilterExpression=Attr("username").eq(username),
        ProjectionExpression="user_id",
    )
    user_ids = [
        item["user_id"]
        for item in response.get("Items", [])
        if "user_id" in item
    ]

    while "LastEvaluatedKey" in response:
        response = users_table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"],
            FilterExpression=Attr("username").eq(username),
            ProjectionExpression="user_id",
        )
        user_ids.extend(
            item["user_id"]
            for item in response.get("Items", [])
            if "user_id" in item
        )

    return user_ids


def delete_cognito_user(
    cognito: Any,
    user_pool_id: str,
    username: str,
    dry_run: bool,
) -> None:
    if dry_run:
        print(f"DRY RUN: would delete Cognito user {username}")
        return

    cognito.admin_delete_user(
        UserPoolId=user_pool_id,
        Username=username,
    )
    print(f"Deleted Cognito user {username}")


def teardown_demo_users(
    cognito: Any,
    users_table: Any,
    policy_table: Any,
    customer_data_table: Any,
    analytics_data_table: Any,
    transactions_table: Any,
    account_data_table: Any,
    user_pool_id: str,
    dry_run: bool,
) -> None:
    if dry_run:
        print(
            "Teardown is running in dry-run mode. "
            "Pass --execute to delete resources."
        )

    for user in HUMAN_USERS:
        username = user["username"]
        user_id = get_cognito_user_id(cognito, user_pool_id, username)
        users_table_ids = find_users_table_ids_by_username(users_table, username)
        if user_id:
            users_table_ids.append(user_id)

        for users_table_id in sorted(set(users_table_ids)):
            delete_users_table_item(users_table, users_table_id, dry_run)
            delete_table_item(
                policy_table,
                {"user_id": users_table_id},
                "DynamoDB policy-table item",
                dry_run,
            )
            delete_table_item(
                account_data_table,
                {"user_id": users_table_id},
                "DynamoDB account_data item",
                dry_run,
            )

        if user_id:
            delete_cognito_user(cognito, user_pool_id, username, dry_run)
        else:
            print(f"Cognito user {username} does not exist.")
            if not users_table_ids:
                print(f"No DynamoDB users-table items found for {username}.")

    delete_users_table_item(users_table, AGENT_USER["user_id"], dry_run)
    delete_table_item(
        policy_table,
        {"user_id": AGENT_USER["user_id"]},
        "DynamoDB policy-table item",
        dry_run,
    )

    for row in CUSTOMER_ROWS:
        delete_table_item(
            customer_data_table,
            {"customer_id": row["customer_id"]},
            "DynamoDB customer_data item",
            dry_run,
        )
    for row in ANALYTICS_ROWS:
        delete_table_item(
            analytics_data_table,
            {"metric_id": row["metric_id"]},
            "DynamoDB analytics_data item",
            dry_run,
        )
    for row in TRANSACTION_ROWS:
        delete_table_item(
            transactions_table,
            {"transaction_id": row["transaction_id"]},
            "DynamoDB transactions item",
            dry_run,
        )


def main() -> int:
    args = parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    cloudformation = session.client("cloudformation")
    cognito = session.client("cognito-idp")
    dynamodb = session.resource("dynamodb")

    outputs = get_stack_outputs(cloudformation, args.stack_name)
    user_pool_id = find_output(outputs, "UserPoolId")
    users_table_name = find_output(outputs, "UsersTableName")
    policy_table_name = find_output(outputs, "PolicyTableName")
    customer_data_table_name = find_output(outputs, "CustomerDataTableName")
    analytics_data_table_name = find_output(outputs, "AnalyticsDataTableName")
    transactions_table_name = find_output(outputs, "TransactionsTableName")
    account_data_table_name = find_output(outputs, "AccountDataTableName")
    users_table = dynamodb.Table(users_table_name)
    policy_table = dynamodb.Table(policy_table_name)
    customer_data_table = dynamodb.Table(customer_data_table_name)
    analytics_data_table = dynamodb.Table(analytics_data_table_name)
    transactions_table = dynamodb.Table(transactions_table_name)
    account_data_table = dynamodb.Table(account_data_table_name)

    print(f"Using Cognito user pool: {user_pool_id}")
    print(f"Using users table: {users_table_name}")
    print(f"Using policy table: {policy_table_name}")
    print(f"Using customer data table: {customer_data_table_name}")
    print(f"Using analytics data table: {analytics_data_table_name}")
    print(f"Using transactions table: {transactions_table_name}")
    print(f"Using account data table: {account_data_table_name}")

    if args.command == "bootstrap":
        if args.execute:
            print("--execute is only needed for teardown; ignoring it for bootstrap.")
        bootstrap_demo_users(
            cognito,
            users_table,
            policy_table,
            customer_data_table,
            analytics_data_table,
            transactions_table,
            account_data_table,
            user_pool_id,
        )
    else:
        teardown_demo_users(
            cognito=cognito,
            users_table=users_table,
            policy_table=policy_table,
            customer_data_table=customer_data_table,
            analytics_data_table=analytics_data_table,
            transactions_table=transactions_table,
            account_data_table=account_data_table,
            user_pool_id=user_pool_id,
            dry_run=not args.execute,
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Demo user script failed: {error}", file=sys.stderr)
        raise SystemExit(1)
