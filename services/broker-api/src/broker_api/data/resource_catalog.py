import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Resource:
    key: str
    table_name: str
    table_arn: str
    purpose: str


def get_resource_catalog() -> dict[str, Resource]:
    return {
        "users_table": Resource(
            key="users_table",
            table_name=os.environ["USERS_TABLE_NAME"],
            table_arn=os.environ["USERS_TABLE_ARN"],
            purpose=(
                "Principal directory for humans and agents. Contains user_id, "
                "username, display name, role label, and human/agent flag."
            ),
        ),
        "user_pool": Resource(
            key="user_pool",
            table_name=os.environ["USER_POOL_ID"],
            table_arn=os.environ["USER_POOL_ARN"],
            purpose=(
                "Cognito user pool for creating and managing application "
                "users and group membership."
            ),
        ),
        "customer_data": Resource(
            key="customer_data",
            table_name=os.environ["CUSTOMER_DATA_TABLE_NAME"],
            table_arn=os.environ["CUSTOMER_DATA_TABLE_ARN"],
            purpose=(
                "Sensitive customer records for support work. Contains names, "
                "emails, plan, account status, and support notes."
            ),
        ),
        "analytics_data": Resource(
            key="analytics_data",
            table_name=os.environ["ANALYTICS_DATA_TABLE_NAME"],
            table_arn=os.environ["ANALYTICS_DATA_TABLE_ARN"],
            purpose=(
                "Aggregated business analytics and metrics. This is for company "
                "analyst work and must not be exposed to customers."
            ),
        ),
        "transactions": Resource(
            key="transactions",
            table_name=os.environ["TRANSACTIONS_TABLE_NAME"],
            table_arn=os.environ["TRANSACTIONS_TABLE_ARN"],
            purpose=(
                "Transaction records for company operational and reporting "
                "work. Contains transaction ids, customer ids, amounts, status, "
                "and timestamps."
            ),
        ),
        "account_data": Resource(
            key="account_data",
            table_name=os.environ["ACCOUNT_DATA_TABLE_NAME"],
            table_arn=os.environ["ACCOUNT_DATA_TABLE_ARN"],
            purpose=(
                "Account self-service records keyed by user_id. Contains "
                "account balance, plan, and account status for the signed-in "
                "principal."
            ),
        ),
        "policy_table": Resource(
            key="policy_table",
            table_name=os.environ["POLICY_TABLE_NAME"],
            table_arn=os.environ["POLICY_TABLE_ARN"],
            purpose=(
                "Access policy store. Admins may read and write this table when "
                "creating or editing policies."
            ),
        ),
    }


def catalog_for_prompt(catalog: dict[str, Resource]) -> str:
    lines = []
    for resource in catalog.values():
        lines.append(
            f"- {resource.key}: AWS resource {resource.table_name}. "
            f"Purpose: {resource.purpose}"
        )
    return "\n".join(lines)
