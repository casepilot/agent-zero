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
            bank_customer_profiles_table=self.data.bank_customer_profiles_table,
            bank_operational_metrics_table=self.data.bank_operational_metrics_table,
            bank_transactions_table=self.data.bank_transactions_table,
            bank_balances_table=self.data.bank_balances_table,
            support_requests_table=self.data.support_requests_table,
            request_logs_table=self.data.request_logs_table,
            user_pool_client_id=self.auth.user_pool_client.ref,
        )
        self.frontend_hosting = FrontendHosting(
            self,
            "FrontendHosting",
            agent_websocket_url=self.broker_api.agent_websocket_url,
        )
