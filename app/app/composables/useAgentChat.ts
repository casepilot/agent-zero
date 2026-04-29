import { computed, reactive, ref } from 'vue'
import { useAmplifyAuth } from './useAmplifyAuth'

type TurnStatus = 'connecting' | 'waiting' | 'thinking' | 'answering' | 'complete' | 'failed'
type ToolStatus = 'in_progress' | 'completed' | 'error'
type ToolTone = 'running' | 'completed' | 'approved' | 'denied' | 'failed'

interface StreamEnvelope {
  type: 'stream'
  requestId?: string
  streamType?: 'message_marker' | 'delta' | 'completed_message'
  sequenceId?: number
  data?: unknown[]
}

interface ErrorMessage {
  type: 'error'
  requestId?: string
  error?: string
  message?: string
  missing?: string[]
}

interface TopLevelMessage {
  type?: string
  requestId?: string
}

export interface AgentToolCall {
  id: string
  name: string
  status: ToolStatus
  label: string
  statusLabel: string
  detail: string
  tone: ToolTone
  resultId?: string
}

export interface AgentChatTurn {
  id: string
  requestId: string
  threadId: string
  parentId: string
  userText: string
  answer: string
  reasoning: string
  reasoningSummary: string[]
  tools: AgentToolCall[]
  status: TurnStatus
  phase: string
  errorTitle: string
  errorMessage: string
  missing: string[]
  lastSequenceId: number
}

const ACTIVE_STATUSES: TurnStatus[] = ['connecting', 'waiting', 'thinking', 'answering']
const LOG_PREFIX = '[agent-chat]'

function cleanConfigValue(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function stringValue(value: unknown) {
  return typeof value === 'string' ? value : ''
}

function stringArray(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function createId(prefix: string) {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}-${crypto.randomUUID()}`
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function recordValue(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {}
}

function numberValue(value: unknown) {
  return typeof value === 'number' ? value : null
}

function parseToolOutput(value: unknown) {
  if (isRecord(value)) {
    return value
  }

  if (typeof value !== 'string' || !value.trim()) {
    return {}
  }

  try {
    const parsed = JSON.parse(value) as unknown
    return recordValue(parsed)
  } catch {
    return {}
  }
}

function parseToolArguments(value: unknown) {
  if (isRecord(value)) {
    return value
  }

  if (typeof value !== 'string' || !value.trim()) {
    return {}
  }

  try {
    const parsed = JSON.parse(value) as unknown
    return recordValue(parsed)
  } catch {
    return {}
  }
}

function humanizeIdentifier(value: string) {
  return value
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function bankResourceLabel(resourceKey: string) {
  switch (resourceKey) {
    case 'bank_customer_profiles':
      return 'customer profile records'
    case 'bank_balances':
      return 'account balances'
    case 'bank_transactions':
      return 'transaction history'
    case 'bank_operational_metrics':
      return 'bank operational metrics'
    case 'users_table':
      return 'bank user directory'
    case 'policy_table':
      return 'access policy records'
    case 'user_pool':
      return 'bank sign-in users'
    default:
      return resourceKey ? humanizeIdentifier(resourceKey).toLowerCase() : 'bank records'
  }
}

function operationLabel(operation: string) {
  switch (operation) {
    case 'get_item':
      return 'reading'
    case 'query_by_user_id':
      return 'querying'
    case 'scan':
      return 'scanning'
    case 'put_item':
      return 'writing'
    case 'update_item':
      return 'updating'
    case 'delete_item':
      return 'deleting'
    default:
      return operation ? humanizeIdentifier(operation).toLowerCase() : 'accessing'
  }
}

function pastOperationLabel(operation: string) {
  switch (operation) {
    case 'get_item':
      return 'read'
    case 'query_by_user_id':
      return 'queried'
    case 'scan':
      return 'scanned'
    case 'put_item':
      return 'wrote'
    case 'update_item':
      return 'updated'
    case 'delete_item':
      return 'deleted'
    default:
      return operation ? humanizeIdentifier(operation).toLowerCase() : 'accessed'
  }
}

function toolNameLabel(toolName: string) {
  return humanizeIdentifier(toolName || 'bank workflow step')
}

function toolBaseLabel(toolName: string) {
  switch (toolName) {
    case 'list_known_resources':
      return 'Loading bank data catalog'
    case 'run_dynamodb_operation':
      return 'Checking bank data access'
    case 'request_aws_access':
      return 'Requesting AgentZero bank access review'
    case 'write_user_policy':
      return 'Updating bank access policy'
    case 'create_cognito_user':
      return 'Creating bank application user'
    default:
      return `Running bank workflow step: ${toolNameLabel(toolName)}`
  }
}

function bankCatalogDetail(resources: unknown) {
  if (!Array.isArray(resources)) {
    return 'Checking which bank data sources the agent can safely use.'
  }

  const labels = resources
    .map((resource) => isRecord(resource) ? bankResourceLabel(stringValue(resource.resource_key)) : '')
    .filter(Boolean)

  if (!labels.length) {
    return 'No bank data sources were returned.'
  }

  return `Available sources: ${Array.from(new Set(labels)).join(', ')}.`
}

function initialToolPresentation(toolName: string, status: ToolStatus, args: Record<string, unknown> = {}) {
  const resourceKey = stringValue(args.resource_key)
  const operation = stringValue(args.operation)
  const group = stringValue(args.group)

  if (status === 'error') {
    return {
      label: toolBaseLabel(toolName),
      statusLabel: 'Failed',
      detail: 'The tool could not complete this step.',
      tone: 'failed' as ToolTone,
    }
  }

  if (toolName === 'run_dynamodb_operation' && (resourceKey || operation)) {
    return {
      label: `${humanizeIdentifier(operationLabel(operation))} ${bankResourceLabel(resourceKey)}`,
      statusLabel: status === 'completed' ? 'Complete' : 'Running',
      detail: `Bank data source: ${bankResourceLabel(resourceKey)}. Operation: ${operation ? humanizeIdentifier(operation) : 'Access'}.`,
      tone: status === 'completed' ? 'completed' as ToolTone : 'running' as ToolTone,
    }
  }

  if (toolName === 'request_aws_access') {
    return {
      label: 'AgentZero is reviewing bank-data access',
      statusLabel: status === 'completed' ? 'Complete' : 'Running',
      detail: 'The broker is checking the request against the signed-in user role and free-text access policy.',
      tone: status === 'completed' ? 'completed' as ToolTone : 'running' as ToolTone,
    }
  }

  if (toolName === 'list_known_resources') {
    return {
      label: 'Loading bank data catalog',
      statusLabel: status === 'completed' ? 'Complete' : 'Running',
      detail: 'Checking available bank tables: profiles, balances, transactions, operational metrics, users, and policies.',
      tone: status === 'completed' ? 'completed' as ToolTone : 'running' as ToolTone,
    }
  }

  if (toolName === 'write_user_policy') {
    const policyOperation = operation === 'delete_item' ? 'Deleting' : 'Writing'

    return {
      label: `${policyOperation} bank access policy`,
      statusLabel: status === 'completed' ? 'Complete' : 'Running',
      detail: 'Updating the policy record used for future access reviews.',
      tone: status === 'completed' ? 'completed' as ToolTone : 'running' as ToolTone,
    }
  }

  if (toolName === 'create_cognito_user') {
    return {
      label: 'Creating bank application user',
      statusLabel: status === 'completed' ? 'Complete' : 'Running',
      detail: group ? `Role group: ${humanizeIdentifier(group)}.` : 'Creating a Cognito user and matching bank directory row.',
      tone: status === 'completed' ? 'completed' as ToolTone : 'running' as ToolTone,
    }
  }

  if (status === 'completed') {
    return {
      label: toolBaseLabel(toolName),
      statusLabel: 'Complete',
      detail: '',
      tone: 'completed' as ToolTone,
    }
  }

  return {
    label: toolBaseLabel(toolName),
    statusLabel: 'Running',
    detail: '',
    tone: 'running' as ToolTone,
  }
}

function resultDecision(output: Record<string, unknown>) {
  const body = recordValue(output.body)
  const decision = recordValue(body.decision || output.decision)
  const approved = decision.approved

  return {
    body,
    decision,
    approved: typeof approved === 'boolean' ? approved : null,
    reason: stringValue(decision.reason),
  }
}

function errorCode(output: Record<string, unknown>) {
  const body = recordValue(output.body)
  return stringValue(output.error) || stringValue(body.error)
}

function isDeniedResult(output: Record<string, unknown>) {
  const { approved } = resultDecision(output)
  const body = recordValue(output.body)
  const code = errorCode(output)
  const statusCode = numberValue(output.status_code)

  return approved === false
    || statusCode === 403
    || stringValue(body.status) === 'denied'
    || ['access_denied', 'no_policy_found', 'AccessDeniedException'].includes(code)
}

function safeFailureDetail(output: Record<string, unknown>) {
  switch (errorCode(output)) {
    case 'missing_reason':
      return 'A clear business reason is required.'
    case 'missing_required_fields':
      return 'Required fields are missing.'
    case 'invalid_group':
      return 'The requested user role is not valid.'
    case 'unknown_resource':
      return 'The requested resource is not available.'
    case 'unsupported_operation':
      return 'The requested data operation is not supported.'
    case 'decision_failed':
    case 'llm_failed':
      return 'The access review service could not make a decision.'
    case 'audit_log_failed':
      return 'The access review could not be safely recorded.'
    case 'credential_issue_failed':
      return 'Temporary credentials could not be issued.'
    case 'AccessDeniedException':
    case 'access_denied':
      return 'Access was not granted for this step.'
    case 'no_policy_found':
      return 'No matching access policy was found.'
    default:
      return 'The tool could not complete this step.'
  }
}

function brokerDecisionDetail(output: Record<string, unknown>) {
  const { body, decision, reason } = resultDecision(output)
  const parts = [
    stringValue(decision.risk) ? `Risk: ${humanizeIdentifier(stringValue(decision.risk))}` : '',
    stringValue(decision.authorization) ? `Authorization: ${humanizeIdentifier(stringValue(decision.authorization))}` : '',
    typeof decision.duration_seconds === 'number'
      ? `Duration: ${Math.round(decision.duration_seconds / 60)} min`
      : '',
  ].filter(Boolean)

  if (reason) {
    return parts.length ? `${reason} ${parts.join(' • ')}.` : reason
  }

  if (output.ok === true || stringValue(body.status) === 'approved') {
    return parts.length
      ? `Temporary scoped access was approved. ${parts.join(' • ')}.`
      : 'Temporary scoped access was approved.'
  }

  return safeFailureDetail(output)
}

function dataOperationDetail(output: Record<string, unknown>) {
  const response = recordValue(output.response)
  const resourceKey = stringValue(output.resource_key)
  const operation = stringValue(output.operation)
  const prefix = `${humanizeIdentifier(pastOperationLabel(operation))} ${bankResourceLabel(resourceKey)}`
  const items = response.Items

  if (Array.isArray(items)) {
    return `${prefix}; returned ${items.length} ${items.length === 1 ? 'record' : 'records'}.`
  }

  if (isRecord(response.Item)) {
    return `${prefix}; returned 1 record.`
  }

  if (isRecord(response.Attributes)) {
    return `${prefix}; returned the updated record.`
  }

  return `${prefix}; operation completed.`
}

function summarizeToolResult(toolName: string, status: ToolStatus, output: Record<string, unknown>) {
  const ok = output.ok === true
  const denied = isDeniedResult(output)

  if (toolName === 'request_aws_access') {
    if (ok) {
      return {
        label: 'Access review complete',
        statusLabel: 'Approved',
        detail: brokerDecisionDetail(output),
        tone: 'approved' as ToolTone,
      }
    }

    if (denied) {
      return {
        label: 'Access review complete',
        statusLabel: 'Denied',
        detail: brokerDecisionDetail(output),
        tone: 'denied' as ToolTone,
      }
    }

    return {
      label: 'Access review failed',
      statusLabel: 'Failed',
      detail: safeFailureDetail(output),
      tone: 'failed' as ToolTone,
    }
  }

  if (toolName === 'list_known_resources') {
    const resources = Array.isArray(output.resources) ? output.resources.length : 0

    return {
      label: 'Bank data catalog loaded',
      statusLabel: ok ? 'Complete' : 'Failed',
      detail: ok
        ? `${resources} ${resources === 1 ? 'source is' : 'sources are'} available. ${bankCatalogDetail(output.resources)}`
        : safeFailureDetail(output),
      tone: ok ? 'completed' as ToolTone : 'failed' as ToolTone,
    }
  }

  if (toolName === 'run_dynamodb_operation') {
    const resourceKey = stringValue(output.resource_key)
    const operation = stringValue(output.operation)

    if (ok) {
      return {
        label: `${humanizeIdentifier(pastOperationLabel(operation))} ${bankResourceLabel(resourceKey)}`,
        statusLabel: 'Approved',
        detail: dataOperationDetail(output),
        tone: 'approved' as ToolTone,
      }
    }

    if (denied) {
      return {
        label: `${humanizeIdentifier(operationLabel(operation))} ${bankResourceLabel(resourceKey)} blocked`,
        statusLabel: 'Denied',
        detail: `${bankResourceLabel(resourceKey)} access was not granted for ${operation ? humanizeIdentifier(operation).toLowerCase() : 'this operation'}.`,
        tone: 'denied' as ToolTone,
      }
    }

    return {
      label: `${humanizeIdentifier(operationLabel(operation))} ${bankResourceLabel(resourceKey)} failed`,
      statusLabel: 'Failed',
      detail: safeFailureDetail(output),
      tone: 'failed' as ToolTone,
    }
  }

  if (toolName === 'write_user_policy') {
    if (ok) {
      return {
        label: 'Bank access policy updated',
        statusLabel: 'Approved',
        detail: 'The access policy was updated.',
        tone: 'approved' as ToolTone,
      }
    }

    return {
      label: denied ? 'Bank policy update blocked' : 'Bank policy update failed',
      statusLabel: denied ? 'Denied' : 'Failed',
      detail: safeFailureDetail(output),
      tone: denied ? 'denied' as ToolTone : 'failed' as ToolTone,
    }
  }

  if (toolName === 'create_cognito_user') {
    const group = stringValue(output.group)

    if (ok) {
      return {
        label: 'Bank application user created',
        statusLabel: 'Approved',
        detail: group ? `Created or updated a ${humanizeIdentifier(group)} sign-in user.` : 'The bank application user was created or updated.',
        tone: 'approved' as ToolTone,
      }
    }

    return {
      label: denied ? 'Bank user creation blocked' : 'Bank user creation failed',
      statusLabel: denied ? 'Denied' : 'Failed',
      detail: safeFailureDetail(output),
      tone: denied ? 'denied' as ToolTone : 'failed' as ToolTone,
    }
  }

  if (status === 'error' || !ok) {
    return {
      label: toolBaseLabel(toolName),
      statusLabel: denied ? 'Denied' : 'Failed',
      detail: safeFailureDetail(output),
      tone: denied ? 'denied' as ToolTone : 'failed' as ToolTone,
    }
  }

  return {
    label: toolBaseLabel(toolName),
    statusLabel: 'Complete',
    detail: 'Tool step completed.',
    tone: 'completed' as ToolTone,
  }
}

function buildErrorMessage(error: unknown) {
  return error instanceof Error && error.message
    ? error.message
    : 'Unable to reach the agent. Try again.'
}

function logInfo(event: string, fields: Record<string, unknown> = {}) {
  console.info(LOG_PREFIX, event, fields)
}

function logWarn(event: string, fields: Record<string, unknown> = {}) {
  console.warn(LOG_PREFIX, event, fields)
}

function logError(event: string, fields: Record<string, unknown> = {}) {
  console.error(LOG_PREFIX, event, fields)
}

function endpointDetails(url: string) {
  try {
    const parsedUrl = new URL(url)

    return {
      protocol: parsedUrl.protocol,
      host: parsedUrl.host,
      pathname: parsedUrl.pathname,
    }
  } catch {
    return {
      protocol: '',
      host: '',
      pathname: '',
    }
  }
}

function decodeBase64Url(value: string) {
  if (typeof atob !== 'function') {
    return ''
  }

  const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
  return atob(padded)
}

function tokenMetadata(accessToken: string) {
  const tokenPayload = accessToken.split('.')[1]

  if (!tokenPayload) {
    return { available: false }
  }

  try {
    const payload = JSON.parse(decodeBase64Url(tokenPayload)) as Record<string, unknown>
    const expiresAtSeconds = typeof payload.exp === 'number' ? payload.exp : 0
    const issuedAtSeconds = typeof payload.iat === 'number' ? payload.iat : 0
    const groups = Array.isArray(payload['cognito:groups'])
      ? payload['cognito:groups'].map(String)
      : []

    return {
      available: true,
      tokenUse: payload.token_use,
      clientId: payload.client_id,
      issuer: payload.iss,
      subject: payload.sub,
      username: payload.username,
      groups,
      issuedAt: issuedAtSeconds ? new Date(issuedAtSeconds * 1000).toISOString() : '',
      expiresAt: expiresAtSeconds ? new Date(expiresAtSeconds * 1000).toISOString() : '',
      expiresInSeconds: expiresAtSeconds ? Math.round(expiresAtSeconds - Date.now() / 1000) : null,
    }
  } catch (error) {
    return {
      available: false,
      error: buildErrorMessage(error),
    }
  }
}

function summarizeStreamData(streamType: StreamEnvelope['streamType'], data: unknown[]) {
  if (streamType === 'message_marker') {
    const firstItem = data[0]
    return {
      marker: isRecord(firstItem) ? firstItem.marker : undefined,
    }
  }

  if (streamType === 'delta') {
    return {
      count: data.length,
      items: data.map((item) => {
        if (!isRecord(item)) {
          return { type: typeof item }
        }

        return {
          type: item.type,
          operation: item.operation,
          status: item.status,
          id: item.id,
          contentLength: typeof item.content === 'string' ? item.content.length : 0,
          patchType: isRecord(item.message) && isRecord(item.message.data)
            ? item.message.data.type
            : undefined,
        }
      }),
    }
  }

  if (streamType === 'completed_message') {
    return {
      count: data.length,
      items: data.map((item) => {
        if (!isRecord(item) || !isRecord(item.message)) {
          return { type: typeof item }
        }

        const messageData = isRecord(item.message.data) ? item.message.data : {}

        return {
          operation: item.operation,
          id: item.id,
          messageType: messageData.type,
          status: messageData.status,
          toolName: messageData.tool_name,
        }
      }),
    }
  }

  return { count: data.length }
}

export function useAgentChat() {
  const runtimeConfig = useRuntimeConfig()
  const agentWsUrl = cleanConfigValue(runtimeConfig.public.agentWsUrl)
  const { getAccessToken } = useAmplifyAuth()
  const turns = reactive<AgentChatTurn[]>([])
  const revision = ref(0)
  const threadId = createId('thread')
  const setupError = computed(() => agentWsUrl ? '' : 'Agent WebSocket URL is not configured.')
  const isBusy = computed(() => turns.some((turn) => ACTIVE_STATUSES.includes(turn.status)))
  const connectionState = ref<'idle' | 'connecting' | 'open' | 'closed'>('idle')

  let socket: WebSocket | null = null
  let connectPromise: Promise<WebSocket> | null = null
  let activeRequestId = ''
  let intentionalClose = false

  function touch() {
    revision.value += 1
  }

  function findTurn(requestId?: string) {
    if (requestId) {
      return turns.find((turn) => turn.requestId === requestId)
    }

    return turns.find((turn) => turn.requestId === activeRequestId)
  }

  function markTurnFailed(turn: AgentChatTurn, title: string, message: string, missing: string[] = []) {
    turn.status = 'failed'
    turn.phase = 'Failed'
    turn.errorTitle = title
    turn.errorMessage = message
    turn.missing = missing

    if (activeRequestId === turn.requestId) {
      activeRequestId = ''
    }

    touch()
  }

  function closeSocket() {
    const currentSocket = socket
    connectPromise = null
    connectionState.value = 'closed'

    if (!currentSocket) {
      logInfo('socket_close_skipped', { reason: 'no_socket' })
      intentionalClose = false
      return
    }

    intentionalClose = true
    socket = null
    logInfo('socket_close_requested', {
      readyState: currentSocket.readyState,
      activeRequestId,
    })
    currentSocket.close()

    setTimeout(() => {
      intentionalClose = false
    }, 0)
  }

  function handleClose(closedSocket: WebSocket, event: CloseEvent) {
    if (socket === closedSocket) {
      socket = null
    }

    connectionState.value = 'closed'
    logWarn('socket_closed', {
      code: event.code,
      reason: event.reason,
      wasClean: event.wasClean,
      intentionalClose,
      activeRequestId,
    })

    const activeTurn = findTurn()
    if (!intentionalClose && activeTurn && ACTIVE_STATUSES.includes(activeTurn.status)) {
      markTurnFailed(
        activeTurn,
        'Connection closed',
        'The agent connection closed before the response finished.',
      )
    }

    intentionalClose = false
    socket = null
  }

  function openSocket(accessToken: string, forceRefresh: boolean) {
    return new Promise<WebSocket>((resolve, reject) => {
      const wsUrl = `${agentWsUrl}?token=${encodeURIComponent(accessToken)}`
      logInfo('socket_connect_start', {
        endpoint: endpointDetails(agentWsUrl),
        forceRefresh,
        token: tokenMetadata(accessToken),
      })

      const ws = new WebSocket(wsUrl)
      let opened = false
      let settled = false

      ws.onopen = () => {
        opened = true
        settled = true
        socket = ws
        connectionState.value = 'open'
        logInfo('socket_open', {
          readyState: ws.readyState,
          endpoint: endpointDetails(agentWsUrl),
        })
        resolve(ws)
      }

      ws.onmessage = (event) => {
        handleSocketMessage(event.data)
      }

      ws.onerror = () => {
        logError('socket_error', {
          opened,
          settled,
          readyState: ws.readyState,
          endpoint: endpointDetails(agentWsUrl),
        })

        if (!opened && !settled) {
          settled = true
          reject(new Error('Unable to connect to the agent.'))
        }
      }

      ws.onclose = (event) => {
        if (!opened && !settled) {
          settled = true
          logError('socket_connect_closed_before_open', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
            endpoint: endpointDetails(agentWsUrl),
          })
          reject(new Error(`Unable to authenticate the agent connection. Close code: ${event.code || 'unknown'}.`))
          return
        }

        if (socket === ws) {
          handleClose(ws, event)
        }
      }
    })
  }

  async function connect(forceRefresh = false) {
    if (!agentWsUrl) {
      logError('config_missing_agent_ws_url')
      throw new Error('Agent WebSocket URL is not configured.')
    }

    if (import.meta.server) {
      logError('connect_rejected_on_server')
      throw new Error('Agent chat can only connect from the browser.')
    }

    connectionState.value = 'connecting'
    logInfo('token_fetch_start', { forceRefresh })
    const accessToken = await getAccessToken(forceRefresh)

    if (!accessToken) {
      logError('token_fetch_empty', { forceRefresh })
      throw new Error('No active session was found.')
    }

    logInfo('token_fetch_success', {
      forceRefresh,
      token: tokenMetadata(accessToken),
    })

    return openSocket(accessToken, forceRefresh)
  }

  async function getOpenSocket() {
    if (socket?.readyState === WebSocket.OPEN) {
      return socket
    }

    if (connectPromise) {
      return connectPromise
    }

    connectPromise = (async () => {
      try {
        return await connect(false)
      } catch (error) {
        logWarn('socket_connect_retrying_with_forced_refresh', {
          error: buildErrorMessage(error),
        })
        closeSocket()
        return connect(true)
      } finally {
        connectPromise = null
      }
    })()

    return connectPromise
  }

  function buildPayload(turn: AgentChatTurn) {
    return {
      action: 'requestAccess',
      requestId: turn.requestId,
      threadId: turn.threadId,
      parentId: turn.parentId,
      message: turn.userText,
    }
  }

  async function sendPrompt(userText: string) {
    const text = userText.trim()

    if (!text || isBusy.value) {
      return
    }

    const turn: AgentChatTurn = {
      id: createId('turn'),
      requestId: createId('request'),
      threadId,
      parentId: createId('parent'),
      userText: text,
      answer: '',
      reasoning: '',
      reasoningSummary: [],
      tools: [],
      status: 'connecting',
      phase: 'Connecting',
      errorTitle: '',
      errorMessage: '',
      missing: [],
      lastSequenceId: 0,
    }

    turns.push(turn)
    activeRequestId = turn.requestId
    logInfo('turn_created', {
      requestId: turn.requestId,
      threadId: turn.threadId,
      parentId: turn.parentId,
      promptLength: text.length,
    })
    touch()

    try {
      const ws = await getOpenSocket()
      turn.status = 'waiting'
      turn.phase = 'Waiting for agent'
      ws.send(JSON.stringify(buildPayload(turn)))
      logInfo('turn_sent', {
        requestId: turn.requestId,
        threadId: turn.threadId,
        parentId: turn.parentId,
        readyState: ws.readyState,
      })
      touch()
    } catch (error) {
      logError('turn_send_failed', {
        requestId: turn.requestId,
        error: buildErrorMessage(error),
      })
      markTurnFailed(turn, 'Connection failed', buildErrorMessage(error))

      if (buildErrorMessage(error).includes('No active session')) {
        await navigateTo('/login')
      }
    }
  }

  async function retryTurn(turn: AgentChatTurn) {
    if (isBusy.value || turn.status !== 'failed') {
      return
    }

    turn.requestId = createId('request')
    turn.parentId = createId('parent')
    turn.answer = ''
    turn.reasoning = ''
    turn.reasoningSummary = []
    turn.tools = []
    turn.status = 'connecting'
    turn.phase = 'Connecting'
    turn.errorTitle = ''
    turn.errorMessage = ''
    turn.missing = []
    turn.lastSequenceId = 0
    activeRequestId = turn.requestId
    logInfo('turn_retry_started', {
      requestId: turn.requestId,
      threadId: turn.threadId,
      parentId: turn.parentId,
      promptLength: turn.userText.length,
    })
    touch()

    try {
      const ws = await getOpenSocket()
      turn.status = 'waiting'
      turn.phase = 'Waiting for agent'
      ws.send(JSON.stringify(buildPayload(turn)))
      logInfo('turn_retry_sent', {
        requestId: turn.requestId,
        threadId: turn.threadId,
        parentId: turn.parentId,
        readyState: ws.readyState,
      })
      touch()
    } catch (error) {
      logError('turn_retry_failed', {
        requestId: turn.requestId,
        error: buildErrorMessage(error),
      })
      markTurnFailed(turn, 'Retry failed', buildErrorMessage(error))

      if (buildErrorMessage(error).includes('No active session')) {
        await navigateTo('/login')
      }
    }
  }

  function markAccepted(message: TopLevelMessage) {
    const turn = findTurn(message.requestId)

    if (!turn || turn.status === 'failed' || turn.status === 'complete') {
      return
    }

    turn.status = 'waiting'
    turn.phase = 'Accepted'
    logInfo('turn_ack', { requestId: turn.requestId })
    touch()
  }

  function markDone(message: TopLevelMessage) {
    const turn = findTurn(message.requestId)

    if (!turn || turn.status === 'failed') {
      return
    }

    turn.status = 'complete'
    turn.phase = 'Complete'

    if (activeRequestId === turn.requestId) {
      activeRequestId = ''
    }

    logInfo('turn_done', { requestId: turn.requestId })
    touch()
  }

  function markBackendError(message: ErrorMessage) {
    const turn = findTurn(message.requestId)

    if (!turn) {
      return
    }

    markTurnFailed(
      turn,
      message.error || 'Agent error',
      message.message || 'The agent could not finish this turn.',
      message.missing || [],
    )
    logError('turn_backend_error', {
      requestId: turn.requestId,
      error: message.error,
      message: message.message,
      missing: message.missing,
    })
  }

  function handleSocketMessage(rawData: unknown) {
    let message: unknown

    try {
      message = JSON.parse(String(rawData))
    } catch (error) {
      logWarn('message_parse_failed', {
        error: buildErrorMessage(error),
        rawType: typeof rawData,
      })
      return
    }

    if (!isRecord(message)) {
      logWarn('message_ignored_non_object', { rawType: typeof message })
      return
    }

    logInfo('message_received', {
      type: message.type,
      requestId: message.requestId,
      streamType: message.streamType,
      sequenceId: message.sequenceId,
    })

    if (message.type === 'ack') {
      markAccepted(message as TopLevelMessage)
      return
    }

    if (message.type === 'done') {
      markDone(message as TopLevelMessage)
      return
    }

    if (message.type === 'error') {
      markBackendError(message as ErrorMessage)
      return
    }

    if (message.type === 'stream') {
      handleStreamMessage(message as StreamEnvelope)
    }
  }

  function handleStreamMessage(message: StreamEnvelope) {
    const turn = findTurn(message.requestId)

    if (!turn || turn.status === 'failed' || turn.status === 'complete') {
      logWarn('stream_ignored_no_active_turn', {
        requestId: message.requestId,
        streamType: message.streamType,
        sequenceId: message.sequenceId,
      })
      return
    }

    if (typeof message.sequenceId === 'number') {
      if (message.sequenceId <= turn.lastSequenceId) {
        logWarn('stream_ignored_duplicate_or_old_sequence', {
          requestId: message.requestId,
          streamType: message.streamType,
          sequenceId: message.sequenceId,
          lastSequenceId: turn.lastSequenceId,
        })
        return
      }

      turn.lastSequenceId = message.sequenceId
    }

    const data = Array.isArray(message.data) ? message.data : []
    logInfo('stream_apply', {
      requestId: turn.requestId,
      streamType: message.streamType,
      sequenceId: message.sequenceId,
      summary: summarizeStreamData(message.streamType, data),
    })

    if (message.streamType === 'message_marker') {
      handleMarker(turn, data[0])
      return
    }

    if (message.streamType === 'completed_message') {
      data.forEach((item) => handleCompletedMessage(turn, item))
      touch()
      return
    }

    if (message.streamType === 'delta') {
      data.forEach((item) => handleDelta(turn, item))
      touch()
    }
  }

  function handleMarker(turn: AgentChatTurn, markerData: unknown) {
    if (!isRecord(markerData)) {
      return
    }

    const marker = markerData.marker

    if (marker === 'cot_token') {
      turn.status = 'thinking'
      turn.phase = 'Thinking'
    } else if (marker === 'generating_summary') {
      turn.phase = 'Preparing answer'
    } else if (marker === 'user_visible_token') {
      turn.status = 'answering'
      turn.phase = 'Answering'
    } else if (marker === 'end_turn') {
      turn.phase = 'Finishing'
    }

    touch()
  }

  function handleCompletedMessage(turn: AgentChatTurn, item: unknown) {
    if (!isRecord(item) || item.operation !== 'add' || !isRecord(item.message)) {
      return
    }

    const message = item.message
    const data = isRecord(message.data) ? message.data : {}

    if (data.type === 'tool_result') {
      handleToolResult(
        turn,
        stringValue(message.id) || stringValue(item.id) || createId('tool-result'),
        data,
      )
      return
    }

    if (data.type !== 'tool_call') {
      return
    }

    const name = stringValue(data.tool_name) || 'tool_call'
    const status = stringValue(data.status) === 'completed' ? 'completed' : 'in_progress'
    const args = parseToolArguments(data.arguments)

    upsertTool(turn, {
      id: stringValue(message.id) || stringValue(item.id) || createId('tool'),
      name,
      status,
      ...initialToolPresentation(name, status, args),
    })
  }

  function handleDelta(turn: AgentChatTurn, item: unknown) {
    if (!isRecord(item)) {
      return
    }

    if (item.operation === 'patch' && isRecord(item.message)) {
      patchMessage(turn, item.message)
      return
    }

    if (item.type === 'assistant_message') {
      turn.status = 'answering'
      turn.phase = 'Answering'

      if (item.operation === 'add') {
        turn.answer = stringValue(item.content)
      } else if (item.operation === 'append') {
        turn.answer += stringValue(item.content)
      }
      return
    }

    if (item.type === 'reasoning') {
      turn.status = turn.status === 'answering' ? 'answering' : 'thinking'
      turn.phase = turn.status === 'answering' ? 'Answering' : 'Thinking'

      if (item.operation === 'append') {
        turn.reasoning += stringValue(item.content)
      }
      return
    }

    if (item.type === 'tool_result') {
      handleToolResult(turn, stringValue(item.id) || createId('tool-result'), item)
      return
    }

    if (item.type === 'tool_call' && item.operation === 'replace') {
      const tool = turn.tools.find((candidate) => candidate.id === item.id)

      if (tool) {
        tool.status = stringValue(item.status) === 'completed' ? 'completed' : tool.status
      }
    }
  }

  function handleToolResult(turn: AgentChatTurn, messageId: string, data: Record<string, unknown>) {
    const name = stringValue(data.tool_name) || 'tool_result'
    const status = stringValue(data.status) === 'error' ? 'error' : 'completed'
    const output = parseToolOutput(data.output)
    const presentation = summarizeToolResult(name, status, output)
    const existing = [...turn.tools]
      .reverse()
      .find((tool) => tool.name === name && !tool.resultId)

    if (existing) {
      Object.assign(existing, {
        status,
        resultId: messageId,
        ...presentation,
      })
      return
    }

    upsertTool(turn, {
      id: messageId,
      name,
      status,
      resultId: messageId,
      ...presentation,
    })
  }

  function patchMessage(turn: AgentChatTurn, message: Record<string, unknown>) {
    const data = isRecord(message.data) ? message.data : {}

    if (data.type === 'assistant_message') {
      turn.answer = stringValue(data.content) || turn.answer
      return
    }

    if (data.type === 'reasoning') {
      const summary = stringArray(data.summary)
      turn.reasoningSummary = summary

      if (summary.length) {
        turn.reasoning = summary.join('\n')
      }
    }
  }

  function upsertTool(turn: AgentChatTurn, nextTool: AgentToolCall) {
    const existing = turn.tools.find((tool) => tool.id === nextTool.id)

    if (existing) {
      Object.assign(existing, nextTool)
      return
    }

    turn.tools.push(nextTool)
  }

  return {
    turns,
    revision,
    setupError,
    isBusy,
    connectionState,
    sendPrompt,
    retryTurn,
    close: closeSocket,
  }
}
