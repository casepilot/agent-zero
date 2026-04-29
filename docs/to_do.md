# To Do

1. [x] Spin up a Python CDK app in `infra/`.
2. [x] Create the base CDK stack and environment config.
3. [ ] Add DynamoDB tables for principals, policies, request logs, and demo app data. Users, policy, customer_data, and analytics_data tables are added; request logs remain.
4. [x] Add Cognito user pool, app client, and groups for `admin` and `employee`.
5. [x] Add broad target IAM roles for DynamoDB, S3, and future AWS resource access.
6. [ ] Create `services/shared/` for shared types, schemas, errors, and logging helpers.
7. [x] Create `services/broker-api/` with a basic Lambda handler.
8. [x] Wire the Broker API Lambda behind API Gateway.
9. [x] Add Cognito auth for human requests to the Agent API.
10. [x] Add IAM auth for Agent Lambda requests to the Broker API credentials endpoint.
11. [x] Add principal and policy lookup from DynamoDB. Broker currently uses a temporary trusted `user_id` query param from Agent API; remove this after Agent API forwards the Cognito sub.
12. [x] Add a resource catalog that describes stack resources and their ARNs.
13. [x] Add the LLM reviewer with structured JSON output.
14. [x] Add deterministic validation for LLM decisions, allowed actions, resources, durations, and deny rules.
15. [x] Add session policy generation for approved requests.
16. [x] Add `sts:AssumeRole` with the inline session policy.
17. [x] Add AWS console sign-in URL generation for human users.
18. [ ] Add broker-side request logging to DynamoDB.
19. [x] Create `services/agent-api/` with a Lambda behind API Gateway.
20. [ ] Add agent tools that request broker access and then perform approved DynamoDB actions.
21. [x] Create the single Nuxt app in `app/`. Skeleton created with Tailwind CSS and shadcn-vue.
22. [ ] Add Nuxt admin screens for creating humans, agents, and free-text policies.
23. [ ] Add Nuxt employee screens for requesting access and receiving console URLs.
24. [x] Add the customer support demo chat screen to the single Nuxt app. Static desktop chat UI is in place on dynamic chat routes with simulated streaming.
25. [x] Add Amplify hosting infrastructure for `app/`.
26. [x] Remove the separate support agent UI.
27. [ ] Connect the Nuxt chat flow to the customer support LLM agent.
28. [ ] Add demo data for customers, flights, bookings, and sensitive internal records.
29. [ ] Add scripts for seeding demo data and printing deployed stack outputs. Demo user bootstrap now has a dry-run teardown command.
30. [ ] Write docs for architecture, API usage, threat model, and the hackathon demo script.
31. [ ] Run an end-to-end demo path for human approval, agent approval, and agent denial.
32. [x] Add local automation to refresh `docs/layout.md` with Codex every 30 minutes and run git stage, commit, and pull every 5 minutes.

## Frontend Hosting

1. [ ] Push this monorepo to GitHub so Amplify can connect to the repository.
2. [ ] Deploy `IamAgentStack` with CDK so the Amplify app and branch are created.
3. [ ] Connect the Amplify app to the GitHub repo if CDK cannot attach the repo automatically.
4. [ ] Confirm Amplify builds `app/` from the monorepo root.
5. [x] Add Amplify hosting for `app/`.
6. [ ] Confirm the hosted single UI loads from the Amplify default domain.
