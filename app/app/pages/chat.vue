<script setup lang="ts">
import {
  Bot,
  LogOut,
  SendHorizontal,
  Sparkles,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useAmplifyAuth } from '~/composables/useAmplifyAuth'

type ChatRole = 'user' | 'assistant'

interface ChatMessage {
  id: string
  role: ChatRole
  text: string
}

const streamChunks = [
  'I am simulating the agent response. ',
  'First, I would identify the minimum AWS action needed for this customer support task. ',
  'Then I would ask the broker for a temporary session scoped to the request only. ',
  'If the request matches the free-text policy, the broker can approve narrow access. ',
  'If the prompt asks for unrelated or sensitive records, the broker should deny it and log the reason.',
]

const messages = reactive<ChatMessage[]>([])
const draft = ref('')
const isStreaming = ref(false)
const messagesEl = ref<HTMLElement | null>(null)
const { signOut: signOutFromAuth } = useAmplifyAuth()
let streamTimer: ReturnType<typeof setInterval> | undefined

useHead({
  title: 'Chat | IAM Agent',
})

function scrollToBottom(behavior: ScrollBehavior = 'smooth') {
  nextTick(() => {
    requestAnimationFrame(() => {
      if (!messagesEl.value) {
        return
      }

      messagesEl.value.scrollTo({
        top: messagesEl.value.scrollHeight,
        behavior,
      })
    })
  })
}

async function signOut() {
  try {
    await signOutFromAuth()
  } finally {
    await navigateTo('/login')
  }
}

function sendMessage() {
  const text = draft.value.trim()

  if (!text || isStreaming.value) {
    return
  }

  const timestamp = Date.now()

  messages.push({
    id: `user-${timestamp}`,
    role: 'user',
    text,
  })

  const assistantMessage: ChatMessage = {
    id: `assistant-${timestamp}`,
    role: 'assistant',
    text: '',
  }

  messages.push(assistantMessage)
  draft.value = ''
  isStreaming.value = true
  scrollToBottom()

  let chunkIndex = 0
  streamTimer = setInterval(() => {
    assistantMessage.text += streamChunks[chunkIndex]
    chunkIndex += 1
    scrollToBottom()

    if (chunkIndex >= streamChunks.length) {
      clearInterval(streamTimer)
      streamTimer = undefined
      isStreaming.value = false
      scrollToBottom()
    }
  }, 520)
}

onMounted(() => scrollToBottom('auto'))
onBeforeUnmount(() => {
  if (streamTimer) {
    clearInterval(streamTimer)
  }
})
</script>

<template>
  <main class="relative h-screen overflow-hidden bg-[#070b12] text-white">
    <div class="absolute inset-0 opacity-85">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_24%_12%,rgba(56,189,248,0.20),transparent_32%),radial-gradient(circle_at_82%_86%,rgba(59,130,246,0.13),transparent_30%),linear-gradient(135deg,#070b12_0%,#0d1320_48%,#05070b_100%)]" />
      <div class="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.045)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(circle_at_54%_46%,black,transparent_74%)]" />
    </div>

    <Button
      type="button"
      variant="outline"
      class="login-rise absolute right-7 top-6 z-20 h-10 border-white/12 bg-white/[0.06] px-4 text-sm text-slate-200 backdrop-blur-xl hover:bg-white/[0.10] hover:text-white"
      @click="signOut"
    >
      <LogOut class="size-4" />
      Sign out
    </Button>

    <section class="login-rise relative flex h-screen min-w-0 flex-col">
      <div
        ref="messagesEl"
        class="min-h-0 flex-1 overflow-y-auto px-10 pb-40 pt-24"
      >
        <div class="mx-auto flex max-w-4xl flex-col gap-5">
          <article
            v-for="message in messages"
            :key="message.id"
            class="chat-message flex gap-4"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div
              v-if="message.role === 'assistant'"
              class="mt-1 flex size-9 shrink-0 items-center justify-center rounded-lg bg-sky-300 text-slate-950 shadow-[0_0_26px_rgba(125,211,252,0.30)]"
            >
              <Bot class="size-5" />
            </div>

            <div
              class="max-w-2xl rounded-lg px-5 py-4 text-[15px] leading-7 shadow-[0_16px_50px_rgba(0,0,0,0.22)]"
              :class="message.role === 'user'
                ? 'bg-sky-300 text-slate-950'
                : 'border border-white/10 bg-white/[0.075] text-slate-100 backdrop-blur-xl'"
            >
              <p v-if="message.text">
                {{ message.text }}
              </p>
              <div
                v-else
                class="flex items-center gap-2 text-slate-300"
              >
                <Sparkles class="size-4 animate-pulse text-sky-200" />
                Streaming response
              </div>
            </div>
          </article>
        </div>
      </div>

      <div class="pointer-events-none absolute inset-x-0 bottom-0 px-10 pb-7 pt-12 [background:linear-gradient(to_top,#070b12_0%,rgba(7,11,18,0.92)_48%,transparent_100%)]">
        <form
          class="pointer-events-auto mx-auto flex max-w-4xl items-end gap-3 rounded-lg border border-white/12 bg-white/[0.075] p-3 shadow-[0_24px_90px_rgba(0,0,0,0.42)] backdrop-blur-2xl"
          @submit.prevent="sendMessage"
        >
          <textarea
            v-model="draft"
            rows="1"
            placeholder="Ask the support agent to help with a customer request..."
            class="max-h-32 min-h-12 flex-1 resize-none bg-transparent px-3 py-3 text-base leading-6 text-white outline-none placeholder:text-slate-500"
            @keydown.enter.exact.prevent="sendMessage"
          />
          <Button
            type="submit"
            size="lg"
            class="h-12 shrink-0 bg-sky-300 px-5 text-slate-950 shadow-[0_16px_42px_rgba(56,189,248,0.22)] hover:bg-sky-200"
            :disabled="isStreaming || !draft.trim()"
          >
            <SendHorizontal class="size-5" />
            Send
          </Button>
        </form>
      </div>
    </section>
  </main>
</template>
