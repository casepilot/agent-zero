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
