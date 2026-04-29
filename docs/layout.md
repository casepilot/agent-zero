# Repo Layout

This file describes the current repo layout.

It separates checked-in project files from local generated files. Use this file
when adding new folders or deciding where new code should live.

## Current Source Layout

This tree shows the useful checked-in source, docs, tests, and automation.
Generated dependency and build folders are listed later.

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
        useAmplifyAuth.ts
      middleware/
        auth.global.ts
      pages/
        index.vue
        login.vue
        chats/
          index.vue
          [chatId].vue
      plugins/
        amplify.client.ts

  docs/
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
      src/
        agent_api/
          __init__.py
          handler.py
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

## Local Or Generated Layout

These folders and files may exist in a local checkout. They are ignored or
generated and should not guide new feature placement.

```text
agent-zero/
  .DS_Store
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
```

Other ignored local folders may appear after running tools, such as
`__pycache__/`, `.pytest_cache/`, `.venv/`, or `infra/cdk.out/`.

## Current Folder Roles

### Root Files

- `AGENTS.md` contains local instructions for Codex and future agents.
- `README.md` is the repo entry point.
- `.gitignore` ignores local env files, Python caches, Node dependencies,
  logs, local automation runtime files, and editor files.

### `app/`

Nuxt app for the demo UI.

Current state:

- Nuxt 4 app using pnpm.
- Tailwind CSS and shadcn-vue are configured.
- `lucide-vue-next` is used for icons.
- `/` redirects to `/chats`.
- `app/app/pages/login.vue` is the login screen wired to Cognito through the
  Amplify client SDK.
- `app/app/pages/chats/index.vue` is the themed empty chat home state with a
  link to `/chats/flight-change`.
- `app/app/pages/chats/[chatId].vue` is the desktop chat interface with seeded
  chat routes and local simulated streaming.
- `app/app/composables/useAmplifyAuth.ts` contains shared Amplify Auth helpers.
- `app/app/middleware/auth.global.ts` protects every route except `/login`.
- `app/app/plugins/amplify.client.ts` configures Amplify on the client.
- `app/app/components/ui/` contains shadcn-style button, input, and label
  components.
- `app/app/lib/utils.ts` contains the shared `cn()` class helper.
- `app/.env` is an ignored local file with public Cognito client config:
  `NUXT_PUBLIC_AWS_REGION`, `NUXT_PUBLIC_COGNITO_USER_POOL_ID`, and
  `NUXT_PUBLIC_COGNITO_USER_POOL_CLIENT_ID`.

Admin screens, employee request screens, and the live customer support LLM flow
are not built yet.

### `docs/`

Project docs.

Current docs:

- `project.md` explains the product, access model, security model, and demo
  story.
- `to_do.md` is the source of truth for build status and next work.
- `layout.md` describes the repo layout.

### `infra/`

Python AWS CDK app.

The stack is `IamAgentStack` and the project currently uses one CDK stack.

Current constructs:

- `auth.py` creates the Cognito user pool, app client, and `admin` and
  `employee` groups.
- `data.py` creates four DynamoDB tables:
  - `users-table`
  - `policy-table`
  - `customer_data`
  - `analytics_data`
- `broker_api.py` creates:
  - the broad broker credentials role used with scoped STS session policies
  - the Broker Lambda named `AgentZero`
  - the Agent Lambda named `UserAgent`
  - one API Gateway REST API
  - `GET /credentials` with IAM auth
  - `POST /agent` with Cognito auth
  - permissions for the agent Lambda to call the broker credentials endpoint
- `frontend_hosting.py` creates the Amplify app and `main` branch for the Nuxt
  app.

Current config:

- `resources.py` stores the project name, AWS account, AWS region, Cognito group
  names, and Amplify app root.

Current tests:

- `infra/tests/unit/test_infra_stack.py` checks Cognito, DynamoDB, API Gateway,
  Lambda, IAM, STS, and Amplify resources.

Add new infrastructure as constructs inside `IamAgentStack`.
Do not add another stack unless the user asks for it.

### `services/agent-api/`

Lambda-facing service for the user-facing agent route.

Current state:

- Handles Cognito-authenticated `POST /agent` requests.
- Reads the Cognito `sub` from API Gateway authorizer claims.
- Parses the request body for the access reason and staff flag.
- Calls the Broker API `GET /credentials` endpoint using IAM-signed requests.
- Returns the broker response to the caller.
- Loads the OpenAI secret as a plumbing check.

This service does not yet run the customer support LLM agent tools.

### `services/broker-api/`

Backend service for credential decisions.

Current state:

- Exposes the `GET /credentials` Lambda handler.
- Requires IAM-authenticated caller context from API Gateway.
- Rejects caller-supplied resource choices. The broker chooses resources from
  its catalog.
- Loads a principal policy from `policy-table`.
- Loads the OpenAI key from Secrets Manager.
- Builds a resource catalog for `customer_data`, `analytics_data`, and
  `policy_table`.
- Calls an OpenAI reviewer for a structured access decision.
- Validates decisions with deterministic allowlists, deny rules, and schema
  checks.
- Builds a scoped inline STS session policy for approved grants.
- Calls `sts:AssumeRole` through the broker credentials role.
- Returns temporary credentials for approved requests.
- Returns an AWS console sign-in URL when `is_staff` is true.

Current modules:

- `handlers/credentials.py` contains the Lambda entry point and request flow.
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

Broker-side request logging to DynamoDB is not implemented yet.

### `scripts/`

Local helper scripts.

Current scripts:

- `bootstrap_demo_users.py` bootstraps demo Cognito users, the demo agent
  record, demo policies, `customer_data` rows, and `analytics_data` rows. It
  also supports a dry-run teardown by default.
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
    customers.json
    flights.json
    bookings.json
    sensitive-internal.json

  docs/
    architecture.md
    api.md
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

- request logging to DynamoDB
- a request log table in infrastructure
- stronger human and agent identity mapping
- agent tool execution after credentials are issued
- more complete resource coverage for the full demo story

### `demo-data/`

Planned standalone fake data for the demo.

Some demo data currently lives inline in `scripts/bootstrap_demo_users.py`.
Move or copy it here if the project needs reusable fixtures.

### More Docs

Planned docs:

- `architecture.md`
- `api.md`
- `demo-script.md`
- `threat-model.md`
