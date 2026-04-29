# API Notes

## Agent WebSocket Endpoint

The support-agent frontend talks to the Agent API over API Gateway WebSocket.

Use:

```text
NUXT_PUBLIC_AGENT_WS_URL
```

Current deployed shape:

```text
wss://<api-id>.execute-api.ap-southeast-2.amazonaws.com/prod
```

Connect with the Cognito access token as a query string token:

```text
wss://<api-id>.execute-api.ap-southeast-2.amazonaws.com/prod?token=<cognito-access-token>
```

If the token is missing or invalid, `$connect` returns `401`.

## Sending A User Turn

After the socket opens, send a JSON message with action `requestAccess`.

Minimum payload:

```json
{
  "action": "requestAccess",
  "requestId": "turn-uuid",
  "message": "tell a story about ducks"
}
```

Preferred frontend payload:

```json
{
  "action": "requestAccess",
  "requestId": "turn-uuid",
  "threadId": "thread-uuid",
  "parentId": "turn-uuid",
  "tenantId": "tenant-or-demo-id",
  "caseId": "case-or-demo-id",
  "message": "tell a story about ducks"
}
```

`message`, `prompt`, or `reason` can hold the user text. Prefer `message` for chat.

Do not send `user_id`. The backend ignores user IDs from the client and uses the Cognito user from the WebSocket authorizer.

## Top-Level Server Messages

The server sends four top-level message types:

```text
ack
stream
error
done
```

### `ack`

Sent first after the backend accepts the turn and invokes the worker Lambda.

```json
{
  "type": "ack",
  "requestId": "turn-uuid"
}
```

Use this to mark the turn as accepted.

### `error`

Sent when the turn cannot continue.

```json
{
  "type": "error",
  "requestId": "turn-uuid",
  "error": "invalid_request",
  "message": "Missing required field(s): requestId.",
  "missing": ["requestId"]
}
```

Known errors:

- `invalid_request`
- `openai_secret_check_failed`
- `agent_stream_failed`

### `done`

Sent after the agent stream finishes and after the `end_turn` marker.

```json
{
  "type": "done",
  "requestId": "turn-uuid"
}
```

Use this as the final backend completion signal.

## Rich Stream Envelope

All UI-renderable assistant events are sent as top-level `type: "stream"`.

```json
{
  "type": "stream",
  "requestId": "turn-uuid",
  "tenantId": "tenant-or-user-id",
  "threadId": "thread-uuid",
  "caseId": "case-or-demo-id",
  "parentId": "turn-uuid",
  "streamType": "delta",
  "timestamp": 1777444500000,
  "sequenceId": 12,
  "data": []
}
```

Frontend rules:

- Sort or apply by `sequenceId`.
- `sequenceId` is monotonic within one worker run.
- `parentId` is the assistant turn ID.
- `threadId` groups turns into one chat thread.
- `data` is always an array.
- Ignore unknown fields so the backend can add fields later.

## Stream Types

### `message_marker`

Markers announce agent phases.

```json
{
  "type": "stream",
  "streamType": "message_marker",
  "data": [{ "marker": "cot_token" }]
}
```

Markers:

- `cot_token`: model/agent turn started. Show thinking state.
- `generating_summary`: final model output item started. Show a generating-answer tool/status row if useful.
- `user_visible_token`: final answer tokens are about to stream. Stop generic thinking state and show the answer block.
- `end_turn`: agent turn has finished. Close loaders and wait for top-level `done`.

Expected order for a normal turn:

```text
ack
stream message_marker cot_token
stream completed_message tool_call
stream delta replace tool_call completed
stream message_marker generating_summary
stream message_marker user_visible_token
stream delta add assistant_message
stream delta append assistant_message ...
stream delta patch assistant_message completed
stream message_marker end_turn
done
```

Reasoning summary markers/events may appear between `cot_token` and tool/final-answer events when the model emits them.

### `completed_message`

Used for full message objects, currently mainly tool calls.

```json
{
  "type": "stream",
  "streamType": "completed_message",
  "data": [
    {
      "operation": "add",
      "id": "tool-message-id",
      "message": {
        "id": "tool-message-id",
        "caseId": "case-or-demo-id",
        "tenantId": "tenant-or-user-id",
        "createdAt": "2026-04-29T04:35:00Z",
        "itemType": "assistantMessage",
        "data": {
          "threadId": "thread-uuid",
          "groupId": "turn-uuid",
          "parentId": "turn-uuid",
          "order": 1,
          "type": "tool_call",
          "role": null,
          "status": "in_progress",
          "summary": null,
          "arguments": "{\"reason\":\"demo\"}",
          "tool_name": "check_agent_employee_access",
          "call_id": "call-id",
          "output": null,
          "content": null,
          "thoughtFor": null,
          "taggedEvidence": [],
          "annotations": []
        }
      }
    }
  ]
}
```

Frontend behavior:

- On `operation: "add"`, add the message to the current turn.
- For `type: "tool_call"`, show a tool row using `tool_name`.
- Do not show raw tool output unless the UI explicitly needs it.

### `delta`

Used for incremental updates.

Common delta payload:

```json
{
  "type": "stream",
  "streamType": "delta",
  "data": [
    {
      "type": "assistant_message",
      "operation": "append",
      "id": "assistant-message-id",
      "order": 2,
      "status": "in_progress",
      "content": " token text",
      "role": "assistant"
    }
  ]
}
```

Operations:

- `add`: create a streaming message block.
- `append`: append `content` to the message with matching `id`.
- `replace`: update an existing message, usually to mark a tool call completed.
- `patch`: replace an in-progress streaming block with the completed full message object.

Message types:

- `assistant_message`: final user-visible answer.
- `reasoning`: visible reasoning summary only, not private chain-of-thought.
- `tool_call`: a tool call lifecycle event.

## Assistant Answer Streaming

The final answer starts with:

```json
{
  "streamType": "delta",
  "data": [
    {
      "type": "assistant_message",
      "operation": "add",
      "id": "assistant-message-id",
      "status": "in_progress",
      "content": "Once",
      "role": "assistant"
    }
  ]
}
```

Then more tokens arrive as:

```json
{
  "streamType": "delta",
  "data": [
    {
      "type": "assistant_message",
      "operation": "append",
      "id": "assistant-message-id",
      "status": "in_progress",
      "content": " upon",
      "role": "assistant"
    }
  ]
}
```

Completion arrives as a `patch` event:

```json
{
  "streamType": "delta",
  "data": [
    {
      "operation": "patch",
      "message": {
        "id": "assistant-message-id",
        "data": {
          "type": "assistant_message",
          "status": "completed",
          "content": "Full final answer text"
        }
      }
    },
    {
      "operation": null,
      "id": "assistant-message-id",
      "type": "assistant_message",
      "status": "completed"
    }
  ]
}
```

Frontend behavior:

- Create the answer block on `add`.
- Append text on each `append`.
- On `patch`, replace the local message with `data[0].message` if present.

## Tool Call Streaming

The model tool call is sent as `completed_message` with `type: "tool_call"` and `status: "in_progress"`.

When the tool finishes, the backend sends:

```json
{
  "streamType": "delta",
  "data": [
    {
      "type": "tool_call",
      "operation": "replace",
      "id": "tool-message-id",
      "status": "completed",
      "content": null
    }
  ]
}
```

Frontend behavior:

- Add the tool row from the `completed_message`.
- Mark that same row completed on `replace`.
- Match by `id`.

Current hard-coded demo tool:

```text
check_agent_employee_access
```

This exists so the frontend can build the tool-call UI before real broker-backed support tools are fully wired.

## Reasoning Summary Streaming

OpenAI does not expose hidden chain-of-thought tokens. The backend only forwards visible reasoning summary events when the model emits them.

Reasoning start:

```json
{
  "streamType": "delta",
  "data": [
    {
      "type": "reasoning",
      "operation": "add",
      "id": "reasoning-message-id",
      "status": "in_progress",
      "content": null
    }
  ]
}
```

Reasoning summary token:

```json
{
  "streamType": "delta",
  "data": [
    {
      "type": "reasoning",
      "operation": "append",
      "id": "reasoning-message-id",
      "status": "in_progress",
      "content": "Checking the user request against policy."
    }
  ]
}
```

Reasoning completion:

```json
{
  "streamType": "delta",
  "data": [
    {
      "operation": "patch",
      "message": {
        "id": "reasoning-message-id",
        "data": {
          "type": "reasoning",
          "status": "completed",
          "summary": ["Checking the user request against policy."]
        }
      }
    },
    {
      "operation": null,
      "id": "reasoning-message-id",
      "type": "reasoning",
      "status": "completed"
    }
  ]
}
```

Frontend behavior:

- Render reasoning in a collapsible thinking/details area.
- Treat reasoning as optional. Simple turns may not emit reasoning summary frames.
- Never expect raw private chain-of-thought.

The backend includes OpenAI `reasoning.encrypted_content` in model requests so reasoning state can continue correctly across model/tool turns. That encrypted content is for the OpenAI API, not the browser.

## Basic Frontend Listener Shape

```ts
const ws = new WebSocket(`${agentWsUrl}?token=${encodeURIComponent(accessToken)}`)

ws.onopen = () => {
  ws.send(JSON.stringify({
    action: 'requestAccess',
    requestId,
    threadId,
    parentId: turnId,
    message: userText,
  }))
}

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data)

  if (msg.type === 'ack') {
    markTurnAccepted(msg.requestId)
    return
  }

  if (msg.type === 'error') {
    markTurnErrored(msg)
    return
  }

  if (msg.type === 'done') {
    markTurnDone(msg.requestId)
    return
  }

  if (msg.type !== 'stream') return

  switch (msg.streamType) {
    case 'message_marker':
      handleMarker(msg.data[0].marker, msg)
      break
    case 'completed_message':
      handleCompletedMessage(msg.data[0], msg)
      break
    case 'delta':
      handleDelta(msg.data, msg)
      break
  }
}
```

## Smoke-Tested Live Behavior

The deployed endpoint has been tested with:

```json
{
  "action": "requestAccess",
  "requestId": "codex-rich-stream-smoke-1",
  "threadId": "codex-thread-1",
  "parentId": "codex-turn-1",
  "message": "tell a story about ducks"
}
```

Observed live sequence:

- unauthenticated connect returns `401`
- authenticated connect returns `101`
- `ack`
- `message_marker: cot_token`
- `completed_message` for `check_agent_employee_access`
- `delta replace` marking the tool call completed
- `message_marker: generating_summary`
- `message_marker: user_visible_token`
- many `assistant_message` token deltas
- `delta patch` completing the assistant message
- `message_marker: end_turn`
- `done`

