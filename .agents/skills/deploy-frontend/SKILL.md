---
name: deploy-frontend
description: Deploy the Agent Zero frontend hosting infrastructure to AWS Amplify. Use when the user says "deploy frontend", "frontend deploy", "deploy the UI", "publish frontend", "deploy Amplify", or asks to run the frontend deployment for this repo.
---

# Deploy Frontend

## Workflow

Run the project-local deploy wrapper from the repository root:

```bash
scripts/deploy_frontend.sh
```

Do not stop at a plan when the user asks to deploy. Execute the script.

The script deploys:

- CDK app directory: `infra/`
- Stack: `IamAgentStack`
- AWS profile: `openai-hackathon`
- Amplify app root: `app/`

## Guardrails

- Use `/Users/deepak/hackathon/agent-zero` as the working directory.
- Do not deploy another stack.
- Do not switch AWS profiles unless the user explicitly asks.
- If CDK, AWS, or network access requires approval outside the sandbox, request approval for the same script and rerun it.
- If `cdk` is missing, report that the AWS CDK CLI is not installed or not on `PATH`.
- If AWS credentials fail, remind the user to check `--profile openai-hackathon`.
- If Amplify reports that GitHub is not connected, state that the CDK app exists but the Amplify repository connection still needs setup.

## Reporting

After the script exits, report whether the deploy succeeded. Include the important CDK outputs, especially Amplify app ID and default domain if they appear.
