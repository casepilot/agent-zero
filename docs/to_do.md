# To Do

1. [x] Spin up a Python CDK app in `infra/`.
2. [x] Create the base CDK stack and environment config.
3. [x] Add DynamoDB tables for principals, policies, request logs, and demo app data.
4. [x] Add Cognito user pool, app client, and groups for `admin` and `employee`.
5. [x] Add broad target IAM roles for DynamoDB, S3, and future AWS resource access.
6. [ ] Create `services/shared/` for shared types, schemas, errors, and logging helpers.
7. [x] Create `services/broker-api/` with a basic Lambda handler.
8. [x] Wire the Broker API Lambda behind API Gateway.
9. [x] Add Cognito auth for human requests to the Agent API.
10. [x] Add IAM auth for Agent Lambda requests to the Broker API credentials endpoint.
11. [x] Add principal and policy lookup from DynamoDB. Agent API forwards the trusted Cognito sub to Broker API as the principal user_id.
12. [x] Add a resource catalog that describes stack resources and their ARNs.
13. [x] Add the LLM reviewer with structured JSON output.
14. [x] Add deterministic validation for LLM decisions, allowed actions, resources, durations, and deny rules.
15. [x] Add session policy generation for approved requests.
16. [x] Add `sts:AssumeRole` with the inline session policy.
17. [x] Add AWS console sign-in URL generation for human users.
18. [x] Add broker-side request logging to DynamoDB.
19. [x] Create `services/agent-api/` with Lambdas behind an API Gateway WebSocket API.
20. [x] Add agent tools that request broker access and then perform approved DynamoDB actions.
21. [x] Create the single Nuxt app in `app/`. Skeleton created with Tailwind CSS and shadcn-vue.
24. [x] Add the customer support demo chat screen to the single Nuxt app. Live desktop chat UI is in place on `/chat` with Agent API WebSocket streaming.
25. [x] Add Amplify hosting infrastructure for `app/`.
26. [x] Remove the separate support agent UI.
<<<<<<< HEAD
27. [x] Connect the Nuxt chat flow to the customer support LLM agent. The Nuxt chat now consumes rich Agent API WebSocket streaming, including markers, reasoning summaries, safe tool result summaries, markdown-rendered final answer deltas, and end-turn events.
28. [ ] Add demo data for customers, flights, bookings, and sensitive internal records. bank_customer_profiles, bank_operational_metrics, bank_transactions, and bank_balances are bootstrapped; flights, bookings, and sensitive internal records remain.
29. [ ] Add scripts for seeding demo data and printing deployed stack outputs. Demo user bootstrap now seeds and tears down users, policies, bank_customer_profiles, bank_operational_metrics, bank_transactions, and bank_balances.
=======
27. [ ] Connect the Nuxt chat flow to the customer support LLM agent. Agent API now has rich WebSocket streaming for OpenAI Agents SDK turns, including markers, reasoning summaries, tool calls, tool results, final answer deltas, and end-turn events.
28. [x] Add bank demo data. Final demo data now seeds bank_customer_profiles, bank_operational_metrics, bank_transactions, and bank_balances with bank-only production-style records.
29. [x] Add scripts for seeding demo data and printing deployed stack outputs. Demo bootstrap now clears old demo data, deletes old demo Cognito users, and seeds bank users, policies, balances, transactions, customer profiles, and operational metrics.
>>>>>>> a63f2be74b445584013c259c51be4e3672438b69
30. [ ] Write docs for architecture, API usage, threat model, and the hackathon demo script. Agent WebSocket streaming contract is documented in `docs/api.md`.
31. [ ] Run an end-to-end demo path for human approval, agent approval, and agent denial.
32. [x] Add local automation to refresh `docs/layout.md` with Codex every 30 minutes and run git stage, commit, and pull every 5 minutes.
33. [x] Wire the Nuxt login screen to Cognito with the Amplify client SDK and protect every non-login route.

## Frontend Hosting

1. [ ] Push this monorepo to GitHub so Amplify can connect to the repository.
2. [ ] Deploy `IamAgentStack` with CDK so the Amplify app and branch are created.
3. [ ] Connect the Amplify app to the GitHub repo if CDK cannot attach the repo automatically.
4. [ ] Confirm Amplify builds `app/` from the monorepo root.
5. [x] Add Amplify hosting for `app/`.
6. [ ] Confirm the hosted single UI loads from the Amplify default domain.
