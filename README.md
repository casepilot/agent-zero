# Agent Zero

**Zero standing permissions for your cloud.**

Agent Zero is a continuous, just-in-time access broker for AWS. Humans and AI
agents get the access they need, when they need it, for only as long as they
need it, and nothing more. No standing IAM users. No thousands of static
policies. No multi-day waits on legal, security, or IT to approve a one-off
task.

## The Problem

Cloud identity is broken in two directions at once:

- **Humans** sit on permanent, over-broad IAM roles because nobody has time to
  scope them per task. So every laptop is a blast radius.
- **AI agents** are about to make this 100x worse. Every new agent today gets
  handed a static API key or a long-lived role, and it keeps that access
  forever, regardless of what it is actually doing in any given moment.

Meanwhile, the access request process is stuck in a ticketing queue. An
engineer needs read access to one table to debug one ticket and waits two days
for an approval chain that nobody actually reads.

## What Agent Zero Does

Every request, from a human or an agent, flows through a broker that asks four
questions in plain English:

1. Who are you?
2. What do you want to do?
3. Which resource do you need?
4. Why do you need it?

The broker pulls the principal's free-text policy from DynamoDB, hands the
request to an LLM reviewer with the resource catalog as context, runs the LLM's
structured decision through a deterministic validator, and if the request is
approved, calls `sts:AssumeRole` with a tightly scoped inline session policy.

The result is one short-lived AWS session, scoped to one action on one resource,
that auto-expires. CloudTrail logs the whole thing.

- **Humans** get a one-click AWS console sign-in URL backed by those temporary
  credentials when the request is staff-facing.
- **AI agents** get raw STS credentials returned to the calling Lambda.

The trick that makes this work at scale: a small set of broad target roles
gets narrowed at request time by an inline session policy. AWS evaluates the
intersection, so you do not have to mint a new IAM policy per task.

## Why This Matters For AI Agents

Cloud agents are hard to permission safely. The organization wants them to have
enough access to help end users and complete real work, but nobody wants to hand
an agent a huge policy up front. Prompt injection, bad tool calls, or a confused
conversation can turn broad standing access into a serious security incident.

Static credentials are the wrong primitive for autonomous agents. An agent that
is allowed to read customer profiles to answer a support question should not
also be able to read that customer's payment history, dump the whole table, or
touch an unrelated table, even though the underlying IAM role might technically
permit all of it.

Agent Zero gives teams a safer way to deploy agents in the cloud. There are
zero standing policies for the agent to abuse. When access is needed, the broker
makes a just-in-time decision and returns short-lived credentials scoped to the
exact approved job. Prompt injection that tries to widen the agent's access gets
denied at the broker, not at the application layer.

## Main Mental Model

There are four core objects:

- **Principals:** humans and AI agents, stored in `users-table` and backed by
  Cognito for signed-in human users.
- **Policies:** free-text business rules stored in `policy-table`, keyed by
  `user_id`.
- **Resources:** known AWS resources from the live resource catalog, including
  bank customer profiles, balances, transactions, support requests, operational
  metrics, the user directory, the policy table, and the Cognito user pool.
- **Access requests:** short-lived requests with a trusted `user_id`, a reason,
  and staff/customer context.

The current repo flow works like this:

1. A user logs in through Cognito in the Nuxt app.
2. The frontend opens the Agent API WebSocket with the Cognito access token in
   the `token` query string.
3. The WebSocket authorizer validates the Cognito access token and passes the
   trusted `user_id`, username, client id, and groups into the route context.
4. The frontend sends a `requestAccess` WebSocket message with the user's prompt.
5. The WebSocket route Lambda validates the route and asynchronously invokes the
   `UserAgentWorker` Lambda.
6. The worker runs the OpenAI agent with trusted Cognito context. The agent can
   call tools such as `request_aws_access`, `run_dynamodb_operation`,
   `write_user_policy`, and `create_cognito_user`.
7. When the agent needs AWS access, it calls the Broker API `GET /credentials`
   endpoint with `user_id`, `reason`, and `is_staff`.
8. The Agent worker signs that broker request with AWS SigV4. API Gateway
   protects `/credentials` with IAM auth, so callers cannot hit it anonymously.
9. The Broker Lambda rejects caller-selected resources. The caller supplies the
   identity and reason, but the broker chooses the resource grants.
10. The Broker Lambda loads the principal profile from `users-table` and the
    free-text policy from `policy-table`.
11. The Broker Lambda builds the live resource catalog from environment-backed
    table names, table ARNs, and the Cognito user pool ARN.
12. The LLM reviewer decides whether the reason fits the policy and returns a
    structured access decision with approved grants, AWS actions, resource keys,
    and duration.
13. The deterministic validator checks that decision against hard rules,
    allowed actions, allowed resources, duration limits, and sensitive resource
    constraints.
14. If the request is denied, the broker logs the denial and returns the reason.
15. If the request is approved, the broker builds an inline STS session policy
    from the approved grants. Customer-owned tables such as balances,
    transactions, and support requests are scoped with `dynamodb:LeadingKeys`
    for the signed-in `user_id`.
16. The broker calls `sts:AssumeRole` into the reusable broker credentials role
    with that inline session policy and the approved duration.
17. The broker writes the decision, policy snapshot, grants, session policy,
    target role, and credential expiration to the request log table.
18. The broker returns temporary credentials to the Agent worker. For staff
    requests, it can also return a console login URL.
19. The Agent worker retries the approved tool call with the temporary
    credentials, streams tool results and answer deltas back over the WebSocket,
    and then the credentials expire naturally.

The important boundary is that the chat agent does not decide authorization.
The Agent worker can ask for access, but Agent Zero, the Broker API, decides
what access is allowed and mints the short-lived credentials.

## What's In This Repo

```text
infra/                CDK app, single IamAgentStack with all AWS resources
services/broker-api/  Broker Lambda, LLM reviewer, validator, STS AssumeRole
services/agent-api/   Agent Lambda, WebSocket API for the customer support agent
app/                  Nuxt frontend, login, chat, and WebSocket client
scripts/              Bootstrap and teardown helpers for demo data
```

## Getting Started

Target AWS account: `338375260114`

Target AWS region: `ap-southeast-2`

AWS profile: `openai-hackathon`

### 1. Deploy The Infrastructure

First-time only, bootstrap CDK in the target account:

```bash
cd infra
cdk bootstrap --profile openai-hackathon
```

Then deploy the stack:

```bash
cd infra
cdk deploy IamAgentStack --profile openai-hackathon
```

This provisions the DynamoDB tables, Cognito user pool and groups, Broker API,
Agent API WebSocket, broad reusable IAM role, request logs, and Amplify hosting
app for the frontend.

### 2. Bootstrap The Demo Data

After the CDK deploy finishes, seed Cognito and DynamoDB from the repo root:

```bash
python3 scripts/bootstrap_demo_users.py bootstrap --profile openai-hackathon
```

This creates demo Cognito users, adds them to groups, writes their records into
`users-table`, seeds the bank demo data, and writes free-text policies into
`policy-table`.

Seeded users:

```text
Email or id             Role      Type
admin@example.com       admin     human
employee1@example.com   employee  human
customer_support_agent  employee  agent
```

To tear it back down:

```bash
python3 scripts/bootstrap_demo_users.py teardown --execute --profile openai-hackathon
```

### 3. Host The Frontend On Amplify

The Nuxt app in `app/` is wired to AWS Amplify Hosting via the CDK stack.

1. Push this repo to GitHub.
2. Open the Amplify app created by `IamAgentStack` in the AWS console and
   connect it to the GitHub repo if CDK did not attach it automatically.
3. Confirm Amplify builds from the monorepo root with `app/` as the app
   directory.
4. Visit the Amplify default domain once the build finishes.

Local dev alternative:

```bash
cd app
npm install
npm run dev
```

### 4. Log In And Request Access

Open the hosted Amplify URL, or `http://localhost:3000` for local dev. The
login screen is wired to Cognito.

- As `admin@example.com`, manage users, write free-text policies, and view the
  access request log.
- As `employee1@example.com`, request temporary AWS access by saying what you
  need and why.
- As any signed-in user, use `/chat` to talk to the customer support AI agent.
  Try a normal customer support request, then try a prompt injection asking it
  to read another customer's record. The overbroad request should be denied at
  the broker.
