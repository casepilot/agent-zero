from typing import Any

from broker_api.data.resource_catalog import Resource
from broker_api.policy.schemas import AccessDecision


def build_session_policy(
    decision: AccessDecision,
    catalog: dict[str, Resource],
    *,
    user_id: str | None = None,
    include_dynamodb_list_tables: bool = False,
    include_dynamodb_scan: bool = False,
) -> dict[str, Any]:
    statements = []
    for grant in decision.grants:
        resource = catalog[grant.resource_key]
        actions = set(grant.actions)
        is_dynamodb = any(action.startswith("dynamodb:") for action in actions)
        if is_dynamodb:
            actions.add("dynamodb:DescribeTable")
            if include_dynamodb_scan:
                actions.add("dynamodb:Scan")
        statement: dict[str, Any] = {
            "Effect": "Allow",
            "Action": sorted(actions),
            "Resource": (
                [
                    resource.table_arn,
                    f"{resource.table_arn}/index/*",
                ]
                if is_dynamodb
                else [resource.table_arn]
            ),
        }
        if grant.resource_key == "account_data" and user_id:
            statement["Condition"] = {
                "ForAllValues:StringEquals": {
                    "dynamodb:LeadingKeys": [user_id],
                }
            }
        statements.append(statement)

    if include_dynamodb_list_tables and statements:
        statements.append(
            {
                "Effect": "Allow",
                "Action": ["dynamodb:ListTables"],
                "Resource": "*",
            }
        )

    return {
        "Version": "2012-10-17",
        "Statement": statements,
    }
