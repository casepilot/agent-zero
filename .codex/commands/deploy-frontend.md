---
description: Deploy the Agent Zero frontend hosting stack from this repo.
---

Run the project-local frontend deploy script:

```bash
scripts/deploy_frontend.sh
```

Use `/Users/deepak/hackathon/agent-zero` as the working directory.

Rules:

- Only run the script in this repository.
- Do not deploy any other stack.
- If the command needs AWS/CDK/network access outside the sandbox, request approval and rerun the same script.
- After the deploy finishes, report whether it succeeded and include the key CDK/Amplify outputs.
- If Amplify still needs a GitHub connection, say that clearly.
