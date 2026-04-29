import { Amplify } from 'aws-amplify'
import {
  fetchAuthSession,
  getCurrentUser as amplifyGetCurrentUser,
  signIn,
  signOut as amplifySignOut,
} from 'aws-amplify/auth'

let isConfigured = false

export interface AuthSessionProfile {
  username: string
  subject: string
  groups: string[]
  role: 'admin' | 'employee' | 'customer' | 'unknown'
  roleLabel: string
}

function cleanConfigValue(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

export function configureAmplifyAuth() {
  if (isConfigured) {
    return true
  }

  const runtimeConfig = useRuntimeConfig()
  const userPoolId = cleanConfigValue(runtimeConfig.public.cognitoUserPoolId)
  const userPoolClientId = cleanConfigValue(runtimeConfig.public.cognitoUserPoolClientId)

  if (!userPoolId || !userPoolClientId) {
    return false
  }

  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        loginWith: {
          email: true,
        },
      },
    },
  })

  isConfigured = true

  return true
}

function requireAmplifyAuth() {
  if (!configureAmplifyAuth()) {
    throw new Error('Amplify Auth is not configured. Fill in the Cognito values in app/.env.')
  }
}

function groupsFromPayload(payload: Record<string, unknown>) {
  const groups = payload['cognito:groups']

  if (!Array.isArray(groups)) {
    return []
  }

  return groups.map(String).filter(Boolean)
}

function roleFromGroups(groups: string[]) {
  if (groups.includes('admin')) {
    return {
      role: 'admin' as const,
      roleLabel: 'Superuser / Admin',
    }
  }

  if (groups.includes('employee')) {
    return {
      role: 'employee' as const,
      roleLabel: 'Employee',
    }
  }

  if (groups.includes('customer')) {
    return {
      role: 'customer' as const,
      roleLabel: 'Customer',
    }
  }

  return {
    role: 'unknown' as const,
    roleLabel: 'Unknown role',
  }
}

export function getAmplifyAuthErrorMessage(error: unknown) {
  const name = typeof error === 'object' && error && 'name' in error
    ? String((error as { name?: unknown }).name)
    : ''

  if (name === 'NotAuthorizedException' || name === 'UserNotFoundException') {
    return 'Username or password is incorrect.'
  }

  if (name === 'UserNotConfirmedException') {
    return 'This account has not been confirmed yet.'
  }

  if (name === 'PasswordResetRequiredException') {
    return 'This password must be reset before signing in.'
  }

  if (name === 'AuthUserPoolException' || name === 'AuthTokenConfigException') {
    return 'Authentication is not configured yet. Fill in the Cognito values in app/.env.'
  }

  const message = error instanceof Error ? error.message : ''

  if (message.includes('not configured')) {
    return 'Authentication is not configured yet. Fill in the Cognito values in app/.env.'
  }

  return 'Unable to sign in. Check your details and try again.'
}

export function useAmplifyAuth() {
  return {
    async getCurrentUser() {
      requireAmplifyAuth()
      return amplifyGetCurrentUser()
    },

    async signInWithPassword(username: string, password: string) {
      requireAmplifyAuth()

      return signIn({
        username,
        password,
      })
    },

    async signOut() {
      if (!configureAmplifyAuth()) {
        return
      }

      await amplifySignOut()
    },

    async getAccessToken(forceRefresh = false) {
      requireAmplifyAuth()

      const session = await fetchAuthSession({ forceRefresh })
      return session.tokens?.accessToken?.toString() || ''
    },

    async getSessionProfile(forceRefresh = false): Promise<AuthSessionProfile> {
      requireAmplifyAuth()

      const session = await fetchAuthSession({ forceRefresh })
      const payload = session.tokens?.accessToken?.payload || {}
      const groups = groupsFromPayload(payload)
      const role = roleFromGroups(groups)

      return {
        username: typeof payload.username === 'string' ? payload.username : '',
        subject: typeof payload.sub === 'string' ? payload.sub : '',
        groups,
        ...role,
      }
    },
  }
}
