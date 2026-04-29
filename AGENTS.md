# Agent Instructions

Use simple language.

Before making project changes, read these files:

1. `docs/project.md`
   - Use this to understand what the product does.
   - Use this for the project purpose, context, access model, and demo story.

2. `docs/layout.md`
   - Use this to understand the target repo structure.
   - Follow this layout when creating new folders and files.

3. `docs/to_do.md`
   - Use this to understand the current build plan.
   - When the user asks what is next, refer to this file.
   - When making plans, use this file as the source of truth.
   - Update this file when tasks are completed or when the build plan changes.

Keep implementation choices aligned with these docs unless the user gives newer instructions.

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
