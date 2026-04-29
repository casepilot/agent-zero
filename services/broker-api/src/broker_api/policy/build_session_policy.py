from typing import Any

from broker_api.data.resource_catalog import Resource
from broker_api.policy.schemas import AccessDecision


def build_session_policy(
    decision: AccessDecision,
    catalog: dict[str, Resource],
    *,
    include_dynamodb_list_tables: bool = False,
) -> dict[str, Any]:
    statements = []
    for grant in decision.grants:
        resource = catalog[grant.resource_key]
        statements.append(
            {
                "Effect": "Allow",
                "Action": sorted(set(grant.actions)),
                "Resource": [
                    resource.table_arn,
                    f"{resource.table_arn}/index/*",
                ],
            }
        )

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
