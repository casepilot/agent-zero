#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INFRA_DIR="$REPO_ROOT/infra"

STACK_NAME="${STACK_NAME:-IamAgentStack}"
AWS_PROFILE_NAME="${AWS_PROFILE_NAME:-openai-hackathon}"
AWS_REGION_NAME="${AWS_REGION_NAME:-ap-southeast-2}"

if [[ ! -d "$INFRA_DIR" ]]; then
  echo "Could not find infra directory at: $INFRA_DIR" >&2
  exit 1
fi

if [[ ! -f "$INFRA_DIR/cdk.json" ]]; then
  echo "Could not find CDK app config at: $INFRA_DIR/cdk.json" >&2
  exit 1
fi

if ! command -v cdk >/dev/null 2>&1; then
  echo "cdk is not installed or not on PATH." >&2
  echo "Install the AWS CDK CLI, then rerun this script." >&2
  exit 127
fi

VENV_PYTHON="$INFRA_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Creating Python virtualenv at $INFRA_DIR/.venv"
  python3 -m venv "$INFRA_DIR/.venv"
fi

if ! "$VENV_PYTHON" -c "import aws_cdk" >/dev/null 2>&1; then
  echo "Installing CDK Python dependencies from infra/requirements.txt"
  "$VENV_PYTHON" -m pip install -r "$INFRA_DIR/requirements.txt"
fi

echo "Deploying $STACK_NAME from $INFRA_DIR"
echo "AWS profile: $AWS_PROFILE_NAME"
echo "AWS region: $AWS_REGION_NAME"
echo "Amplify app root: app"

export AWS_PROFILE="$AWS_PROFILE_NAME"
export AWS_REGION="$AWS_REGION_NAME"
export AWS_DEFAULT_REGION="$AWS_REGION_NAME"
export AWS_SDK_LOAD_CONFIG=1

cd "$INFRA_DIR"
exec cdk deploy "$STACK_NAME" --profile "$AWS_PROFILE_NAME" --app ".venv/bin/python app.py" "$@"
