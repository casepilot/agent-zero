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

        self.customer_data_table = dynamodb.Table(
            self,
            "CustomerDataTable",
            table_name="customer_data",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.analytics_data_table = dynamodb.Table(
            self,
            "AnalyticsDataTable",
            table_name="analytics_data",
            partition_key=dynamodb.Attribute(
                name="metric_id",
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
            "CustomerDataTableName",
            value=self.customer_data_table.table_name,
        )
        CfnOutput(
            self,
            "AnalyticsDataTableName",
            value=self.analytics_data_table.table_name,
        )
        CfnOutput(
            self,
            "RequestLogsTableName",
            value=self.request_logs_table.table_name,
        )
