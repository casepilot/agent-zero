import { configureAmplifyAuth } from '~/composables/useAmplifyAuth'

export default defineNuxtPlugin(() => {
  configureAmplifyAuth()
})
