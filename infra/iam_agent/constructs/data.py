from aws_cdk import CfnOutput, RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct


class Data(Construct):
    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)

        self.users_table = dynamodb.Table(
            self,
            "UsersTable",
            table_name="users-table",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.policy_table = dynamodb.Table(
            self,
            "PolicyTable",
            table_name="policy-table",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.bank_customer_profiles_table = dynamodb.Table(
            self,
            "CustomerDataTable",
            table_name="bank_customer_profiles",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.bank_operational_metrics_table = dynamodb.Table(
            self,
            "AnalyticsDataTable",
            table_name="bank_operational_metrics",
            partition_key=dynamodb.Attribute(
                name="metric_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.bank_transactions_table = dynamodb.Table(
            self,
            "TransactionsTable",
            table_name="bank_transactions",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="transaction_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.bank_balances_table = dynamodb.Table(
            self,
            "AccountDataTable",
            table_name="bank_balances",
            partition_key=dynamodb.Attribute(
                name="user_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.request_logs_table = dynamodb.Table(
            self,
            "RequestLogsTable",
            table_name="request_logs",
            partition_key=dynamodb.Attribute(
                name="request_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        CfnOutput(
            self,
            "UsersTableName",
            value=self.users_table.table_name,
        )
        CfnOutput(
            self,
            "PolicyTableName",
            value=self.policy_table.table_name,
        )
        CfnOutput(
            self,
            "BankCustomerProfilesTableName",
            value=self.bank_customer_profiles_table.table_name,
        )
        CfnOutput(
            self,
            "BankOperationalMetricsTableName",
            value=self.bank_operational_metrics_table.table_name,
        )
        CfnOutput(
            self,
            "BankTransactionsTableName",
            value=self.bank_transactions_table.table_name,
        )
        CfnOutput(
            self,
            "BankBalancesTableName",
            value=self.bank_balances_table.table_name,
        )
        CfnOutput(
            self,
            "RequestLogsTableName",
            value=self.request_logs_table.table_name,
        )
