# Repo Layout

This is the target monorepo layout for the hackathon project.

```text
iam-agent/
  README.md
  AGENTS.md
  .env.example
  .gitignore

  infra/
    app.py
    cdk.json
    requirements.txt
    requirements-dev.txt
    README.md
    iam_agent/
      __init__.py
      iam_agent_stack.py
      constructs/
        __init__.py
        auth.py
        broker_api.py
        data.py
        demo_resources.py
        broker_api.py
        observability.py
        roles.py
      config/
        __init__.py
        resources.py

  services/
    shared/
      pyproject.toml
      src/
        iam_agent_shared/
          __init__.py
          types.py
          schemas.py
          errors.py
          logging.py

    broker-api/
      pyproject.toml
      src/
        broker_api/
          __init__.py
          handlers/
            __init__.py
            request_access.py
            admin_users.py
          auth/
            __init__.py
            cognito.py
            api_key.py
          llm/
            __init__.py
            reviewer.py
            prompts.py
            schemas.py
          policy/
            __init__.py
            build_session_policy.py
            validate_decision.py
            allowlist.py
            denylist.py
          aws/
            __init__.py
            sts.py
            console_url.py
          data/
            __init__.py
            principal_store.py
            request_log_store.py
            resource_catalog.py
      tests/

    agent-api/
      pyproject.toml
      src/
        agent_api/
          __init__.py
          handler.py
      tests/

  apps/
    staff/
      README.md
      requirements.txt
      streamlit_app.py
      pages/
        admin_users.py
        request_access.py
        audit_log.py
      iam_agent_client/
        __init__.py
        broker.py
        cognito.py

    support-agent/
      README.md
      package.json
      nuxt.config.ts
      app/
      components/
      server/
      utils/

  demo-data/
    customers.json
    flights.json
    bookings.json
    sensitive-internal.json

  docs/
    project.md
    to_do.md
    layout.md
    architecture.md
    api.md
    demo-script.md
    threat-model.md

  scripts/
    seed_demo_data.py
    create_agent_api_key.py
    print_outputs.py
```

## Folder Roles

### `infra/`

Python AWS CDK code.

Owns the AWS infrastructure:

- Cognito
- API Gateway
- Broker Lambda
- Agent Lambda and Broker API Gateway routes
- DynamoDB tables
- demo data resources
- target IAM roles
- CloudWatch logging

The CDK app should wire resources together, not contain product logic.

### `services/shared/`

Shared Python package for common contracts.

Use this for:

- shared types
- JSON schemas
- error classes
- logging helpers

### `services/broker-api/`

The main backend service.

This is the policy brain.

It handles:

- human and agent auth context
- policy lookup
- LLM review
- deterministic validation
- STS session policy creation
- `AssumeRole`
- console URL generation
- access request logging

### `services/agent-api/`

The Lambda-facing service for AI agents.

It should stay thin.

It receives Cognito-authenticated tool calls, calls the Broker API with IAM auth, receives approved temporary credentials, then performs only the approved tool action.

### `apps/staff/`

Streamlit app for internal users.

Admin users can create humans, agents, and free-text policies.

Employee users can request temporary AWS access.

### `apps/support-agent/`

Nuxt app for the customer support AI agent demo.

This is the customer-facing chat interface.

### `demo-data/`

Fake data used for the demo.

Include both safe and sensitive data so the demo can show approvals and denials.

### `docs/`

Project documentation for judges and future contributors.

### `scripts/`

Small local helper scripts.

Use this for seed data, generated API keys, and printing useful CDK outputs.
