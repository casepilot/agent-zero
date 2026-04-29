# Agent Instructions

Use simple language.

Before making project changes, read `README.md`.

Use it to understand:

- what the product does
- the project purpose and access model
- the current credential flow
- the repo layout
- the demo story

Keep implementation choices aligned with the README unless the user gives newer instructions.

## CDK Deploy

The CDK app lives in `infra/`.

The stack is named `IamAgentStack`.

Keep CDK as one stack.

Add new infrastructure as constructs inside `IamAgentStack`.

Do not create extra CDK stacks unless the user explicitly asks for it.

Reason: this keeps deploys simple and avoids cross-stack dependency problems that can brick or block stack updates.

The target AWS account is:

```text
338375260114
```

The target AWS region is:

```text
ap-southeast-2
```

Use the AWS profile:

```text
openai-hackathon
```

Bootstrap command:

```bash
cd infra
cdk bootstrap --profile openai-hackathon
```

Deploy command:

```bash
cd infra
cdk deploy IamAgentStack --profile openai-hackathon
```

If CDK says no credentials are configured, check for typos in `--profile openai-hackathon`.
