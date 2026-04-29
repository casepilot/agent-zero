# Repo Layout

This file describes the current repo layout.

It also lists planned folders that are part of the product plan but do not
exist yet.

## Current Layout

```text
agent-zero/
  .gitignore
  AGENTS.md
  README.md
  .codex-automation/
    locks/
    logs/

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
      pages/
        home.vue
        index.vue
        login.vue
      plugins/

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
      src/
        broker_api/
          __init__.py
          handlers/
            __init__.py
            credentials.py

  scripts/
    bootstrap_demo_users.py
    automation/
      git_sync.sh
      install_launchd.sh
      update_layout_with_codex.sh
    launchd/
      com.agent-zero.git-sync.plist
      com.agent-zero.layout-refresh.plist
```

## Current Folder Roles

### `app/`

Nuxt app for the demo UI.

Current state:

- Nuxt 4 app using pnpm.
- Tailwind CSS and shadcn-vue are configured.
- `app/app/pages/index.vue` redirects to `/home`.
- `app/app/pages/login.vue` is a static login screen that routes through `/` on submit.
- `app/app/pages/home.vue` is the post-login landing page.
- `app/app/components/ui/` contains shadcn-style button, input, and label components.
- `app/app/lib/utils.ts` contains the shared `cn()` class helper.

The admin, employee, and customer support demo screens are not built yet.

### `docs/`

Project docs.

Current docs:

- `project.md` explains the product, access model, security model, and demo story.
- `to_do.md` is the source of truth for build status and next work.
- `layout.md` describes the repo layout.

### `infra/`

Python AWS CDK app.

The stack is `IamAgentStack` and it currently uses one CDK stack.

Current constructs:

- `auth.py` creates the Cognito user pool, app client, and `admin` and `employee` groups.
- `data.py` creates `users-table` and `policy-table` DynamoDB tables.
- `broker_api.py` creates the Broker Lambda, Agent Lambda, API Gateway routes, and IAM auth wiring.
- `frontend_hosting.py` creates the Amplify app and `main` branch for the Nuxt app.

Current config:

- `resources.py` stores the project name, AWS account, AWS region, Cognito group names, and Amplify app root.

Current tests:

- `infra/tests/unit/test_infra_stack.py` checks Cognito, DynamoDB, API Gateway, Lambda, IAM, and Amplify resources.

Add new infrastructure as constructs inside `IamAgentStack`.
Do not add another stack unless the user asks for it.

### `services/agent-api/`

Lambda-facing service for the user-facing agent route.

Current state:

- Receives Cognito-authenticated `POST /agent` requests.
- Calls the Broker API `GET /credentials` endpoint using IAM-signed requests.
- Returns the broker response to the caller.

### `services/broker-api/`

Backend service for credential decisions.

Current state:

- Exposes a basic `GET /credentials` Lambda handler.
- Requires IAM-authenticated caller context from API Gateway.
- Loads the OpenAI key from Secrets Manager to prove broker plumbing.
- Returns request context only. LLM review and STS issuance are not implemented yet.

### `scripts/`

Local helper scripts.

Current scripts:

- `bootstrap_demo_users.py` bootstraps or tears down demo Cognito users and the demo agent record in `users-table`.
- `automation/update_layout_with_codex.sh` runs Codex to refresh this layout doc.
- `automation/git_sync.sh` stages, commits, and pulls from the current branch.
- `automation/install_launchd.sh` installs the local launchd jobs.
- `launchd/*.plist` defines the local layout-refresh and git-sync launch agents.

### `.codex-automation/`

Local runtime folder created by the automation scripts.

It is ignored by git and holds local logs and lock folders.

## Planned Or Missing Layout

These folders and files are part of the intended product shape, but they are
not present in the current codebase.

```text
agent-zero/
  services/
    shared/
    broker-api/
      src/
        broker_api/
          auth/
          aws/
          data/
          llm/
          policy/

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

### More Broker API Modules

The broker still needs modules for:

- human and agent auth context
- policy lookup
- resource catalog lookup
- LLM review
- deterministic validation
- session policy generation
- `AssumeRole`
- console URL generation
- access request logging

### `demo-data/`

Planned fake data for the demo.

It should include both safe and sensitive records so the demo can show approvals
and denials.

### Planned Docs

The project still needs docs for:

- architecture
- API usage
- threat model
- hackathon demo script
