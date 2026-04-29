from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_cognito as cognito
from constructs import Construct

from iam_agent.config.resources import ADMIN_GROUP_NAME, EMPLOYEE_GROUP_NAME


class Auth(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True),
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.user_pool_client = cognito.CfnUserPoolClient(
            self,
            "StaffAppClient",
            user_pool_id=self.user_pool.user_pool_id,
            explicit_auth_flows=[
                "ALLOW_USER_PASSWORD_AUTH",
                "ALLOW_USER_SRP_AUTH",
                "ALLOW_REFRESH_TOKEN_AUTH",
            ],
            generate_secret=False,
            prevent_user_existence_errors="ENABLED",
            supported_identity_providers=["COGNITO"],
        )

        self.admin_group = cognito.UserPoolGroup(
            self,
            "AdminGroup",
            user_pool=self.user_pool,
            group_name=ADMIN_GROUP_NAME,
            description="Admins can manage users, agents, and access policies.",
            precedence=0,
        )

        self.employee_group = cognito.UserPoolGroup(
            self,
            "EmployeeGroup",
            user_pool=self.user_pool,
            group_name=EMPLOYEE_GROUP_NAME,
            description="Employees can request temporary AWS access.",
            precedence=10,
        )

        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
        )
        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.ref,
        )
