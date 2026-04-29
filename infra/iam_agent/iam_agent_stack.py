from aws_cdk import Stack
from constructs import Construct

from iam_agent.constructs.auth import Auth
from iam_agent.constructs.frontend_hosting import FrontendHosting


class IamAgentStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.auth = Auth(self, "Auth")
        self.frontend_hosting = FrontendHosting(self, "FrontendHosting")
