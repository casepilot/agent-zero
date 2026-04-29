from pathlib import Path

from aws_cdk import Aws, BundlingOptions, CfnOutput, DockerImage, Duration
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_apigatewayv2 as apigatewayv2
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
        request_logs_table,
        user_pool_client_id: str,
    ) -> None:
        super().__init__(scope, construct_id)

        repo_root = Path(__file__).resolve().parents[3]
        broker_service_path = repo_root / "services" / "broker-api"
        agent_service_path = repo_root / "services" / "agent-api"
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
            architecture=lambda_.Architecture.ARM_64,
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
                "REQUEST_LOGS_TABLE_NAME": request_logs_table.table_name,
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
            iam.PolicyStatement(
                actions=["dynamodb:ListTables"],
                resources=["*"],
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
        request_logs_table.grant_write_data(self.broker_lambda)
        openai_secret.grant_read(self.broker_lambda)
        self.broker_credentials_role.grant_assume_role(self.broker_lambda)

        self.api = apigateway.RestApi(
            self,
            "BrokerRestApi",
            rest_api_name="iam-agent-broker-api",
            deploy_options=apigateway.StageOptions(stage_name="prod"),
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

        agent_code = lambda_.Code.from_asset(
            str(agent_service_path),
            bundling=BundlingOptions(
                image=DockerImage.from_registry("public.ecr.aws/sam/build-python3.11"),
                command=[
                    "bash",
                    "-c",
                    "pip install -r requirements.txt -t /asset-output && cp -R src/* /asset-output/",
                ],
            ),
        )

        # UserAgent is the agent that users interact with.
        self.agent_authorizer_lambda = lambda_.Function(
            self,
            "AgentWebSocketAuthorizerLambda",
            function_name="UserAgentWebSocketAuthorizer",
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.ARM_64,
            handler="agent_api.authorizer.handler",
            code=agent_code,
            timeout=Duration.seconds(10),
            environment={
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_CLIENT_ID": user_pool_client_id,
            },
        )

        self.agent_worker_lambda = lambda_.Function(
            self,
            "AgentWorkerLambda",
            function_name="UserAgentWorker",
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.ARM_64,
            handler="agent_api.handler.worker_handler",
            code=agent_code,
            timeout=Duration.seconds(120),
            environment={
                "CREDENTIALS_URL": credentials_url,
                "OPENAI_SECRET_NAME": "openai-key",
            },
        )
        openai_secret.grant_read(self.agent_worker_lambda)

        self.agent_route_lambda = lambda_.Function(
            self,
            "AgentWebSocketLambda",
            function_name="UserAgentWebSocket",
            runtime=lambda_.Runtime.PYTHON_3_11,
            architecture=lambda_.Architecture.ARM_64,
            handler="agent_api.handler.route_handler",
            code=agent_code,
            timeout=Duration.seconds(10),
            environment={
                "AGENT_WORKER_FUNCTION_NAME": self.agent_worker_lambda.function_name,
            },
        )
        self.agent_worker_lambda.grant_invoke(self.agent_route_lambda)

        self.agent_worker_lambda.add_to_role_policy(
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

        self.agent_websocket_api = apigatewayv2.CfnApi(
            self,
            "AgentWebSocketApi",
            name="iam-agent-agent-api",
            protocol_type="WEBSOCKET",
            route_selection_expression="$request.body.action",
        )
        self.agent_websocket_url = (
            f"wss://{self.agent_websocket_api.ref}.execute-api."
            f"{Aws.REGION}.{Aws.URL_SUFFIX}/prod"
        )

        self.agent_websocket_authorizer = apigatewayv2.CfnAuthorizer(
            self,
            "AgentWebSocketAuthorizer",
            api_id=self.agent_websocket_api.ref,
            authorizer_type="REQUEST",
            name="agent-websocket-cognito-authorizer",
            authorizer_uri=self._lambda_integration_uri(
                self.agent_authorizer_lambda.function_arn
            ),
            identity_source=["route.request.querystring.token"],
        )

        self.agent_websocket_route_integration = apigatewayv2.CfnIntegration(
            self,
            "AgentWebSocketRouteIntegration",
            api_id=self.agent_websocket_api.ref,
            integration_type="AWS_PROXY",
            integration_uri=self._lambda_integration_uri(
                self.agent_route_lambda.function_arn
            ),
        )

        self._add_websocket_route("$connect", authorization_type="CUSTOM")
        self._add_websocket_route("$disconnect")
        self._add_websocket_route("$default")
        self._add_websocket_route("requestAccess")

        self.agent_websocket_stage = apigatewayv2.CfnStage(
            self,
            "AgentWebSocketProdStage",
            api_id=self.agent_websocket_api.ref,
            stage_name="prod",
            auto_deploy=True,
        )

        self._grant_apigateway_invoke(
            "AgentWebSocketRouteInvokePermission",
            self.agent_route_lambda,
        )
        self._grant_apigateway_invoke(
            "AgentWebSocketAuthorizerInvokePermission",
            self.agent_authorizer_lambda,
        )

        self.agent_worker_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:ManageConnections"],
                resources=[
                    (
                        f"arn:{Aws.PARTITION}:execute-api:{Aws.REGION}:"
                        f"{Aws.ACCOUNT_ID}:{self.agent_websocket_api.ref}/"
                        "prod/POST/@connections/*"
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
            "AgentWebSocketUrl",
            value=self.agent_websocket_url,
        )

    def _lambda_integration_uri(self, function_arn: str) -> str:
        return (
            f"arn:{Aws.PARTITION}:apigateway:{Aws.REGION}:lambda:path/"
            f"2015-03-31/functions/{function_arn}/invocations"
        )

    def _add_websocket_route(
        self,
        route_key: str,
        *,
        authorization_type: str = "NONE",
    ) -> None:
        route_kwargs = {}
        if authorization_type == "CUSTOM":
            route_kwargs["authorizer_id"] = self.agent_websocket_authorizer.ref

        apigatewayv2.CfnRoute(
            self,
            f"AgentWebSocket{self._route_id_part(route_key)}Route",
            api_id=self.agent_websocket_api.ref,
            route_key=route_key,
            authorization_type=authorization_type,
            target=f"integrations/{self.agent_websocket_route_integration.ref}",
            **route_kwargs,
        )

    def _route_id_part(self, route_key: str) -> str:
        return (
            route_key.replace("$", "")
            .replace("-", "")
            .replace("_", "")
            .replace("/", "")
            .title()
            or "Default"
        )

    def _grant_apigateway_invoke(
        self,
        construct_id: str,
        function: lambda_.Function,
    ) -> None:
        lambda_.CfnPermission(
            self,
            construct_id,
            action="lambda:InvokeFunction",
            function_name=function.function_name,
            principal="apigateway.amazonaws.com",
            source_arn=(
                f"arn:{Aws.PARTITION}:execute-api:{Aws.REGION}:"
                f"{Aws.ACCOUNT_ID}:{self.agent_websocket_api.ref}/*"
            ),
        )
