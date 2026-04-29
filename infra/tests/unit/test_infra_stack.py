import aws_cdk as core
import aws_cdk.assertions as assertions

from iam_agent.iam_agent_stack import IamAgentStack


def test_cognito_auth_resources_created():
    app = core.App()
    stack = IamAgentStack(app, "iam-agent-auth")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::Cognito::UserPool", 1)
    template.resource_count_is("AWS::Cognito::UserPoolClient", 1)
    template.has_resource_properties(
        "AWS::Cognito::UserPoolGroup",
        {"GroupName": "admin"},
    )
    template.has_resource_properties(
        "AWS::Cognito::UserPoolGroup",
        {"GroupName": "employee"},
    )


def test_ui_amplify_resources_created():
    app = core.App()
    stack = IamAgentStack(app, "iam-agent")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::Amplify::App", 1)
    template.resource_count_is("AWS::Amplify::Branch", 1)
    template.has_resource_properties(
        "AWS::Amplify::App",
        {
            "Name": "iam-agent-ui",
            "Platform": "WEB_COMPUTE",
            "EnvironmentVariables": assertions.Match.array_with(
                [
                    {
                        "Name": "AMPLIFY_MONOREPO_APP_ROOT",
                        "Value": "app",
                    },
                    {
                        "Name": "NITRO_PRESET",
                        "Value": "aws_amplify",
                    },
                    {
                        "Name": "NUXT_PUBLIC_AGENT_WS_URL",
                        "Value": assertions.Match.any_value(),
                    },
                ],
            ),
        },
    )


def test_dynamodb_user_and_policy_tables_created():
    app = core.App()
    stack = IamAgentStack(app, "iam-agent-data")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::DynamoDB::Table", 5)
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "users-table",
            "KeySchema": [
                {
                    "AttributeName": "user_id",
                    "KeyType": "HASH",
                },
            ],
            "AttributeDefinitions": [
                {
                    "AttributeName": "user_id",
                    "AttributeType": "S",
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "customer_data",
            "KeySchema": [
                {
                    "AttributeName": "customer_id",
                    "KeyType": "HASH",
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "analytics_data",
            "KeySchema": [
                {
                    "AttributeName": "metric_id",
                    "KeyType": "HASH",
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "request_logs",
            "KeySchema": [
                {
                    "AttributeName": "request_id",
                    "KeyType": "HASH",
                },
            ],
            "AttributeDefinitions": [
                {
                    "AttributeName": "request_id",
                    "AttributeType": "S",
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )


def test_agent_only_credentials_api_created():
    app = core.App()
    stack = IamAgentStack(app, "iam-agent-api")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::ApiGateway::Method", 1)
    template.resource_count_is("AWS::ApiGatewayV2::Api", 1)
    template.resource_count_is("AWS::ApiGatewayV2::Route", 4)
    template.resource_count_is("AWS::ApiGatewayV2::Stage", 1)
    template.resource_count_is("AWS::ApiGatewayV2::Authorizer", 1)
    template.resource_count_is("AWS::Lambda::Function", 4)
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "AgentZero",
            "Handler": "broker_api.handlers.credentials.handler",
            "Environment": {
                "Variables": assertions.Match.object_like(
                    {
                        "OPENAI_SECRET_NAME": "openai-key",
                        "CUSTOMER_DATA_TABLE_NAME": assertions.Match.any_value(),
                        "ANALYTICS_DATA_TABLE_NAME": assertions.Match.any_value(),
                        "REQUEST_LOGS_TABLE_NAME": assertions.Match.any_value(),
                        "BROKER_CREDENTIALS_ROLE_ARN": assertions.Match.any_value(),
                    }
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "UserAgentWebSocketAuthorizer",
            "Handler": "agent_api.authorizer.handler",
            "Environment": {
                "Variables": assertions.Match.object_like(
                    {
                        "USER_POOL_ID": assertions.Match.any_value(),
                        "USER_POOL_CLIENT_ID": assertions.Match.any_value(),
                    }
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "UserAgentWebSocket",
            "Handler": "agent_api.handler.route_handler",
            "Environment": {
                "Variables": assertions.Match.object_like(
                    {"AGENT_WORKER_FUNCTION_NAME": assertions.Match.any_value()}
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "UserAgentWorker",
            "Handler": "agent_api.handler.worker_handler",
            "Environment": {
                "Variables": assertions.Match.object_like(
                    {
                        "CREDENTIALS_URL": assertions.Match.any_value(),
                        "OPENAI_SECRET_NAME": "openai-key",
                    }
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Action": [
                                    "secretsmanager:GetSecretValue",
                                    "secretsmanager:DescribeSecret",
                                ],
                                "Effect": "Allow",
                            }
                        )
                    ]
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Action": assertions.Match.array_with(
                                    ["dynamodb:PutItem"]
                                ),
                                "Effect": "Allow",
                                "Resource": assertions.Match.any_value(),
                            }
                        )
                    ]
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        {
            "HttpMethod": "GET",
            "AuthorizationType": "AWS_IAM",
        },
    )
    template.has_resource_properties(
        "AWS::ApiGatewayV2::Api",
        {
            "Name": "iam-agent-agent-api",
            "ProtocolType": "WEBSOCKET",
            "RouteSelectionExpression": "$request.body.action",
        },
    )
    template.has_resource_properties(
        "AWS::ApiGatewayV2::Authorizer",
        {
            "AuthorizerType": "REQUEST",
            "IdentitySource": ["route.request.querystring.token"],
            "Name": "agent-websocket-cognito-authorizer",
        },
    )
    template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {
            "RouteKey": "$connect",
            "AuthorizationType": "CUSTOM",
            "AuthorizerId": assertions.Match.any_value(),
        },
    )
    template.has_resource_properties(
        "AWS::ApiGatewayV2::Route",
        {
            "RouteKey": "requestAccess",
            "AuthorizationType": "NONE",
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Action": "execute-api:Invoke",
                                "Effect": "Allow",
                                "Resource": assertions.Match.any_value(),
                            }
                        )
                    ]
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::DynamoDB::Table",
        {
            "TableName": "policy-table",
            "KeySchema": [
                {
                    "AttributeName": "user_id",
                    "KeyType": "HASH",
                },
            ],
            "AttributeDefinitions": [
                {
                    "AttributeName": "user_id",
                    "AttributeType": "S",
                },
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Action": "sts:AssumeRole",
                                "Effect": "Allow",
                            }
                        )
                    ]
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::IAM::Policy",
        {
            "PolicyDocument": {
                "Statement": assertions.Match.array_with(
                    [
                        assertions.Match.object_like(
                            {
                                "Action": "execute-api:ManageConnections",
                                "Effect": "Allow",
                                "Resource": assertions.Match.any_value(),
                            }
                        )
                    ]
                ),
            },
        },
    )
