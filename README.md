# IAM Agent

Hackathon version of a Continuous Identity / Zero Standing Privilege system for AWS.

## First Step: Deploy Infrastructure

The CDK app lives in `infra/`. Deploy the stack before running any data bootstrap commands.

```bash
cd infra
cdk deploy IamAgentStack --profile openai-hackathon
```

If this is the first deploy into the AWS account, bootstrap CDK first:

```bash
cd infra
cdk bootstrap --profile openai-hackathon
```

The target AWS account is `338375260114` and the target region is `ap-southeast-2`.

## Bootstrap Demo Data

After the CDK deploy finishes, run the demo user bootstrap from the repo root:

```bash
python3 scripts/bootstrap_demo_users.py bootstrap --profile openai-hackathon
```

This creates the human Cognito users, adds them to Cognito groups, and writes users into `users-table`.

Seeded users:

- `admin@example.com`, role `admin`, human user
- `employee1@example.com`, role `employee`, human user
- `customer_support_agent`, role `employee`, agent user in DynamoDB only

The `policy-table` is left empty.

## Tear Down Demo Data

Preview what will be removed:

```bash
python3 scripts/bootstrap_demo_users.py teardown --profile openai-hackathon
```

Actually delete the seeded demo users:

```bash
python3 scripts/bootstrap_demo_users.py teardown --execute --profile openai-hackathon
```

This removes the seeded Cognito users and their matching `users-table` records. It also removes the `customer_support_agent` record from `users-table`.
