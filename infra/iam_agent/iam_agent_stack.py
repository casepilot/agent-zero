from aws_cdk import Stack
from constructs import Construct

from iam_agent.constructs.auth import Auth
from iam_agent.constructs.broker_api import BrokerApi
from iam_agent.constructs.data import Data
from iam_agent.constructs.frontend_hosting import FrontendHosting


class IamAgentStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.auth = Auth(self, "Auth")
        self.data = Data(self, "Data")
        self.broker_api = BrokerApi(
            self,
            "BrokerApi",
            user_pool=self.auth.user_pool,
            users_table=self.data.users_table,
            policy_table=self.data.policy_table,
            customer_data_table=self.data.customer_data_table,
            analytics_data_table=self.data.analytics_data_table,
        )
        self.frontend_hosting = FrontendHosting(self, "FrontendHosting")
