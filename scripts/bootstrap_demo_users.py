#!/usr/bin/env python3

import argparse
import sys
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError


ADMIN_GROUP = "admin"
EMPLOYEE_GROUP = "employee"
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
]

AGENT_USER = {
    "user_id": "customer_support_agent",
    "role": EMPLOYEE_GROUP,
    "name": "customer_support_agent",
    "is_human": False,
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
    user_pool_id: str,
) -> None:
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

    users_table.put_item(Item=AGENT_USER)
    print(f"Bootstrapped agent user {AGENT_USER['user_id']}")

    print("Policy table intentionally left empty.")


def delete_users_table_item(users_table: Any, user_id: str, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY RUN: would delete DynamoDB users-table item {user_id}")
        return

    users_table.delete_item(Key={"user_id": user_id})
    print(f"Deleted DynamoDB users-table item {user_id}")


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

        if user_id:
            delete_cognito_user(cognito, user_pool_id, username, dry_run)
        else:
            print(f"Cognito user {username} does not exist.")
            if not users_table_ids:
                print(f"No DynamoDB users-table items found for {username}.")

    delete_users_table_item(users_table, AGENT_USER["user_id"], dry_run)


def main() -> int:
    args = parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    cloudformation = session.client("cloudformation")
    cognito = session.client("cognito-idp")
    dynamodb = session.resource("dynamodb")

    outputs = get_stack_outputs(cloudformation, args.stack_name)
    user_pool_id = find_output(outputs, "UserPoolId")
    users_table_name = find_output(outputs, "UsersTableName")
    users_table = dynamodb.Table(users_table_name)

    print(f"Using Cognito user pool: {user_pool_id}")
    print(f"Using users table: {users_table_name}")

    if args.command == "bootstrap":
        if args.execute:
            print("--execute is only needed for teardown; ignoring it for bootstrap.")
        bootstrap_demo_users(cognito, users_table, user_pool_id)
    else:
        teardown_demo_users(
            cognito=cognito,
            users_table=users_table,
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
