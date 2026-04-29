<script setup lang="ts">
import {
  Bot,
  CheckCircle2,
  Clock3,
  LogOut,
  MessageSquare,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useAmplifyAuth } from '~/composables/useAmplifyAuth'

type ChatRole = 'user' | 'assistant'

interface ChatSummary {
  id: string
  title: string
  preview: string
  timestamp: string
  status: 'ready' | 'active' | 'review'
}

interface ChatMessage {
  id: string
  role: ChatRole
  text: string
}

const chats: ChatSummary[] = [
  {
    id: 'flight-change',
    title: 'Flight change request',
    preview: 'Customer wants to update their own booking.',
    timestamp: 'Now',
    status: 'active',
  },
  {
    id: 'policy-review',
    title: 'Policy review',
    preview: 'Check whether read-only access should be granted.',
    timestamp: '9:42',
    status: 'review',
  },
  {
    id: 'prompt-injection',
    title: 'Prompt injection test',
    preview: 'Validate denial for sensitive internal records.',
    timestamp: 'Yesterday',
    status: 'ready',
  },
  {
    id: 'customer-profile',
    title: 'Customer profile lookup',
    preview: 'Find safe customer details for support context.',
    timestamp: 'Mon',
    status: 'ready',
  },
]

const messagesByChat = reactive<Record<string, ChatMessage[]>>({
  'flight-change': [
    {
      id: 'm1',
      role: 'assistant',
      text: 'I can help with customer support requests while keeping AWS access temporary and scoped.',
    },
    {
      id: 'm2',
      role: 'user',
      text: 'The customer wants to move flight QF402 to a later departure.',
    },
    {
      id: 'm3',
      role: 'assistant',
      text: 'I will check the booking context, request only the access needed, and avoid unrelated customer records.',
    },
  ],
  'policy-review': [
    {
      id: 'm4',
      role: 'assistant',
      text: 'Policy review mode is ready. Ask whether a requested action fits the principal policy.',
    },
  ],
  'prompt-injection': [
    {
      id: 'm5',
      role: 'assistant',
      text: 'Use this chat to test a prompt injection path that asks for sensitive internal records.',
    },
  ],
  'customer-profile': [
    {
      id: 'm6',
      role: 'assistant',
      text: 'Customer profile lookup is ready for safe support context.',
    },
  ],
})

const streamChunks = [
  'I am simulating the agent response. ',
  'First, I would identify the minimum AWS action needed for this customer support task. ',
  'Then I would ask the broker for a temporary session scoped to the booking record only. ',
  'If the request matches the free-text policy, the broker can approve narrow access. ',
  'If the prompt asks for unrelated or sensitive records, the broker should deny it and log the reason.',
]

const draft = ref('')
const isStreaming = ref(false)
const messagesEl = ref<HTMLElement | null>(null)
const { signOut: signOutFromAuth } = useAmplifyAuth()
let streamTimer: ReturnType<typeof setInterval> | undefined

const route = useRoute()
const routeChatId = computed(() => {
  const chatId = route.params.chatId

  return Array.isArray(chatId) ? chatId[0] : chatId
})

const activeChatId = computed(() => routeChatId.value ?? '')
const activeChat = computed(() => chats.find(chat => chat.id === activeChatId.value))
const activeMessages = computed(() => messagesByChat[activeChatId.value] ?? [])

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

async function selectChat(chatId: string) {
  await navigateTo(`/chats/${chatId}`)
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

  const chatMessages = messagesByChat[activeChatId.value]

  if (!chatMessages) {
    return
  }

  const timestamp = Date.now()

  chatMessages.push({
    id: `user-${timestamp}`,
    role: 'user',
    text,
  })

  const assistantMessage: ChatMessage = {
    id: `assistant-${timestamp}`,
    role: 'assistant',
    text: '',
  }

  chatMessages.push(assistantMessage)
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

watch(activeChatId, () => scrollToBottom('auto'))
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
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_26%_14%,rgba(56,189,248,0.20),transparent_32%),radial-gradient(circle_at_82%_84%,rgba(59,130,246,0.13),transparent_30%),linear-gradient(135deg,#070b12_0%,#0d1320_48%,#05070b_100%)]" />
      <div class="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.045)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(circle_at_54%_46%,black,transparent_74%)]" />
    </div>

    <div class="relative grid h-screen grid-cols-[288px_minmax(0,1fr)]">
      <aside class="login-rise flex h-screen flex-col border-r border-white/10 bg-slate-950/44 backdrop-blur-2xl">
        <div class="border-b border-white/10 px-5 py-5">
          <div class="flex items-center gap-3">
            <div class="flex size-10 items-center justify-center rounded-lg bg-sky-300 text-slate-950 shadow-[0_0_34px_rgba(125,211,252,0.35)]">
              <ShieldCheck class="size-5" />
            </div>
            <div>
              <p class="text-sm font-medium text-sky-100/75">
                IAM Agent
              </p>
              <h1 class="text-lg font-semibold tracking-normal">
                Chats
              </h1>
            </div>
          </div>
        </div>

        <nav class="min-h-0 flex-1 space-y-2 overflow-y-auto px-3 py-4">
          <button
            v-for="chat in chats"
            :key="chat.id"
            type="button"
            class="group relative w-full rounded-lg px-3 py-3 text-left transition-all"
            :class="chat.id === activeChatId
              ? 'bg-sky-300/12 text-white shadow-[inset_0_0_0_1px_rgba(125,211,252,0.18)]'
              : 'text-slate-300 hover:bg-white/[0.06] hover:text-white'"
            @click="selectChat(chat.id)"
          >
            <span
              class="absolute left-0 top-3 h-[calc(100%-1.5rem)] w-0.5 rounded-full transition-opacity"
              :class="chat.id === activeChatId ? 'bg-sky-300 opacity-100' : 'bg-transparent opacity-0'"
            />
            <span class="flex items-start justify-between gap-3 pl-2">
              <span class="min-w-0">
                <span class="block truncate text-sm font-semibold">
                  {{ chat.title }}
                </span>
                <span class="mt-1 line-clamp-2 block text-xs leading-5 text-slate-400">
                  {{ chat.preview }}
                </span>
              </span>
              <span class="shrink-0 text-[11px] text-slate-500">
                {{ chat.timestamp }}
              </span>
            </span>
          </button>
        </nav>

        <div class="space-y-4 border-t border-white/10 px-5 py-4 text-xs leading-5 text-slate-400">
          <Button
            type="button"
            variant="outline"
            class="h-10 w-full justify-start border-white/12 bg-white/[0.06] text-sm text-slate-200 hover:bg-white/[0.10] hover:text-white"
            @click="signOut"
          >
            <LogOut class="size-4" />
            Sign out
          </Button>

          <div>
            Demo stream mode
          </div>
          <span class="mt-2 flex items-center gap-2 text-sky-100/80">
            <span class="size-1.5 rounded-full bg-sky-300 shadow-[0_0_16px_rgba(125,211,252,0.7)]" />
            Local test script only
          </span>
        </div>
      </aside>

      <section class="login-rise relative flex h-screen min-w-0 flex-col [animation-delay:80ms]">
        <header class="z-10 flex h-20 shrink-0 items-center justify-between border-b border-white/10 bg-slate-950/28 px-8 backdrop-blur-xl">
          <div class="flex items-center gap-3">
            <div class="flex size-10 items-center justify-center rounded-lg border border-white/10 bg-white/[0.075] text-sky-200">
              <MessageSquare class="size-5" />
            </div>
            <div>
              <h2 class="text-xl font-semibold tracking-normal">
                {{ activeChat?.title ?? 'Unknown chat' }}
              </h2>
              <p class="mt-1 flex items-center gap-2 text-sm text-slate-400">
                <CheckCircle2 class="size-4 text-sky-300" />
                {{ activeChat ? 'Desktop demo conversation' : 'No matching chat route' }}
              </p>
            </div>
          </div>

          <div class="flex items-center gap-3 rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-slate-300">
            <Clock3 class="size-4 text-sky-200" />
            Broker simulation
          </div>
        </header>

        <div
          ref="messagesEl"
          class="min-h-0 flex-1 overflow-y-auto px-10 pb-40 pt-8"
        >
          <div
            v-if="activeChat"
            class="mx-auto flex max-w-4xl flex-col gap-5"
          >
            <article
              v-for="message in activeMessages"
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

          <div
            v-else
            class="mx-auto flex min-h-full max-w-xl flex-col items-center justify-center text-center"
          >
            <div class="relative mb-7 flex size-24 items-center justify-center">
              <div class="absolute inset-0 rounded-full bg-sky-300/15 blur-2xl" />
              <div class="relative flex size-16 items-center justify-center rounded-lg border border-white/12 bg-white/[0.075] text-sky-200 shadow-[0_0_34px_rgba(125,211,252,0.24)] backdrop-blur-xl">
                <MessageSquare class="size-8" />
              </div>
            </div>
            <p class="text-sm font-medium text-sky-100/80">
              Empty route
            </p>
            <h2 class="mt-3 text-3xl font-semibold tracking-normal text-white">
              This chat does not exist.
            </h2>
            <p class="mt-4 max-w-md text-base leading-7 text-slate-400">
              Choose a seeded chat from the left panel or return home to start from the empty state.
            </p>
            <NuxtLink
              to="/chats"
              class="mt-7 inline-flex h-11 items-center justify-center rounded-lg border border-white/12 bg-white/[0.075] px-4 text-sm font-medium text-slate-100 transition-colors hover:bg-white/[0.12] hover:text-white"
            >
              Back home
            </NuxtLink>
          </div>
        </div>

        <div
          v-if="activeChat"
          class="pointer-events-none absolute inset-x-0 bottom-0 px-10 pb-7 pt-12 [background:linear-gradient(to_top,#070b12_0%,rgba(7,11,18,0.92)_48%,transparent_100%)]"
        >
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
    </div>
  </main>
</template>
