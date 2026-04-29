import { useAmplifyAuth } from '~/composables/useAmplifyAuth'

export default defineNuxtRouteMiddleware(async (to) => {
  if (to.path === '/') {
    return navigateTo('/chats', { replace: true })
  }

  if (import.meta.server) {
    return
  }

  const isLoginRoute = to.path === '/login'
  const { getCurrentUser } = useAmplifyAuth()

  try {
    await getCurrentUser()

    if (isLoginRoute) {
      return navigateTo('/chats', { replace: true })
    }
  } catch {
    if (!isLoginRoute) {
      return navigateTo('/login', { replace: true })
    }
  }
})
