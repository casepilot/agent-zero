# IAM Agent Project

## TLDR

This project is a hackathon version of a Continuous Identity / Zero Standing Privilege system.

Nobody has standing AWS permissions.

To get access, a human or AI agent request flows through the Agent API and Broker API with:

- who they are
- what they want to do
- which resource they need
- why they need it

The broker loads their free-text policy from DynamoDB, gives the request and resource context to an LLM reviewer, validates the LLM output, and then either denies access or calls `sts:AssumeRole` with a tightly scoped inline session policy.

The result is temporary AWS access that auto-expires.

For agents, the broker returns temporary STS credentials.

For humans, the broker returns an AWS console sign-in URL backed by those temporary credentials.

The main idea is simple:

No standing credentials. No thousands of static IAM policies. No waiting days for IT approval. Access is decided just in time, from business context.

## Product Inspiration

This project is inspired by SGNL-style access control:

- eliminate standing access
- authorize humans and AI agents using context
- replace many static roles with human-readable policies
- make access decisions in real time
- protect cloud infrastructure and sensitive data

This hackathon project keeps the same mental model, but narrows it to AWS infrastructure, an LLM policy reviewer, and STS session policies.

## Core Mental Model

There are four main things in the system:

- principals: humans or AI agents
- resources: AWS resources like S3 buckets, DynamoDB tables, and future RDS databases
- policies: free-text business rules attached to each principal
- access requests: short-lived requests to do a specific action for a specific reason

The system does not grant permanent access.

It grants one temporary session for one approved job.

## Main Flow

1. A human calls the Agent API with Cognito auth, or an AI agent runs inside the Agent Lambda.
2. The Agent Lambda calls the Broker API credentials endpoint with IAM auth.
3. API Gateway authenticates the Agent Lambda with SigV4.
4. Broker API finds the agent principal and policy in DynamoDB.
5. Broker API builds LLM context from:
   - caller identity
   - caller type: human or agent
   - requested action
   - requested AWS resource
   - reason for access
   - free-text policy
   - known resource catalog
6. LLM reviewer returns a structured decision:
   - approve or deny
   - reason
   - allowed AWS actions
   - allowed AWS resources
   - duration
7. Validator checks the LLM output against hard allowlists and denylists.
8. If denied, broker returns a denial reason.
9. If approved, broker calls `sts:AssumeRole`.
10. Broker passes an inline session policy through the STS `Policy` parameter.
11. AWS returns temporary credentials.
12. Broker returns credentials to the Agent Lambda.
13. CloudTrail logs the role session.
14. The session expires naturally.

## Why STS Session Policies Matter

The key AWS primitive is the `Policy` parameter on `sts:AssumeRole`.

The target role can be broad, like:

- DynamoDB access role
- S3 access role
- RDS access role

But every request gets a narrower inline session policy.

AWS evaluates the final permissions as the intersection of:

- the target role permissions
- the inline session policy

So the target role can be reusable, while each session stays narrow.

This avoids creating thousands of IAM policies at runtime.

## Principal Types

### Human Users

Humans log in through Cognito.

They can be:

- admin
- employee

Admins manage users and policies.

Employees request access.

When an employee requests access, they fill out a form like:

> I need read access to the customers table to investigate ticket ABC-123.

If approved, they receive a temporary AWS console URL.

### AI Agents

Agents do not log in through the web UI.

Agents run inside AWS Lambda.

The Agent Lambda has a tightly scoped IAM policy that lets it call only the Broker API `GET /credentials` endpoint.

The Broker API reads the IAM caller identity from API Gateway request context and maps it to an agent record in DynamoDB.

If approved, the agent receives temporary STS credentials directly.

## Policy Model

Policies are stored as free text.

Examples:

- Bob is an on-call engineer and can access production infrastructure if he is on call and has an open ticket assigned to him.
- Michael is a company analyst and can have read-only access to databases for analytical reasons.
- This LLM agent is a customer support agent. It can help customers with flight information, prices, and updating their own details. It must not access unrelated customer records or sensitive internal tables.

The LLM reads these policies and decides whether a request fits.

The validator still enforces hard safety rules after the LLM responds.

The LLM is a reviewer, not the final security boundary.

## Resource Model

Resources are AWS objects managed by the CDK stack.

Examples:

- customer profile DynamoDB table
- flight booking DynamoDB table
- support ticket DynamoDB table
- sensitive internal DynamoDB table
- demo S3 bucket

The system keeps a resource catalog.

The broker includes this catalog in the LLM system prompt so the model knows:

- resource names
- resource ARNs
- what each resource is for
- which resources are sensitive
- which actions are possible

## Web UI

The web UI is built with Nuxt.

It uses Cognito auth.

Admin features:

- create human users
- create AI agent identities
- choose human or agent type
- write free-text access policies
- store policies in DynamoDB
- view access request logs

Employee features:

- request access
- explain why access is needed
- receive denial reason or console URL

Customer support demo features:

- chat with a fake customer
- ask about flight information
- ask about prices
- update the customer's own details
- show denial for prompt injection or overbroad access

The customer support demo lives in the same Nuxt app.

Example requests:

- ask about flight information
- ask about prices
- update their own details

The Nuxt app talks to an LLM agent for the customer support flow.

When the agent needs AWS data, it calls the Agent API.

The Agent Lambda calls the Broker API credentials endpoint with IAM auth.

The demo should prove both sides:

- normal customer support requests are approved
- prompt-injected or overbroad requests are denied

## Agent API

The Agent API is hosted as Lambdas behind an API Gateway WebSocket API.

The frontend connects to the Agent API WebSocket endpoint with Cognito auth.
The Agent API calls the Broker API credentials endpoint internally.

Human callers use Cognito auth to call the Agent API.

The Agent Lambda calls the Broker API `GET /credentials` endpoint with IAM auth.

The broker returns either:

- temporary STS credentials
- a denial reason

The Agent Lambda then uses the temporary credentials to perform the approved AWS action.

## Broker API

The Broker API is the core backend.

It runs as Lambda behind API Gateway.

The credentials endpoint supports one auth mode:

- IAM auth for the Agent Lambda

Responsibilities:

- authenticate the Agent Lambda caller context
- load principal policy from DynamoDB
- load resource catalog
- call LLM reviewer
- validate structured LLM output
- create session policy
- call STS AssumeRole
- return credentials or console URL
- log request, decision, and session metadata

## LLM Reviewer

The LLM reviewer receives structured input.

It should return structured JSON only.

Expected output:

- decision: approve or deny
- reason
- allowed actions
- allowed resources
- duration seconds
- session policy draft

The LLM should never directly call AWS.

It only proposes a decision and a scoped policy.

## Validator

The validator is a deterministic safety layer.

It checks:

- JSON schema is valid
- requested duration is within allowed range
- actions are in the allowlist
- resources are in the resource catalog
- denied actions are not present
- sensitive resources require stricter conditions
- session policy does not contain wildcards unless explicitly allowed
- policy size is within AWS limits

If validation fails, access is denied.

## Audit Model

Every request should be logged.

Logs should include:

- principal id
- principal type
- requested resource
- requested action
- stated reason
- LLM decision
- validator result
- generated session name
- assumed role ARN
- duration
- timestamp

CloudTrail provides the AWS-side audit trail for the assumed role session.

The app should also store broker-side request history in DynamoDB.

## Security Rules For The Hackathon

- The LLM never gets AWS credentials.
- The LLM never directly calls AWS.
- The LLM output must be validated.
- Broker-generated policies should avoid `*`.
- Sensitive resources should be denied by default.
- Agent access should return credentials only for the approved action.
- Human access should prefer short console sessions.
- Every decision should be logged.
- Demo resources should be isolated from real AWS resources.

## Demo Story

The strongest demo path:

1. Admin creates Bob as a human employee.
2. Admin gives Bob a free-text on-call engineer policy.
3. Bob requests temporary production read access with a valid ticket reason.
4. Broker approves and returns a short-lived console URL.
5. Admin creates a customer support AI agent.
6. Admin gives the agent a free-text customer support policy.
7. A customer asks the Nuxt chat app to update their own flight details.
8. Agent calls the Agent API.
9. Agent Lambda calls Broker API.
10. Broker approves narrow DynamoDB access.
11. Agent updates the allowed record.
12. Customer tries prompt injection asking for sensitive internal data.
13. Agent calls the Agent API or attempts access.
14. Broker denies because the request does not match policy.

## What This Proves

This proves that access can be:

- contextual
- temporary
- least privilege
- usable by humans
- usable by AI agents
- auditable
- based on human-readable policy
- enforced with real AWS primitives

The core trick is not creating more IAM roles.

The core trick is using a small number of broad target roles, then narrowing every session with STS inline session policies.
