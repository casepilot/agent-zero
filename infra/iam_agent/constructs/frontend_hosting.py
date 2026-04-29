from aws_cdk import CfnOutput
from aws_cdk import aws_amplify as amplify
from constructs import Construct

from iam_agent.config.resources import APP_ROOT


class FrontendHosting(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        agent_websocket_url: str,
    ) -> None:
        super().__init__(scope, construct_id)

        build_spec = f"""version: 1
applications:
  - appRoot: {APP_ROOT}
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

        self.ui_app = amplify.CfnApp(
            self,
            "UiAmplifyApp",
            name="iam-agent-ui",
            platform="WEB_COMPUTE",
            build_spec=build_spec,
            environment_variables=[
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="AMPLIFY_MONOREPO_APP_ROOT",
                    value=APP_ROOT,
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="NITRO_PRESET",
                    value="aws_amplify",
                ),
                amplify.CfnApp.EnvironmentVariableProperty(
                    name="NUXT_PUBLIC_AGENT_WS_URL",
                    value=agent_websocket_url,
                ),
            ],
        )

        self.ui_branch = amplify.CfnBranch(
            self,
            "UiMainBranch",
            app_id=self.ui_app.attr_app_id,
            branch_name="main",
            enable_auto_build=True,
            stage="DEVELOPMENT",
        )

        CfnOutput(
            self,
            "UiAmplifyAppId",
            value=self.ui_app.attr_app_id,
        )
        CfnOutput(
            self,
            "UiAmplifyDefaultDomain",
            value=self.ui_app.attr_default_domain,
        )
