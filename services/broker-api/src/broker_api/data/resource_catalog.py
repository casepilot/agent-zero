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
        "bank_customer_profiles": Resource(
            key="bank_customer_profiles",
            table_name=os.environ["BANK_CUSTOMER_PROFILES_TABLE_NAME"],
            table_arn=os.environ["BANK_CUSTOMER_PROFILES_TABLE_ARN"],
            purpose=(
                "Sensitive retail bank customer records for support and KYC "
                "work. Contains customer identity, contact details, risk tier, "
                "account status, relationship manager, and support notes."
            ),
        ),
        "bank_operational_metrics": Resource(
            key="bank_operational_metrics",
            table_name=os.environ["BANK_OPERATIONAL_METRICS_TABLE_NAME"],
            table_arn=os.environ["BANK_OPERATIONAL_METRICS_TABLE_ARN"],
            purpose=(
                "Aggregated bank operating metrics for analysts and leaders. "
                "Includes deposits, card spend, fraud rates, liquidity, branch "
                "volume, and portfolio health; no customer-level PII."
            ),
        ),
        "bank_transactions": Resource(
            key="bank_transactions",
            table_name=os.environ["BANK_TRANSACTIONS_TABLE_NAME"],
            table_arn=os.environ["BANK_TRANSACTIONS_TABLE_ARN"],
            purpose=(
                "Bank transaction ledger for transfers, deposits, withdrawals, "
                "card purchases, reversals, and merchant activity. Contains "
                "customer_id, user_id, account_id, amount, merchant, channel, "
                "risk signal, status, and timestamp."
            ),
        ),
        "bank_balances": Resource(
            key="bank_balances",
            table_name=os.environ["BANK_BALANCES_TABLE_NAME"],
            table_arn=os.environ["BANK_BALANCES_TABLE_ARN"],
            purpose=(
                "Retail customer balance and account summary table keyed by "
                "user_id. Contains the signed-in customer's account ids, "
                "available/current balances, currency, overdraft status, and "
                "last statement date."
            ),
        ),
        "support_requests": Resource(
            key="support_requests",
            table_name=os.environ["SUPPORT_REQUESTS_TABLE_NAME"],
            table_arn=os.environ["SUPPORT_REQUESTS_TABLE_ARN"],
            purpose=(
                "Bank customer support request and ticket history keyed by "
                "user_id and request_id. Contains customer-submitted service "
                "requests, categories, status, priority, assigned team, "
                "summaries, and latest support updates."
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
