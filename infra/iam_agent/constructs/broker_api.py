import shutil
import subprocess
import sys
from pathlib import Path

import jsii
from aws_cdk import Aws, BundlingOptions, CfnOutput, DockerImage, Duration, ILocalBundling
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_apigatewayv2 as apigatewayv2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct


@jsii.implements(ILocalBundling)
class _PythonServiceBundling:
    def __init__(self, service_path: Path) -> None:
        self.service_path = service_path

    def try_bundle(self, output_dir: str, options: BundlingOptions) -> bool:
        requirements_path = self.service_path / "requirements.txt"
        src_path = self.service_path / "src"

        if not src_path.exists():
            return False

        try:
            if requirements_path.exists():
                subprocess.check_call(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        "--platform",
                        "manylinux2014_aarch64",
                        "--implementation",
                        "cp",
                        "--python-version",
                        "3.11",
                        "--only-binary=:all:",
                        "--upgrade",
                        "--no-cache-dir",
                        "-r",
                        str(requirements_path),
                        "-t",
                        output_dir,
                    ]
                )
            shutil.copytree(src_path, output_dir, dirs_exist_ok=True)
        except (OSError, subprocess.CalledProcessError):
            return False

        return True


class BrokerApi(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        user_pool,
        users_table,
        policy_table,
        bank_customer_profiles_table,
        bank_operational_metrics_table,
        bank_transactions_table,
        bank_balances_table,
        support_requests_table,
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
        broker_bundling = BundlingOptions(
            image=DockerImage.from_registry("public.ecr.aws/sam/build-python3.11"),
            local=_PythonServiceBundling(broker_service_path),
            command=[
                "bash",
                "-c",
                (
                    "pip install --platform manylinux2014_aarch64 "
                    "--implementation cp --python-version 3.11 "
                    "--only-binary=:all: --upgrade --no-cache-dir "
                    "-r requirements.txt -t /asset-output && "
                    "cp -R src/* /asset-output/"
                ),
            ],
        )
        agent_bundling = BundlingOptions(
            image=DockerImage.from_registry("public.ecr.aws/sam/build-python3.11"),
            local=_PythonServiceBundling(agent_service_path),
            command=[
                "bash",
                "-c",
                (
                    "pip install --platform manylinux2014_aarch64 "
                    "--implementation cp --python-version 3.11 "
                    "--only-binary=:all: --upgrade --no-cache-dir "
                    "-r requirements.txt -t /asset-output && "
                    "cp -R src/* /asset-output/"
                ),
            ],
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
                bundling=broker_bundling,
            ),
            memory_size=1024,
            timeout=Duration.minutes(15),
            environment={
                "USERS_TABLE_NAME": users_table.table_name,
                "USERS_TABLE_ARN": users_table.table_arn,
                "USER_POOL_ID": user_pool.user_pool_id,
                "USER_POOL_ARN": user_pool.user_pool_arn,
                "POLICY_TABLE_NAME": policy_table.table_name,
                "POLICY_TABLE_ARN": policy_table.table_arn,
                "BANK_CUSTOMER_PROFILES_TABLE_NAME": bank_customer_profiles_table.table_name,
                "BANK_CUSTOMER_PROFILES_TABLE_ARN": bank_customer_profiles_table.table_arn,
                "BANK_OPERATIONAL_METRICS_TABLE_NAME": bank_operational_metrics_table.table_name,
                "BANK_OPERATIONAL_METRICS_TABLE_ARN": bank_operational_metrics_table.table_arn,
                "BANK_TRANSACTIONS_TABLE_NAME": bank_transactions_table.table_name,
                "BANK_TRANSACTIONS_TABLE_ARN": bank_transactions_table.table_arn,
                "BANK_BALANCES_TABLE_NAME": bank_balances_table.table_name,
                "BANK_BALANCES_TABLE_ARN": bank_balances_table.table_arn,
                "SUPPORT_REQUESTS_TABLE_NAME": support_requests_table.table_name,
                "SUPPORT_REQUESTS_TABLE_ARN": support_requests_table.table_arn,
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
                    users_table.table_arn,
                    f"{users_table.table_arn}/index/*",
                    policy_table.table_arn,
                    f"{policy_table.table_arn}/index/*",
                    bank_customer_profiles_table.table_arn,
                    f"{bank_customer_profiles_table.table_arn}/index/*",
                    bank_operational_metrics_table.table_arn,
                    f"{bank_operational_metrics_table.table_arn}/index/*",
                    bank_transactions_table.table_arn,
                    f"{bank_transactions_table.table_arn}/index/*",
                    bank_balances_table.table_arn,
                    f"{bank_balances_table.table_arn}/index/*",
                    support_requests_table.table_arn,
                    f"{support_requests_table.table_arn}/index/*",
                ],
            )
        )
        self.broker_credentials_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "cognito-idp:AdminAddUserToGroup",
                    "cognito-idp:AdminCreateUser",
                    "cognito-idp:AdminGetUser",
                    "cognito-idp:AdminSetUserPassword",
                    "cognito-idp:AdminUpdateUserAttributes",
                ],
                resources=[user_pool.user_pool_arn],
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

        agent_code = lambda_.Code.from_asset(
            str(agent_service_path),
            bundling=agent_bundling,
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
            memory_size=1024,
            timeout=Duration.minutes(15),
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
            memory_size=1024,
            timeout=Duration.minutes(15),
            environment={
                "AGENT_MODEL": "gpt-5.5",
                "AGENT_REASONING_EFFORT": "medium",
                "CREDENTIALS_URL": self.api.url_for_path("/credentials"),
                "OPENAI_SECRET_NAME": "openai-key",
                "USER_POOL_ID": user_pool.user_pool_id,
                "USERS_TABLE_NAME": users_table.table_name,
                "POLICY_TABLE_NAME": policy_table.table_name,
                "BANK_CUSTOMER_PROFILES_TABLE_NAME": bank_customer_profiles_table.table_name,
                "BANK_OPERATIONAL_METRICS_TABLE_NAME": bank_operational_metrics_table.table_name,
                "BANK_TRANSACTIONS_TABLE_NAME": bank_transactions_table.table_name,
                "BANK_BALANCES_TABLE_NAME": bank_balances_table.table_name,
                "SUPPORT_REQUESTS_TABLE_NAME": support_requests_table.table_name,
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
            memory_size=1024,
            timeout=Duration.minutes(15),
            environment={
                "AGENT_WORKER_FUNCTION_NAME": self.agent_worker_lambda.function_name,
            },
        )
        self.agent_worker_lambda.grant_invoke(self.agent_route_lambda)

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
        self.agent_route_lambda.add_to_role_policy(
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
        self.agent_worker_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["execute-api:Invoke"],
                resources=[self.api.arn_for_execute_api("GET", "/credentials", "prod")],
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
