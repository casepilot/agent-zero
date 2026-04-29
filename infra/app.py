#!/usr/bin/env python3

import aws_cdk as cdk

from iam_agent.config.resources import AWS_ACCOUNT_ID, AWS_REGION
from iam_agent.iam_agent_stack import IamAgentStack


app = cdk.App()
IamAgentStack(
    app,
    "IamAgentStack",
    env=cdk.Environment(account=AWS_ACCOUNT_ID, region=AWS_REGION),
)

app.synth()
