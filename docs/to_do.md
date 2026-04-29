# To Do

1. [x] Spin up a Python CDK app in `infra/`.
2. [x] Create the base CDK stack and environment config.
3. [ ] Add DynamoDB tables for principals, policies, request logs, and demo app data. Users and policy tables are added; request logs and demo data remain.
4. [x] Add Cognito user pool, app client, and groups for `admin` and `employee`.
5. [ ] Add broad target IAM roles for DynamoDB, S3, and future AWS resource access.
6. [ ] Create `services/shared/` for shared types, schemas, errors, and logging helpers.
7. [x] Create `services/broker-api/` with a basic Lambda handler.
8. [x] Wire the Broker API Lambda behind API Gateway.
9. [x] Add Cognito auth for human requests to the Agent API.
10. [x] Add IAM auth for Agent Lambda requests to the Broker API credentials endpoint.
11. [ ] Add principal and policy lookup from DynamoDB.
12. [ ] Add a resource catalog that describes stack resources and their ARNs.
13. [ ] Add the LLM reviewer with structured JSON output.
14. [ ] Add deterministic validation for LLM decisions, allowed actions, resources, durations, and deny rules.
15. [ ] Add session policy generation for approved requests.
16. [ ] Add `sts:AssumeRole` with the inline session policy.
17. [ ] Add AWS console sign-in URL generation for human users.
18. [ ] Add broker-side request logging to DynamoDB.
19. [x] Create `services/agent-api/` with a Lambda behind API Gateway.
20. [ ] Add agent tools that request broker access and then perform approved DynamoDB actions.
21. [ ] Create the Streamlit staff app in `apps/staff/`.
22. [ ] Add Streamlit admin screens for creating humans, agents, and free-text policies.
23. [ ] Add Streamlit employee screens for requesting access and receiving console URLs.
24. [x] Create the Nuxt customer support agent app in `apps/support-agent/`.
25. [x] Add Amplify hosting infrastructure for `apps/support-agent/`.
26. [ ] Properly build out `apps/support-agent/`; currently only the Nuxt chat UI template has been dropped in.
27. [ ] Connect the Nuxt chat app to the customer support LLM agent.
28. [ ] Add demo data for customers, flights, bookings, and sensitive internal records.
29. [ ] Add scripts for seeding demo data and printing deployed stack outputs. Demo user bootstrap now has a dry-run teardown command.
30. [ ] Write docs for architecture, API usage, threat model, and the hackathon demo script.
31. [ ] Run an end-to-end demo path for human approval, agent approval, and agent denial.

## Frontend Hosting

1. [ ] Push this monorepo to GitHub so Amplify can connect to the repository.
2. [ ] Deploy `IamAgentStack` with CDK so the Amplify app and branch are created.
3. [ ] Connect the Amplify app to the GitHub repo if CDK cannot attach the repo automatically.
4. [ ] Confirm Amplify builds `apps/support-agent/` from the monorepo root.
5. [ ] Confirm the hosted support agent app loads from the Amplify default domain.
