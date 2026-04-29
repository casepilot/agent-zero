from pathlib import Path

from aws_cdk import Aws, BundlingOptions, CfnOutput, DockerImage, Duration
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


class BrokerApi(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        user_pool,
        users_table,
        policy_table,
        customer_data_table,
        analytics_data_table,
    ) -> None:
        super().__init__(scope, construct_id)

        repo_root = Path(__file__).resolve().parents[3]
        broker_service_path = repo_root / "services" / "broker-api"
        agent_code_path = repo_root / "services" / "agent-api" / "src"
        openai_secret = secretsmanager.Secret.from_secret_name_v2(
            self,
            "OpenAiSecret",
            "openai-key",
        )

        # AgentZero is the IAM agent. It owns broker-side credential decisions.
        self.broker_lambda = lambda_.Function(
            self,
            "BrokerLambda",
            function_name="AgentZero",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="broker_api.handlers.credentials.handler",
            code=lambda_.Code.from_asset(
                str(broker_service_path),
                bundling=BundlingOptions(
                    image=DockerImage.from_registry("public.ecr.aws/sam/build-python3.11"),
                    command=[
                        "bash",
                        "-c",
                        "pip install -r requirements.txt -t /asset-output && cp -R src/* /asset-output/",
                    ],
                ),
            ),
            timeout=Duration.seconds(30),
            environment={
                "USERS_TABLE_NAME": users_table.table_name,
                "POLICY_TABLE_NAME": policy_table.table_name,
                "POLICY_TABLE_ARN": policy_table.table_arn,
                "CUSTOMER_DATA_TABLE_NAME": customer_data_table.table_name,
                "CUSTOMER_DATA_TABLE_ARN": customer_data_table.table_arn,
                "ANALYTICS_DATA_TABLE_NAME": analytics_data_table.table_name,
                "ANALYTICS_DATA_TABLE_ARN": analytics_data_table.table_arn,
                "OPENAI_SECRET_NAME": "openai-key",
            },
        )

        self.broker_credentials_role = iam.Role(
            self,
            "BrokerCredentialsRole",
            assumed_by=iam.ArnPrincipal(self.broker_lambda.role.role_arn),
            description="Broad target role for AgentZero to scope down with STS session policies.",
        )
        self.broker_credentials_role.add_to_policy(
            iam.PolicyStatement(
                actions=["dynamodb:*"],
                resources=[
                    policy_table.table_arn,
                    f"{policy_table.table_arn}/index/*",
                    customer_data_table.table_arn,
                    f"{customer_data_table.table_arn}/index/*",
                    analytics_data_table.table_arn,
                    f"{analytics_data_table.table_arn}/index/*",
                ],
            )
        )
        self.broker_credentials_role.add_to_policy(
            iam.PolicyStatement(actions=["s3:*"], resources=["*"])
        )
        self.broker_lambda.add_environment(
            "BROKER_CREDENTIALS_ROLE_ARN",
            self.broker_credentials_role.role_arn,
        )

        users_table.grant_read_data(self.broker_lambda)
        policy_table.grant_read_data(self.broker_lambda)
        openai_secret.grant_read(self.broker_lambda)
        self.broker_credentials_role.grant_assume_role(self.broker_lambda)

        self.api = apigateway.RestApi(
            self,
            "BrokerRestApi",
            rest_api_name="iam-agent-broker-api",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
        )

        self.cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[user_pool],
        )

        credentials_resource = self.api.root.add_resource("credentials")
        credentials_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self.broker_lambda),
            authorization_type=apigateway.AuthorizationType.IAM,
        )

        credentials_url = (
            f"https://{self.api.rest_api_id}.execute-api."
            f"{Aws.REGION}.{Aws.URL_SUFFIX}/prod/credentials"
        )

        # UserAgent is the agent that users interact with.
        self.agent_lambda = lambda_.Function(
            self,
            "AgentLambda",
            function_name="UserAgent",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="agent_api.handler.handler",
            code=lambda_.Code.from_asset(str(agent_code_path)),
            timeout=Duration.seconds(15),
            environment={
                "CREDENTIALS_URL": credentials_url,
                "OPENAI_SECRET_NAME": "openai-key",
            },
        )
        openai_secret.grant_read(self.agent_lambda)

        agent_resource = self.api.root.add_resource("agent")
        agent_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self.agent_lambda),
            authorization_type=apigateway.AuthorizationType.COGNITO,
            authorizer=self.cognito_authorizer,
        )

        self.agent_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:Invoke"],
                resources=[
                    self.api.arn_for_execute_api(
                        method="GET",
                        path="/credentials",
                        stage="prod",
                    )
                ],
            )
        )

        CfnOutput(
            self,
            "BrokerApiUrl",
            value=self.api.url,
        )
        CfnOutput(
            self,
            "CredentialsUrl",
            value=self.api.url_for_path("/credentials"),
        )
        CfnOutput(
            self,
            "AgentUrl",
            value=self.api.url_for_path("/agent"),
        )
