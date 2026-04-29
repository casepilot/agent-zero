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


def test_support_agent_amplify_resources_created():
    app = core.App()
    stack = IamAgentStack(app, "iam-agent")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::Amplify::App", 1)
    template.resource_count_is("AWS::Amplify::Branch", 1)
    template.has_resource_properties(
        "AWS::Amplify::App",
        {
            "Name": "iam-agent-support-agent",
            "Platform": "WEB_COMPUTE",
            "EnvironmentVariables": assertions.Match.array_with(
                [
                    {
                        "Name": "AMPLIFY_MONOREPO_APP_ROOT",
                        "Value": "apps/support-agent",
                    },
                    {
                        "Name": "NITRO_PRESET",
                        "Value": "aws_amplify",
                    },
                ],
            ),
        },
    )


def test_dynamodb_user_and_policy_tables_created():
    app = core.App()
    stack = IamAgentStack(app, "iam-agent-data")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::DynamoDB::Table", 2)
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


def test_agent_only_credentials_api_created():
    app = core.App()
    stack = IamAgentStack(app, "iam-agent-api")
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::ApiGateway::RestApi", 1)
    template.resource_count_is("AWS::ApiGateway::Method", 2)
    template.resource_count_is("AWS::Lambda::Function", 2)
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "AgentZero",
            "Handler": "broker_api.handlers.credentials.handler",
            "Environment": {
                "Variables": assertions.Match.object_like(
                    {"OPENAI_SECRET_NAME": "openai-key"}
                ),
            },
        },
    )
    template.has_resource_properties(
        "AWS::Lambda::Function",
        {
            "FunctionName": "UserAgent",
            "Handler": "agent_api.handler.handler",
            "Environment": {
                "Variables": assertions.Match.object_like(
                    {"OPENAI_SECRET_NAME": "openai-key"}
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
        "AWS::ApiGateway::Method",
        {
            "HttpMethod": "GET",
            "AuthorizationType": "AWS_IAM",
        },
    )
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        {
            "HttpMethod": "POST",
            "AuthorizationType": "COGNITO_USER_POOLS",
            "AuthorizerId": assertions.Match.any_value(),
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
