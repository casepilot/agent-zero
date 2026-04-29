from pathlib import Path

from aws_cdk import Aws, CfnOutput, Duration
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
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
    ) -> None:
        super().__init__(scope, construct_id)

        repo_root = Path(__file__).resolve().parents[3]
        broker_code_path = repo_root / "services" / "broker-api" / "src"
        agent_code_path = repo_root / "services" / "agent-api" / "src"

        self.broker_lambda = lambda_.Function(
            self,
            "BrokerLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="broker_api.handlers.credentials.handler",
            code=lambda_.Code.from_asset(str(broker_code_path)),
            timeout=Duration.seconds(10),
            reserved_concurrent_executions=1,
            environment={
                "USERS_TABLE_NAME": users_table.table_name,
                "POLICY_TABLE_NAME": policy_table.table_name,
            },
        )

        users_table.grant_read_data(self.broker_lambda)
        policy_table.grant_read_data(self.broker_lambda)

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

        self.agent_lambda = lambda_.Function(
            self,
            "AgentLambda",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="agent_api.handler.handler",
            code=lambda_.Code.from_asset(str(agent_code_path)),
            timeout=Duration.seconds(15),
            reserved_concurrent_executions=1,
            environment={
                "CREDENTIALS_URL": credentials_url,
            },
        )

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
