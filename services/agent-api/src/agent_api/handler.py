import asyncio
import json
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError


_apigateway_management_clients: dict[str, Any] = {}
_lambda_client: Any | None = None
_openai_key: str | None = None
_secretsmanager_client: Any | None = None
DEFAULT_AGENT_MODEL = "gpt-5-nano"
FRIENDLY_ASSISTANT_INSTRUCTIONS = "You are a friendly assistant."


def get_lambda_client() -> Any:
    global _lambda_client

    if _lambda_client is None:
        _lambda_client = boto3.client("lambda")
    return _lambda_client


def get_apigateway_management_client(domain_name: str, stage: str) -> Any:
    endpoint_url = f"https://{domain_name}/{stage}"
    if endpoint_url not in _apigateway_management_clients:
        _apigateway_management_clients[endpoint_url] = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=endpoint_url,
        )
    return _apigateway_management_clients[endpoint_url]


def get_secretsmanager_client() -> Any:
    global _secretsmanager_client

    if _secretsmanager_client is None:
        _secretsmanager_client = boto3.client("secretsmanager")
    return _secretsmanager_client


def get_openai_key() -> str:
    global _openai_key

    if _openai_key is not None:
        return _openai_key

    secret_name = os.environ["OPENAI_SECRET_NAME"]
    client = get_secretsmanager_client()
    response = client.get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString")
    if secret_string is None:
        raise RuntimeError(f"Secret {secret_name} did not contain SecretString")

    try:
        secret_json = json.loads(secret_string)
    except json.JSONDecodeError:
        _openai_key = secret_string
    else:
        _openai_key = (
            secret_json.get("OPENAI_API_KEY")
            or secret_json.get("openai_api_key")
            or secret_json.get("api_key")
            or secret_json.get("api-key")
            or secret_json.get("apiKey")
            or secret_string
        )
    return _openai_key


def log(message: str, **fields: Any) -> None:
    print(json.dumps({"message": message, **fields}, default=str))


def request_id(context: Any) -> str | None:
    return getattr(context, "aws_request_id", None)


def parse_body(event: dict[str, Any]) -> dict[str, Any]:
    body = event.get("body")
    if not body:
        return {}

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {}

    if isinstance(parsed, dict):
        return parsed
    return {}


def prompt_from_payload(payload: dict[str, Any]) -> str | None:
    for key in ("message", "prompt", "reason"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def authorizer_context(request_context: dict[str, Any]) -> dict[str, Any]:
    authorizer = request_context.get("authorizer") or {}
    if "user_id" in authorizer:
        return authorizer
    return authorizer.get("claims") or {}


def websocket_response(status_code: int = 200) -> dict[str, Any]:
    return {"statusCode": status_code}


def send_ws_message(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    payload: dict[str, Any],
) -> bool:
    client = get_apigateway_management_client(domain_name, stage)
    try:
        client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(payload, default=str).encode("utf-8"),
        )
        return True
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "GoneException":
            log(
                "websocket_connection_gone",
                connection_id=connection_id,
                payload_type=payload.get("type"),
            )
            return False
        raise


def stream_text(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    request_id: str | None,
    text: str,
) -> bool:
    return send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={"type": "delta", "requestId": request_id, "text": text},
    )


async def stream_friendly_agent_response(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    request_id: str | None,
    prompt: str,
    openai_api_key: str,
) -> None:
    from agents import Agent, Runner, set_default_openai_key

    set_default_openai_key(openai_api_key)
    agent = Agent(
        name="FriendlyAssistant",
        instructions=FRIENDLY_ASSISTANT_INSTRUCTIONS,
        model=os.environ.get("AGENT_MODEL", DEFAULT_AGENT_MODEL),
    )
    result = Runner.run_streamed(agent, input=prompt)

    async for event in result.stream_events():
        if getattr(event, "type", None) != "raw_response_event":
            continue

        data = getattr(event, "data", None)
        delta = getattr(data, "delta", None)
        if not isinstance(delta, str) or not delta:
            continue

        if not stream_text(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            request_id=request_id,
            text=delta,
        ):
            break


def invoke_worker(
    *,
    connection_id: str,
    domain_name: str,
    stage: str,
    user_id: str,
    payload: dict[str, Any],
) -> None:
    get_lambda_client().invoke(
        FunctionName=os.environ["AGENT_WORKER_FUNCTION_NAME"],
        InvocationType="Event",
        Payload=json.dumps(
            {
                "connection_id": connection_id,
                "domain_name": domain_name,
                "stage": stage,
                "user_id": user_id,
                "payload": payload,
            }
        ).encode("utf-8"),
    )


def route_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    aws_request_id = request_id(context)
    request_context = event.get("requestContext", {})
    route_key = request_context.get("routeKey")
    log(
        "agent_websocket_event_started",
        aws_request_id=aws_request_id,
        route_key=route_key,
        request_context_request_id=request_context.get("requestId"),
        has_authorizer=bool(request_context.get("authorizer")),
    )

    if route_key in {"$connect", "$disconnect"}:
        return websocket_response(200)

    if route_key == "$default":
        log(
            "agent_websocket_rejected",
            aws_request_id=aws_request_id,
            reason="unknown_route",
        )
        return websocket_response(400)

    if route_key != "requestAccess":
        return websocket_response(400)

    auth_context = authorizer_context(request_context)
    human_user_id = auth_context.get("user_id") or auth_context.get("sub")
    payload = parse_body(event)
    log(
        "agent_websocket_payload_parsed",
        aws_request_id=aws_request_id,
        human_user_id=human_user_id,
        payload_keys=sorted(payload.keys()),
        has_reason=bool(payload.get("reason")),
    )

    try:
        if not human_user_id:
            raise RuntimeError("Cognito sub was missing from the request context")
        invoke_worker(
            connection_id=request_context["connectionId"],
            domain_name=request_context["domainName"],
            stage=request_context["stage"],
            user_id=human_user_id,
            payload=payload,
        )
    except Exception as error:
        log(
            "agent_worker_invoke_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        return websocket_response(500)

    return websocket_response(200)


def worker_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    aws_request_id = request_id(context)
    connection_id = event["connection_id"]
    domain_name = event["domain_name"]
    stage = event["stage"]
    human_user_id = event["user_id"]
    payload = event.get("payload") or {}
    request_id_value = payload.get("requestId")

    log(
        "agent_worker_started",
        aws_request_id=aws_request_id,
        human_user_id=human_user_id,
        request_id=request_id_value,
        payload_keys=sorted(payload.keys()),
    )

    if not send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={"type": "ack", "requestId": request_id_value},
    ):
        return {"statusCode": 410}

    prompt = prompt_from_payload(payload)
    if prompt is None:
        send_ws_message(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            payload={
                "type": "error",
                "requestId": request_id_value,
                "error": "missing_prompt",
                "message": "message, prompt, or reason is required.",
            },
        )
        return {"statusCode": 400}

    try:
        openai_api_key = get_openai_key()
    except Exception as error:
        log(
            "agent_secret_check_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        send_ws_message(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            payload={
                "type": "error",
                "requestId": request_id_value,
                "error": "openai_secret_check_failed",
                "message": str(error),
            },
        )
        return {"statusCode": 500}

    try:
        asyncio.run(
            stream_friendly_agent_response(
                connection_id=connection_id,
                domain_name=domain_name,
                stage=stage,
                request_id=request_id_value,
                prompt=prompt,
                openai_api_key=openai_api_key,
            )
        )
    except Exception as error:
        log(
            "agent_sdk_stream_failed",
            aws_request_id=aws_request_id,
            error_type=type(error).__name__,
            error_message=str(error),
        )
        send_ws_message(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            payload={
                "type": "error",
                "requestId": request_id_value,
                "error": "agent_stream_failed",
                "message": str(error),
            },
        )
        return {"statusCode": 502}

    log(
        "agent_sdk_stream_completed",
        aws_request_id=aws_request_id,
        human_user_id=human_user_id,
        request_id=request_id_value,
    )
    send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={"type": "done", "requestId": request_id_value},
    )
    return {"statusCode": 200}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if "routeKey" in event.get("requestContext", {}):
        return route_handler(event, context)
    return worker_handler(event, context)
