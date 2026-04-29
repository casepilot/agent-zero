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
COGNITO_USER_ADMIN_ACTIONS = {
    "cognito-idp:AdminAddUserToGroup",
    "cognito-idp:AdminCreateUser",
    "cognito-idp:AdminGetUser",
    "cognito-idp:AdminSetUserPassword",
    "cognito-idp:AdminUpdateUserAttributes",
}
ALLOWED_ACTIONS_BY_RESOURCE = {
    "users_table": READ_ACTIONS | WRITE_ACTIONS,
    "user_pool": COGNITO_USER_ADMIN_ACTIONS,
    "bank_customer_profiles": READ_ACTIONS | WRITE_ACTIONS,
    "bank_operational_metrics": READ_ACTIONS,
    "bank_transactions": READ_ACTIONS,
    "bank_balances": READ_ACTIONS | WRITE_ACTIONS,
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
    is_hr = _contains_any(policy, {"hr", "human resources", "people operations"})
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

        if grant.resource_key == "bank_operational_metrics":
            if looks_like_customer:
                raise ValueError("end customers cannot access bank_operational_metrics")

        if grant.resource_key == "bank_customer_profiles":
            if is_analyst and not is_admin:
                raise ValueError("analyst policies cannot access bank_customer_profiles")

        if grant.resource_key == "users_table" and has_write:
            if not (is_admin or is_hr):
                raise ValueError("only admin or HR policies can write users_table")

        if grant.resource_key == "user_pool":
            if not (is_admin or is_hr):
                raise ValueError("only admin or HR policies can manage user_pool")

        if grant.resource_key == "policy_table" and (has_write or not is_admin):
            if not is_admin:
                raise ValueError("only admin policies can access policy_table")

    return decision
