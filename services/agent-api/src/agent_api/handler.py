import json
import os
from typing import Any
from urllib.parse import quote, urlencode

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.exceptions import ClientError
from botocore.httpsession import URLLib3Session


_apigateway_management_clients: dict[str, Any] = {}
_lambda_client: Any | None = None
_openai_key: str | None = None
_secretsmanager_client: Any | None = None


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


def response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
    }


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


def authorizer_context(request_context: dict[str, Any]) -> dict[str, Any]:
    authorizer = request_context.get("authorizer") or {}
    if "user_id" in authorizer:
        return authorizer
    return authorizer.get("claims") or {}


def websocket_response(status_code: int = 200) -> dict[str, Any]:
    return {"statusCode": status_code}


def sign_request(method: str, url: str) -> AWSRequest:
    credentials = boto3.Session().get_credentials()
    if credentials is None:
        raise RuntimeError("Lambda execution credentials were not available")

    aws_request = AWSRequest(method=method, url=url)
    SigV4Auth(credentials.get_frozen_credentials(), "execute-api", os.environ["AWS_REGION"]).add_auth(
        aws_request
    )
    return aws_request


def call_credentials_endpoint(
    *,
    user_id: str,
    payload: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    query = {
        "user_id": user_id,
        "reason": payload.get("reason", ""),
        "is_staff": str(bool(payload.get("is_staff", True))).lower(),
    }
    credentials_url = f"{os.environ['CREDENTIALS_URL']}?{urlencode(query, quote_via=quote)}"
    prepared_request = sign_request("GET", credentials_url).prepare()
    result = URLLib3Session(timeout=40).send(prepared_request)
    body = result.content.decode("utf-8")

    try:
        parsed_body = json.loads(body)
    except json.JSONDecodeError:
        parsed_body = {"raw_body": body}

    return result.status_code, parsed_body


def sanitize_broker_body(status_code: int, broker_body: dict[str, Any]) -> dict[str, Any]:
    if status_code < 400:
        return broker_body

    decision = broker_body.get("decision")
    message = broker_body.get("message")
    safe_message = None
    if isinstance(message, str):
        safe_message = message.splitlines()[0]

    safe_body = {
        "error": broker_body.get("error", "broker_request_failed"),
        "message": safe_message or "Broker request failed.",
    }
    if isinstance(decision, dict):
        safe_body["decision"] = decision
    return safe_body


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

    try:
        openai_secret_loaded = bool(get_openai_key())
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
        stream_text(
            connection_id=connection_id,
            domain_name=domain_name,
            stage=stage,
            request_id=request_id_value,
            text="Checking your request with the broker.",
        )
        status_code, broker_body = call_credentials_endpoint(
            user_id=human_user_id,
            payload=payload,
        )
    except Exception as error:
        log(
            "agent_broker_call_exception",
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
                "error": "broker_call_failed",
                "message": str(error),
            },
        )
        return {"statusCode": 502}

    safe_broker_body = sanitize_broker_body(status_code, broker_body)
    log(
        "agent_broker_call_completed",
        aws_request_id=aws_request_id,
        broker_status_code=status_code,
        broker_error=safe_broker_body.get("error"),
        broker_secret_loaded=safe_broker_body.get("openai_secret_loaded"),
    )

    # Front-end return patterns:
    # - Approved: broker_response.status="approved", decision.reason/risk/
    #   authorization, credentials, and optionally console_login_url.
    #   Render as: "Automatic approval review approved (risk: medium,
    #   authorization: high): <decision.reason>".
    # - Denied by policy/model: broker_response.error="access_denied" with
    #   decision.reason/risk/authorization when available.
    # - No policy: broker_response.error="no_policy_found".
    # - System failure: broker_response.error or top-level error explains the
    #   failed service path. Stream these states to the front end as the broker
    #   review progresses.
    send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={
            "type": "broker_result",
            "requestId": request_id_value,
            "statusCode": status_code,
            "service": "agent-api",
            "human_user_id": human_user_id,
            "openai_secret_loaded": openai_secret_loaded,
            "broker_response": safe_broker_body,
        },
    )
    send_ws_message(
        connection_id=connection_id,
        domain_name=domain_name,
        stage=stage,
        payload={"type": "done", "requestId": request_id_value},
    )
    return {"statusCode": status_code}


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    if "routeKey" in event.get("requestContext", {}):
        return route_handler(event, context)
    return worker_handler(event, context)
