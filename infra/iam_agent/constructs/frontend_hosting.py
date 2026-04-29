from aws_cdk import CfnOutput
from aws_cdk import aws_amplify as amplify
from constructs import Construct

from iam_agent.config.resources import SUPPORT_AGENT_APP_ROOT


class FrontendHosting(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        build_spec = f"""version: 1
applications:
  - appRoot: {SUPPORT_AGENT_APP_ROOT}
    frontend:
      phases:
        preBuild:
          commands:
            - corepack enable
            - pnpm install --frozen-lockfile
        build:
          commands:
            - pnpm run build
      artifacts:
        baseDirectory: .amplify-hosting
        files:
          - "**/*"
      cache:
        paths:
          - node_modules/**/*
"""

        self.support_agent_app = amplify.CfnApp(
            self,
            "SupportAgentAmplifyApp",
            name="iam-agent-support-agent",
            platform="WEB_COMPUTE",
            build_spec=build_spec,
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="AMPLIFY_MONOREPO_APP_ROOT",
                    value=SUPPORT_AGENT_APP_ROOT,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="NITRO_PRESET",
                    value="aws_amplify",
                ),
            ],
        )

        self.support_agent_branch = amplify.CfnBranch(
            self,
            "SupportAgentMainBranch",
            app_id=self.support_agent_app.attr_app_id,
            branch_name="main",
            enable_auto_build=True,
            stage="DEVELOPMENT",
        )

        CfnOutput(
            self,
            "SupportAgentAmplifyAppId",
            value=self.support_agent_app.attr_app_id,
        )
        CfnOutput(
            self,
            "SupportAgentAmplifyDefaultDomain",
            value=self.support_agent_app.attr_default_domain,
        )
