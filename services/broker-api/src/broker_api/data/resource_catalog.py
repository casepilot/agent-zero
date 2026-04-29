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
            f"- {resource.key}: DynamoDB table {resource.table_name}. "
            f"Purpose: {resource.purpose}"
        )
    return "\n".join(lines)
