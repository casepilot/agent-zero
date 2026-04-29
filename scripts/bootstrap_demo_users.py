#!/usr/bin/env python3

import argparse
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from bootstrap.bank_data import (  # noqa: E402
    BANK_BALANCES_TEMPLATE,
    BANK_CUSTOMER_PROFILES,
    BANK_OPERATIONAL_METRICS,
    BANK_POLICIES,
    BANK_TRANSACTIONS_TEMPLATE,
    BANK_USERS,
    OLD_DEMO_USERNAMES,
)


TABLE_KEYS = {
    "users-table": ["user_id"],
    "policy-table": ["user_id"],
    "bank_customer_profiles": ["customer_id"],
    "bank_operational_metrics": ["metric_id"],
    "bank_transactions": ["user_id", "transaction_id"],
    "bank_balances": ["user_id"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap or teardown bank demo Cognito users and DynamoDB data."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=("bootstrap", "teardown"),
        default="bootstrap",
        help="Action to run. Defaults to bootstrap.",
    )
    parser.add_argument("--profile", default="openai-hackathon")
    parser.add_argument("--region", default="ap-southeast-2")
    parser.add_argument("--stack-name", default="IamAgentStack")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete resources when running teardown. Teardown is dry-run by default.",
    )
    return parser.parse_args()


def decimal_safe(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: decimal_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [decimal_safe(child) for child in value]
    return value


def get_stack_outputs(cloudformation: Any, stack_name: str) -> dict[str, str]:
    response = cloudformation.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0].get("Outputs", [])
    return {output["OutputKey"]: output["OutputValue"] for output in outputs}


def find_output(outputs: dict[str, str], key_fragment: str) -> str:
    if key_fragment in outputs:
        return outputs[key_fragment]

    matches = [value for key, value in outputs.items() if key_fragment in key]
    if len(matches) != 1:
        available = ", ".join(sorted(outputs))
        raise RuntimeError(
            f"Expected one CloudFormation output containing {key_fragment!r}; "
            f"found {len(matches)}. Available: {available}"
        )
    return matches[0]


def table_items(table: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    response = table.scan()
    items.extend(response.get("Items", []))
    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
    return items


def clear_table(table: Any, key_names: list[str], *, dry_run: bool = False) -> None:
    items = table_items(table)
    if dry_run:
        print(f"DRY RUN: would delete {len(items)} rows from {table.name}")
        return

    with table.batch_writer() as batch:
        for item in items:
            batch.delete_item(Key={key: item[key] for key in key_names})
    print(f"Deleted {len(items)} rows from {table.name}")


def delete_cognito_user(cognito: Any, user_pool_id: str, username: str, *, dry_run: bool) -> None:
    try:
        cognito.admin_get_user(UserPoolId=user_pool_id, Username=username)
    except ClientError as error:
        if error.response["Error"]["Code"] == "UserNotFoundException":
            return
        raise

    if dry_run:
        print(f"DRY RUN: would delete Cognito user {username}")
        return

    cognito.admin_delete_user(UserPoolId=user_pool_id, Username=username)
    print(f"Deleted Cognito user {username}")


def ensure_cognito_user(cognito: Any, user_pool_id: str, user: dict[str, Any]) -> str:
    username = user["username"]
    attributes = [
        {"Name": "email", "Value": username},
        {"Name": "email_verified", "Value": "true"},
        {"Name": "name", "Value": user["name"]},
    ]
    cognito.admin_create_user(
        UserPoolId=user_pool_id,
        Username=username,
        UserAttributes=attributes,
        TemporaryPassword=user["password"],
        MessageAction="SUPPRESS",
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


def write_batch(table: Any, rows: list[dict[str, Any]]) -> None:
    with table.batch_writer() as batch:
        for row in rows:
            batch.put_item(Item=decimal_safe(row))
    print(f"Bootstrapped {len(rows)} rows into {table.name}")


def bootstrap_bank_data(
    *,
    cognito: Any,
    user_pool_id: str,
    tables: dict[str, Any],
) -> None:
    for username in OLD_DEMO_USERNAMES + [user["username"] for user in BANK_USERS]:
        delete_cognito_user(cognito, user_pool_id, username, dry_run=False)

    for table_name, key_names in TABLE_KEYS.items():
        clear_table(tables[table_name], key_names)

    user_ids_by_username: dict[str, str] = {}
    customer_user_id = ""
    for user in BANK_USERS:
        user_id = ensure_cognito_user(cognito, user_pool_id, user)
        user_ids_by_username[user["username"]] = user_id
        if user.get("customer_id") == "CUST-1001":
            customer_user_id = user_id

        tables["users-table"].put_item(
            Item={
                "user_id": user_id,
                "username": user["username"],
                "name": user["name"],
                "role": user["role"],
                "title": user["title"],
                "department": user["department"],
                "is_human": user["is_human"],
                **({"customer_id": user["customer_id"]} if user.get("customer_id") else {}),
            }
        )
        tables["policy-table"].put_item(
            Item={
                "user_id": user_id,
                "policy": BANK_POLICIES[user["username"]],
            }
        )
        print(f"Bootstrapped bank user {user['username']} as {user_id}")

    if not customer_user_id:
        raise RuntimeError("Customer user_id was not created")

    customer_profiles = []
    for row in BANK_CUSTOMER_PROFILES:
        if row["customer_id"] == "CUST-1001":
            customer_profiles.append({**row, "user_id": customer_user_id})
        else:
            customer_profiles.append(row)

    balances = [
        {
            **row,
            "user_id": customer_user_id,
            "name": "Emily Carter",
        }
        for row in BANK_BALANCES_TEMPLATE
    ]
    transactions = [
        {
            **row,
            "user_id": customer_user_id,
        }
        for row in BANK_TRANSACTIONS_TEMPLATE
    ]

    write_batch(tables["bank_customer_profiles"], customer_profiles)
    write_batch(tables["bank_operational_metrics"], BANK_OPERATIONAL_METRICS)
    write_batch(tables["bank_balances"], balances)
    write_batch(tables["bank_transactions"], transactions)

    print("\nBank demo users:")
    for user in BANK_USERS:
        print(
            f"- {user['username']} / {user['password']} "
            f"({user['role']}, user_id={user_ids_by_username[user['username']]})"
        )


def teardown_bank_data(
    *,
    cognito: Any,
    user_pool_id: str,
    tables: dict[str, Any],
    dry_run: bool,
) -> None:
    if dry_run:
        print("Teardown is dry-run. Pass --execute to delete data.")

    for username in OLD_DEMO_USERNAMES + [user["username"] for user in BANK_USERS]:
        delete_cognito_user(cognito, user_pool_id, username, dry_run=dry_run)

    for table_name, key_names in TABLE_KEYS.items():
        clear_table(tables[table_name], key_names, dry_run=dry_run)


def main() -> int:
    args = parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    cloudformation = session.client("cloudformation")
    cognito = session.client("cognito-idp")
    dynamodb = session.resource("dynamodb")

    outputs = get_stack_outputs(cloudformation, args.stack_name)
    user_pool_id = find_output(outputs, "UserPoolId")
    table_names = {
        "users-table": find_output(outputs, "UsersTableName"),
        "policy-table": find_output(outputs, "PolicyTableName"),
        "bank_customer_profiles": find_output(outputs, "BankCustomerProfilesTableName"),
        "bank_operational_metrics": find_output(outputs, "BankOperationalMetricsTableName"),
        "bank_transactions": find_output(outputs, "BankTransactionsTableName"),
        "bank_balances": find_output(outputs, "BankBalancesTableName"),
    }
    tables = {
        logical_name: dynamodb.Table(physical_name)
        for logical_name, physical_name in table_names.items()
    }

    print(f"Using Cognito user pool: {user_pool_id}")
    for logical_name, physical_name in table_names.items():
        print(f"Using {logical_name}: {physical_name}")

    if args.command == "bootstrap":
        bootstrap_bank_data(
            cognito=cognito,
            user_pool_id=user_pool_id,
            tables=tables,
        )
    else:
        teardown_bank_data(
            cognito=cognito,
            user_pool_id=user_pool_id,
            tables=tables,
            dry_run=not args.execute,
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Bank bootstrap script failed: {error}", file=sys.stderr)
        raise SystemExit(1)
