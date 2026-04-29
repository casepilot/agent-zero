# Repo Layout

This file describes the current repo layout.

It separates checked-in project files from local generated, ignored, and
untracked files. Use this file when adding new folders or deciding where new
code should live.

## Current Source Layout

This tree shows the checked-in source, docs, tests, and automation that matter
for contributor work. Generated dependency and build folders are listed later.
The repo root also currently has a tracked `.DS_Store`; treat it as local
macOS metadata, not as a project file.

```text
agent-zero/
  .gitignore
  AGENTS.md
  README.md

  .agents/
    skills/
      deploy-frontend/
        SKILL.md
        agents/
          openai.yaml

  app/
    .gitignore
    README.md
    package.json
    pnpm-lock.yaml
    nuxt.config.ts
    tsconfig.json
    components.json
    public/
      favicon.ico
      robots.txt
    app/
      app.vue
      assets/
        css/
          tailwind.css
      components/
        ui/
          button/
            Button.vue
            index.ts
          input/
            Input.vue
            index.ts
          label/
            Label.vue
            index.ts
      lib/
        utils.ts
      composables/
        useAgentChat.ts
        useAmplifyAuth.ts
      middleware/
        auth.global.ts
      pages/
        index.vue
        login.vue
        chat.vue
      plugins/
        amplify.client.ts

  bootstrap/
    __init__.py
    bank_data.py

  docs/
    api.md
    project.md
    to_do.md
    layout.md

  infra/
    .gitignore
    app.py
    cdk.json
    requirements.txt
    requirements-dev.txt
    iam_agent/
      __init__.py
      iam_agent_stack.py
      config/
        __init__.py
        resources.py
      constructs/
        __init__.py
        auth.py
        broker_api.py
        data.py
        frontend_hosting.py
    tests/
      __init__.py
      unit/
        __init__.py
        test_infra_stack.py

  services/
    agent-api/
      requirements.txt
      src/
        agent_api/
          __init__.py
          authorizer.py
          handler.py
      tests/
        test_handler.py
    broker-api/
      requirements.txt
      src/
        broker_api/
          __init__.py
          aws/
            __init__.py
            console_url.py
            sts.py
          data/
            __init__.py
            resource_catalog.py
          handlers/
            __init__.py
            credentials.py
          llm/
            __init__.py
            prompts.py
            reviewer.py
          policy/
            __init__.py
            build_session_policy.py
            schemas.py
            validate_decision.py
      tests/
        test_credentials_handler.py
        test_policy_validation.py

  scripts/
    bootstrap_demo_users.py
    deploy_frontend.sh
    automation/
      git_sync.sh
      install_launchd.sh
      update_layout_with_codex.sh
    launchd/
      com.agent-zero.git-sync.plist
      com.agent-zero.layout-refresh.plist
```

## Local, Generated, Or Untracked Layout

These folders and files may exist in a local checkout. They are ignored,
generated, or not checked in and should not guide new feature placement.

```text
agent-zero/
  .env
  cdk.out/
  .codex-automation/
    locks/
      layout-refresh.lock/
    logs/
      git-sync.err.log
      git-sync.out.log
      layout-last-message.txt
      layout-refresh.err.log
      layout-refresh.out.log
  app/
    .env
    node_modules/
    .nuxt/
    .output/
  infra/
    .venv/
    cdk.out/
    iam_agent/
      __pycache__/
      config/
        __pycache__/
      constructs/
        __pycache__/
```

Other ignored local folders may appear after running tools, such as
`__pycache__/`, `.pytest_cache/`, `.venv/`, `cdk.out/`, or `infra/cdk.out/`.

## Current Folder Roles

### Root Files

- `AGENTS.md` contains local instructions for Codex and future agents.
- `README.md` is the repo entry point.
- `.gitignore` ignores local env files, Python caches, Node dependencies,
  logs, local automation runtime files, and editor files.
- `.DS_Store` is currently tracked in git, but it is macOS metadata and should
  not guide project structure.

### `app/`

Nuxt app for the demo UI.

Current state:

- Nuxt 4 app using pnpm.
- Nuxt renders as a client-side app because route protection depends on the
  browser-side Amplify Auth session.
- Tailwind CSS and shadcn-vue are configured.
- `lucide-vue-next` is used for icons.
- `/` redirects to `/chat`.
- `app/app/pages/login.vue` is the login screen wired to Cognito through the
  Amplify client SDK.
- `app/app/pages/chat.vue` is the single desktop chat interface. It starts as
  an empty chat with a bottom prompt input, live Agent API WebSocket streaming,
  safe tool status summaries, markdown-rendered answer streaming, retry
  handling, and visible sign out.
- `app/app/composables/useAgentChat.ts` contains the Agent API WebSocket client,
  stream reducer, retry flow, and socket cleanup.
- `app/app/composables/useAmplifyAuth.ts` contains shared Amplify Auth helpers,
  including access-token retrieval for WebSocket auth.
- `app/app/middleware/auth.global.ts` protects every route except `/login`.
- `app/app/plugins/amplify.client.ts` configures Amplify on the client.
- `app/app/components/ui/` contains shadcn-style button, input, and label
  components.
- `app/app/lib/utils.ts` contains the shared `cn()` class helper.
- `app/.env` is an ignored local file with public Cognito client config:
  `NUXT_PUBLIC_AWS_REGION`, `NUXT_PUBLIC_COGNITO_USER_POOL_ID`, and
  `NUXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID`. It can also hold
  `NUXT_PUBLIC_AGENT_WS_URL` for the Agent API WebSocket endpoint.

Admin screens and employee request screens are not built yet.

### `docs/`

Project docs.

Current docs:

- `project.md` explains the product, access model, security model, and demo
  story.
- `api.md` documents the current Agent API WebSocket contract and stream
  envelope.
- `to_do.md` is the source of truth for build status and next work.
- `layout.md` describes the repo layout.

### `bootstrap/`

Checked-in Python package for demo seed data.

Current files:

- `bank_data.py` contains bank demo users, group names, free-text access
  policies, customer profiles, balances, transactions, operational metrics, and
  old demo usernames to clean up.
- `__init__.py` makes the folder importable by scripts.

Keep reusable seed data here when it is shared by scripts or tests. Keep script
control flow in `scripts/`.

### `infra/`

Python AWS CDK app.

The stack is `IamAgentStack` and the project currently uses one CDK stack.

Current constructs:

- `auth.py` creates the Cognito user pool, app client, and `admin`, `employee`,
  and `customer` groups.
- `data.py` creates eight DynamoDB tables:
  - `users-table`
  - `policy-table`
  - `bank_customer_profiles`
  - `bank_operational_metrics`
  - `bank_transactions`
  - `bank_balances`
<<<<<<< HEAD
=======
  - `support-requests`
>>>>>>> 3c4b6a9e5e2745e113f22a5c02a6e17e32ea24c6
  - `request_logs`
- `broker_api.py` creates:
  - the broad broker credentials role used with scoped STS session policies
  - the Broker Lambda named `AgentZero`
  - the Agent WebSocket authorizer Lambda named `UserAgentWebSocketAuthorizer`
  - the Agent WebSocket route Lambda named `UserAgentWebSocket`
  - the Agent worker Lambda named `UserAgentWorker`
  - one API Gateway REST API for the Broker API
  - `GET /credentials` with IAM auth
  - one API Gateway WebSocket API for the Agent API
  - a custom WebSocket authorizer that reads a Cognito access token from the
    `token` query string
  - WebSocket routes for `$connect`, `$disconnect`, `$default`, and
    `requestAccess`
  - permissions for the route Lambda to invoke the worker Lambda
  - permissions for the worker Lambda to call the broker credentials endpoint
  - permissions for the worker Lambda to post messages back to WebSocket
    clients
- `frontend_hosting.py` creates the Amplify app and `main` branch for the Nuxt
  app. It also passes the Agent WebSocket URL to Amplify as
  `NUXT_PUBLIC_AGENT_WS_URL`.

Current config:

- `resources.py` stores the project name, AWS account, AWS region, Cognito group
  names (`admin`, `employee`, and `customer`), and Amplify app root.

Current tests:

- `infra/tests/unit/test_infra_stack.py` checks Cognito, DynamoDB, API Gateway,
  Lambda, IAM, STS, and Amplify resources.

Add new infrastructure as constructs inside `IamAgentStack`.
Do not add another stack unless the user asks for it.

### `services/agent-api/`

Lambda-facing service for the user-facing Agent API WebSocket route.

Current state:

- `authorizer.py` validates Cognito access tokens from the WebSocket `token`
  query string.
- The authorizer adds the trusted Cognito `sub` as `user_id` in the API Gateway
  authorizer context.
- `handler.py` contains the WebSocket route handler, worker handler, and a
  compatibility `handler()` dispatcher.
- The route handler accepts `$connect`, `$disconnect`, `$default`, and
  `requestAccess` events.
- `requestAccess` parses the WebSocket body and invokes the worker Lambda
  asynchronously.
- The worker runs the OpenAI Agents SDK and sends top-level `ack`, `stream`,
  `error`, and `done` messages back to the WebSocket client.
- Rich stream messages use `message_marker`, `delta`, and `completed_message`
  stream types for reasoning, tool calls, and assistant answer updates.
- The agent instructions include private routing context, policy-table context
  for identity admins, and access request guidance for employees and customers.
- The live agent exposes tools for requesting broker access, running DynamoDB
  operations, writing policy-table records, and creating Cognito users.
- `handler.py` contains an IAM-signed Broker API helper for `GET /credentials`.
  The `request_aws_access` tool uses it and stores approved temporary
  credentials for the current turn.
- `run_dynamodb_operation` first tries the worker's current AWS credentials. If
  broker access is approved, it can retry using the scoped STS credentials.
- The worker uses the trusted Cognito `sub` from the authorizer context, not a
  caller-supplied body value.
- The worker loads the OpenAI key from Secrets Manager before starting the
  agent stream.
- `tests/test_handler.py` checks trusted authorizer identity handling, staff
  group handling, stream envelope mapping, and the broker query helper.

The Nuxt chat screen is wired to this WebSocket flow. The credential loop and
DynamoDB tool path exist in code, but the full demo path still needs end-to-end
validation.

### `services/broker-api/`

Backend service for credential decisions.

Current state:

- Exposes the `GET /credentials` Lambda handler.
- Requires IAM-authenticated caller context from API Gateway.
- Rejects caller-supplied resource choices. The broker chooses resources from
  its catalog.
- Loads the principal profile from `users-table`.
- Loads a principal policy from `policy-table`.
- Loads the OpenAI key from Secrets Manager.
<<<<<<< HEAD
- Builds a resource catalog for `users_table`, `user_pool`,
  `bank_customer_profiles`, `bank_operational_metrics`, `bank_transactions`,
  `bank_balances`, and `policy_table`.
=======
- Builds a resource catalog for the bank DynamoDB tables, Cognito user pool,
  users table, and policy table.
>>>>>>> 3c4b6a9e5e2745e113f22a5c02a6e17e32ea24c6
- Calls an OpenAI reviewer for a structured access decision.
- Validates decisions with deterministic allowlists, deny rules, and schema
  checks.
- Builds a scoped inline STS session policy for approved grants.
- Calls `sts:AssumeRole` through the broker credentials role.
- Returns temporary credentials for approved requests.
- Returns an AWS console sign-in URL when `is_staff` is true.
- Writes terminal audit records to `request_logs`.

Current modules:

- `handlers/credentials.py` contains the Lambda entry point, request flow, and
  audit logging.
- `data/resource_catalog.py` defines broker-known resources and prompt
  formatting.
- `llm/prompts.py` contains the reviewer prompt text.
- `llm/reviewer.py` calls OpenAI and retries validation failures.
- `policy/schemas.py` defines the structured access decision schema.
- `policy/validate_decision.py` enforces deterministic safety rules.
- `policy/build_session_policy.py` builds inline STS session policies.
- `aws/sts.py` wraps `AssumeRole`.
- `aws/console_url.py` builds AWS federation console login URLs.
- `tests/` covers credential handler behavior, policy validation, and session
  policy generation.

### `scripts/`

Local helper scripts.

Current scripts:

<<<<<<< HEAD
- `bootstrap_demo_users.py` imports data from `bootstrap/bank_data.py` and
  bootstraps bank demo Cognito users, principal rows, policies,
  `bank_customer_profiles`, `bank_operational_metrics`, `bank_transactions`, and
  `bank_balances`. It also supports teardown, with dry-run teardown by default.
=======
- `bootstrap_demo_users.py` bootstraps demo Cognito users, demo policies,
  bank customer profiles, balances, transactions, support requests, and
  operational metrics. It also supports a dry-run teardown by default.
>>>>>>> 3c4b6a9e5e2745e113f22a5c02a6e17e32ea24c6
- `deploy_frontend.sh` runs the single-stack CDK deploy for the frontend hosting
  path.
- `automation/update_layout_with_codex.sh` runs Codex to refresh this layout
  doc.
- `automation/git_sync.sh` stages, commits, and pulls from the current branch.
- `automation/install_launchd.sh` installs the local launchd jobs.
- `launchd/*.plist` defines the local layout-refresh and git-sync launch
  agents.

### `.agents/`

Project-local Codex skills.

Current files:

- `skills/deploy-frontend/SKILL.md` tells Codex how to deploy the frontend
  hosting path.
- `skills/deploy-frontend/agents/openai.yaml` contains UI metadata for the
  skill.

Use it from this repo by telling Codex:

```text
deploy frontend
```

The skill runs `scripts/deploy_frontend.sh`.

### `.codex-automation/`

Local runtime folder created by the automation scripts.

It is ignored by git and holds local logs and lock folders. Do not put product
source here.

## Planned Or Missing Layout

These folders and files are part of the intended product shape, but they are
not present in the current codebase.

```text
agent-zero/
  services/
    shared/

  demo-data/
    flights.json
    bookings.json
    sensitive-internal.json

  docs/
    architecture.md
    demo-script.md
    threat-model.md
```

## Planned Or Missing Folder Roles

### `services/shared/`

Planned shared Python package for common contracts.

Use it for:

- shared types
- JSON schemas
- error classes
- logging helpers

### More Broker Work

The broker still needs:

- stronger human and agent identity mapping
- end-to-end validation of the chat credential loop
- more complete resource coverage for the full demo story

### More App Work

The Nuxt app still needs:

- admin screens for creating humans, agents, and free-text policies
- employee screens for requesting access and receiving console URLs

### `demo-data/`

Planned standalone fake data for the demo.

Bank demo data currently lives in `bootstrap/bank_data.py`. Use `demo-data/`
for future standalone fixtures such as flights, bookings, or sensitive internal
records if the demo still needs them.

### More Docs

Planned docs:

- `architecture.md`
- `demo-script.md`
- `threat-model.md`
