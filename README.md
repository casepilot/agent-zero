 # Agent Zero

  **Zero standing permissions for your cloud.**

  Agent Zero is a continuous, just-in-time access broker for AWS. Humans and AI agents
  get the access they need, when they need it, for only as long as they need it,
  and nothing more. No standing IAM users. No thousands of static policies. No
  multi-day waits on legal, security, or IT to approve a one-off task.

  ## The problem

  Cloud identity is broken in two directions at once:

  - **Humans** sit on permanent, over-broad IAM roles because nobody has time to
    scope them per task. So every laptop is a blast radius.
  - **AI agents** are about to make this 100x worse. Every new agent today gets
    handed a static API key or a long-lived role, and it keeps that access
    forever, regardless of what it's actually doing in any given moment.

  Meanwhile, the access request process is stuck in a ticketing queue. An
  engineer needs read access to one table to debug one ticket and waits two days
  for an approval chain that nobody actually reads.

  ## What Agent Zero does

  Every request, from a human or an agent, flows through a broker that asks
  four questions in plain English:

  1. Who are you?
  2. What do you want to do?
  3. Which resource do you need?
  4. Why do you need it?

  The broker pulls the principal's free-text policy from DynamoDB, hands the
  request to an LLM reviewer with the resource catalog as context, runs the
  LLM's structured decision through a deterministic validator, and if the
  request is approved, calls `sts:AssumeRole` with a tightly scoped **inline
  session policy**.

  The result is one short-lived AWS session, scoped to one action on one
  resource, that auto-expires. CloudTrail logs the whole thing.

  - **Humans** get a one-click AWS console sign-in URL backed by those temporary
    credentials.
  - **AI agents** get raw STS credentials returned to the calling Lambda.

  The trick that makes this work at scale: a small set of broad target roles
  (DynamoDB, S3, RDS) get narrowed at request time by an inline session policy.
  AWS evaluates the intersection, so you don't have to mint a new IAM policy
  per task.

  ## Why this matters for AI agents

  Cloud agents are hard to permission safely. The organization wants them to
  have enough access to help end users and complete real work, but nobody wants
  to hand an agent a huge policy up front. Prompt injection, bad tool calls, or
  a confused conversation can turn broad standing access into a serious
  security incident.

  Static credentials are the wrong primitive for autonomous agents. An agent
  that's allowed to read customer profiles to answer a support question should
  not also be able to read that customer's payment history, dump the whole
  table, or touch an unrelated table, even though the underlying IAM role
  might technically permit all of it.

  Agent Zero gives teams a safer way to deploy agents in the cloud. There are
  zero standing policies for the agent to abuse. When access is needed, the
  broker makes a just-in-time decision and returns short-lived credentials
  scoped to the exact approved job. Prompt injection that tries to widen the
  agent's access gets denied at the broker, not at the application layer.

  ## What's in this repo

  infra/                CDK app, single IamAgentStack with all AWS resources
  services/broker-api/  Broker Lambda, LLM reviewer, validator, STS AssumeRole
  services/agent-api/   Agent Lambda, WebSocket API for the customer support agent
  app/                  Nuxt frontend, admin console, access requests, demo chat
  scripts/              Bootstrap and teardown helpers for demo data
  docs/                 Project docs, architecture, API contract

  ---

  ## Getting started

  Target AWS account: `338375260114` · region: `ap-southeast-2` · profile:
  `openai-hackathon`. Adjust if you're forking.

  ### 1. Deploy the infrastructure (CDK)

  First-time only, bootstrap CDK in the target account:

  ```bash
  cd infra
  cdk bootstrap --profile openai-hackathon

  Then deploy the stack:

  cd infra
  cdk deploy IamAgentStack --profile openai-hackathon

  This provisions the DynamoDB tables (users-table, policy-table, request
  logs, demo bank data), the Cognito user pool and groups, the broker and agent
  Lambdas, the API Gateway endpoints (REST + WebSocket), the broad target IAM
  roles, and the Amplify hosting app for the frontend.

  2. Bootstrap the demo data

  After the CDK deploy finishes, seed Cognito and DynamoDB from the repo root:

  python3 scripts/bootstrap_demo_users.py bootstrap --profile openai-hackathon

  This creates the demo Cognito users, adds them to the right groups, writes
  their records into users-table, seeds the bank demo data
  (bank_customer_profiles, bank_balances, bank_transactions,
  bank_operational_metrics, support-requests), and writes the free-text policies into
  policy-table.

  Seeded users:

  ┌────────────────────────┬──────────┬───────┐
  │       Email / id       │   Role   │ Type  │
  ├────────────────────────┼──────────┼───────┤
  │ admin@example.com      │ admin    │ human │
  ├────────────────────────┼──────────┼───────┤
  │ employee1@example.com  │ employee │ human │
  ├────────────────────────┼──────────┼───────┤
  │ customer_support_agent │ employee │ agent │
  └────────────────────────┴──────────┴───────┘

  To tear it back down:

  python3 scripts/bootstrap_demo_users.py teardown --execute --profile openai-hackathon

  3. Host the frontend on Amplify

  The Nuxt app in app/ is wired to AWS Amplify Hosting via the CDK stack.

  1. Push this repo to GitHub.
  2. Open the Amplify app created by IamAgentStack in the AWS console and
  connect it to the GitHub repo if CDK didn't attach it automatically.
  3. Confirm Amplify builds from the monorepo root with app/ as the app
  directory.
  4. Visit the Amplify default domain once the build finishes.

  Local dev alternative:

  cd app
  npm install
  npm run dev

  4. Log in and request access

  Open the hosted Amplify URL (or http://localhost:3000 for local). The login
  screen is wired to Cognito.

  - As admin@example.com, manage users, write free-text policies, view
  the access request log.
  - As employee1@example.com, request temporary AWS access by saying
  what you need and why. Approved requests come back as a one-click AWS
  console sign-in URL. Denied requests come back with the reason.
  - As any user, on /chat, talk to the customer support AI agent. The
  agent calls the Agent API over WebSocket, which calls the Broker API for
  every action it wants to take. Try asking it to update your own flight
  details (approved). Try a prompt injection asking it to read another
  customer's record (denied at the broker).
