from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ResourceKey = Literal[
    "users_table",
    "user_pool",
    "customer_data",
    "analytics_data",
    "transactions",
    "account_data",
    "policy_table",
]
AwsAction = Literal[
    "dynamodb:GetItem",
    "dynamodb:BatchGetItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "cognito-idp:AdminAddUserToGroup",
    "cognito-idp:AdminCreateUser",
    "cognito-idp:AdminGetUser",
    "cognito-idp:AdminSetUserPassword",
    "cognito-idp:AdminUpdateUserAttributes",
]
RiskLevel = Literal["low", "medium", "high", "critical"]
AuthorizationLevel = Literal["low", "medium", "high"]


class AccessGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resource_key: ResourceKey
    actions: list[AwsAction] = Field(min_length=1, max_length=7)


class AccessDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str = Field(min_length=1, max_length=1000)
    risk: RiskLevel
    authorization: AuthorizationLevel
    duration_seconds: int = Field(ge=900, le=3600)
    grants: list[AccessGrant] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def approved_decisions_need_grants(self) -> "AccessDecision":
        if self.approved and not self.grants:
            raise ValueError("approved decisions must include at least one grant")
        if not self.approved and self.grants:
            raise ValueError("denied decisions must not include grants")
        return self
