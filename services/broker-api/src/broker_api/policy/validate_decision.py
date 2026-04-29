from broker_api.policy.schemas import AccessDecision


READ_ACTIONS = {
    "dynamodb:GetItem",
    "dynamodb:BatchGetItem",
    "dynamodb:Query",
    "dynamodb:Scan",
}
WRITE_ACTIONS = {
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
}
ALLOWED_ACTIONS_BY_RESOURCE = {
    "customer_data": READ_ACTIONS | WRITE_ACTIONS,
    "analytics_data": READ_ACTIONS,
    "policy_table": READ_ACTIONS | WRITE_ACTIONS,
}


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def validate_decision(
    *,
    decision: AccessDecision,
    policy_text: str,
    reason: str,
) -> AccessDecision:
    if not decision.approved:
        return decision

    policy = policy_text.lower()
    request_reason = reason.lower()
    combined = f"{policy} {request_reason}"

    is_admin = _contains_any(policy, {"admin", "administrator", "policy admin"})
    is_analyst = _contains_any(policy, {"analyst", "business intelligence"})
    looks_like_customer = _contains_any(
        combined,
        {"end customer", "customer user", "external customer"},
    )

    for grant in decision.grants:
        allowed_actions = ALLOWED_ACTIONS_BY_RESOURCE[grant.resource_key]
        invalid_actions = sorted(set(grant.actions) - allowed_actions)
        if invalid_actions:
            raise ValueError(
                f"{grant.resource_key} cannot be granted actions: {invalid_actions}"
            )

        has_write = bool(set(grant.actions) & WRITE_ACTIONS)

        if grant.resource_key == "analytics_data":
            if looks_like_customer:
                raise ValueError("end customers cannot access analytics_data")

        if grant.resource_key == "customer_data":
            if is_analyst and not is_admin:
                raise ValueError("analyst policies cannot access customer_data")

        if grant.resource_key == "policy_table" and (has_write or not is_admin):
            if not is_admin:
                raise ValueError("only admin policies can access policy_table")

    return decision
