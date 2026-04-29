<script setup lang="ts">
import MarkdownIt from 'markdown-it'
import {
  AlertCircle,
  Bot,
  Brain,
  CheckCircle2,
  LogOut,
  Loader2,
  RefreshCcw,
  SendHorizontal,
  ShieldCheck,
  Sparkles,
  UserRound,
  Wrench,
} from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { useAgentChat, type AgentChatTurn } from '~/composables/useAgentChat'
import { useAmplifyAuth, type AuthSessionProfile } from '~/composables/useAmplifyAuth'

const draft = ref('')
const messagesEl = ref<HTMLElement | null>(null)
const sessionProfile = ref<AuthSessionProfile | null>(null)
const sessionProfileError = ref('')
const markdown = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})
const defaultLinkOpen = markdown.renderer.rules.link_open
  || ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options))

markdown.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  token?.attrSet('target', '_blank')
  token?.attrSet('rel', 'noreferrer')

  return defaultLinkOpen(tokens, idx, options, env, self)
}

const { getSessionProfile, signOut: signOutFromAuth } = useAmplifyAuth()
const {
  turns,
  revision,
  setupError,
  isBusy,
  sendPrompt,
  retryTurn,
  close: closeAgentChat,
} = useAgentChat()

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
  closeAgentChat()

  try {
    await signOutFromAuth()
  } finally {
    await navigateTo('/login')
  }
}

async function sendMessage() {
  const text = draft.value.trim()

  if (!text || isBusy.value) {
    return
  }

  draft.value = ''
  await sendPrompt(text)
}

function turnStatusText(turn: AgentChatTurn) {
  if (turn.status === 'failed') {
    return turn.errorTitle || 'Failed'
  }

  if (turn.status === 'complete') {
    return 'Complete'
  }

  return turn.phase || 'Working'
}

function isTurnLoading(turn: AgentChatTurn) {
  return ['connecting', 'waiting', 'thinking', 'answering'].includes(turn.status)
}

function renderMarkdown(value: string) {
  return markdown.render(value)
}

function toolToneClass(tool: AgentChatTurn['tools'][number]) {
  if (tool.tone === 'approved' || tool.tone === 'completed') {
    return 'border-emerald-200/14 bg-emerald-300/[0.08] text-emerald-100'
  }

  if (tool.tone === 'denied') {
    return 'border-amber-200/18 bg-amber-300/[0.09] text-amber-100'
  }

  if (tool.tone === 'failed') {
    return 'border-red-300/18 bg-red-500/[0.10] text-red-100'
  }

  return 'border-sky-200/12 bg-slate-950/32 text-slate-300'
}

function toolStatusClass(tool: AgentChatTurn['tools'][number]) {
  if (tool.tone === 'approved' || tool.tone === 'completed') {
    return 'text-emerald-200'
  }

  if (tool.tone === 'denied') {
    return 'text-amber-200'
  }

  if (tool.tone === 'failed') {
    return 'text-red-200'
  }

  return 'text-sky-200'
}

function isToolLoading(tool: AgentChatTurn['tools'][number]) {
  return tool.tone === 'running'
}

function isToolSuccessful(tool: AgentChatTurn['tools'][number]) {
  return tool.tone === 'approved' || tool.tone === 'completed'
}

const displayName = computed(() => {
  const profile = sessionProfile.value

  if (!profile) {
    return 'Checking session'
  }

  return profile.username || 'Signed in user'
})

const roleToneClass = computed(() => {
  const role = sessionProfile.value?.role

  if (role === 'admin') {
    return 'border-amber-200/20 bg-amber-300/10 text-amber-100'
  }

  if (role === 'customer') {
    return 'border-emerald-200/20 bg-emerald-300/10 text-emerald-100'
  }

  return 'border-sky-200/20 bg-sky-300/10 text-sky-100'
})

watch(revision, () => scrollToBottom())

onMounted(async () => {
  scrollToBottom('auto')

  try {
    sessionProfile.value = await getSessionProfile()
  } catch (error) {
    sessionProfileError.value = error instanceof Error ? error.message : 'Unable to load session role.'
  }
})
onBeforeUnmount(() => {
  closeAgentChat()
})
</script>

<template>
  <main class="relative h-screen overflow-hidden bg-[#070b12] text-white">
    <div class="absolute inset-0 opacity-85">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_24%_12%,rgba(56,189,248,0.20),transparent_32%),radial-gradient(circle_at_82%_86%,rgba(59,130,246,0.13),transparent_30%),linear-gradient(135deg,#070b12_0%,#0d1320_48%,#05070b_100%)]" />
      <div class="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.045)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(circle_at_54%_46%,black,transparent_74%)]" />
    </div>

    <div class="login-rise absolute right-7 top-6 z-20 flex items-center gap-3">
      <div
        class="flex min-w-64 items-center gap-3 rounded-lg border px-4 py-3 shadow-[0_16px_50px_rgba(0,0,0,0.22)] backdrop-blur-xl"
        :class="roleToneClass"
      >
        <div class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/12">
          <ShieldCheck
            v-if="sessionProfile?.role === 'admin'"
            class="size-5"
          />
          <UserRound
            v-else
            class="size-5"
          />
        </div>
        <div class="min-w-0">
          <p class="truncate text-sm font-semibold leading-5">
            {{ sessionProfile?.roleLabel || 'Loading role' }}
          </p>
          <p class="truncate text-xs leading-5 opacity-75">
            {{ sessionProfileError || displayName }}
          </p>
        </div>
      </div>

      <Button
        type="button"
        variant="outline"
        class="h-10 border-white/12 bg-white/[0.06] px-4 text-sm text-slate-200 backdrop-blur-xl hover:bg-white/[0.10] hover:text-white"
        @click="signOut"
      >
        <LogOut class="size-4" />
        Sign out
      </Button>
    </div>

    <section class="login-rise relative flex h-screen min-w-0 flex-col">
      <div
        ref="messagesEl"
        class="min-h-0 flex-1 overflow-y-auto px-10 pb-40 pt-24"
      >
        <div class="mx-auto flex max-w-4xl flex-col gap-7">
          <div
            v-if="!turns.length"
            class="mx-auto flex min-h-[52vh] max-w-2xl flex-col items-center justify-center text-center"
          >
            <div class="mb-6 flex size-16 items-center justify-center rounded-lg bg-sky-300 text-slate-950 shadow-[0_0_38px_rgba(125,211,252,0.38)]">
              <Bot class="size-8" />
            </div>
            <p class="text-base font-medium text-sky-100/80">
              IAM Agent
            </p>
            <h1 class="mt-3 text-4xl font-semibold tracking-normal text-white">
              Ask for support access
            </h1>
            <p class="mt-4 max-w-xl text-base leading-7 text-slate-400">
              Start with the customer request, ticket context, or policy question you want the agent to handle.
            </p>
            <div
              v-if="sessionProfile"
              class="mt-6 inline-flex items-center gap-2 rounded-lg border px-4 py-2 text-sm"
              :class="roleToneClass"
            >
              <ShieldCheck class="size-4" />
              Current role: {{ sessionProfile.roleLabel }}
            </div>
          </div>

          <article
            v-for="turn in turns"
            :key="turn.id"
            class="flex flex-col gap-5"
          >
            <div class="flex justify-end">
              <div class="max-w-2xl rounded-lg bg-sky-300 px-5 py-4 text-[15px] leading-7 text-slate-950 shadow-[0_16px_50px_rgba(0,0,0,0.22)]">
                {{ turn.userText }}
              </div>
            </div>

            <div class="flex justify-start gap-4">
              <div class="mt-1 flex size-9 shrink-0 items-center justify-center rounded-lg bg-sky-300 text-slate-950 shadow-[0_0_26px_rgba(125,211,252,0.30)]">
                <Bot class="size-5" />
              </div>

              <div class="flex w-full max-w-2xl flex-col gap-3">
                <div class="rounded-lg border border-white/10 bg-white/[0.075] px-5 py-4 text-[15px] leading-7 text-slate-100 shadow-[0_16px_50px_rgba(0,0,0,0.22)] backdrop-blur-xl">
                  <div
                    v-if="turn.reasoning || turn.status === 'thinking' || turn.phase === 'Preparing answer'"
                    class="mb-4 rounded-lg border border-sky-200/10 bg-slate-950/34 px-4 py-3"
                  >
                    <details :open="turn.status === 'thinking' && !turn.reasoning">
                      <summary class="flex cursor-pointer list-none items-center gap-2 text-sm font-medium text-sky-100">
                        <Brain class="size-4" />
                        Thinking
                      </summary>
                      <p class="mt-3 whitespace-pre-wrap text-sm leading-6 text-slate-300">
                        <template v-if="turn.reasoning">
                          {{ turn.reasoning }}
                        </template>
                        <span
                          v-else
                          class="flex items-center gap-2"
                        >
                          <Loader2 class="size-4 animate-spin text-sky-200" />
                          Checking policy and request context.
                        </span>
                      </p>
                    </details>
                  </div>

                  <div
                    v-if="turn.tools.length"
                    class="mb-4 flex flex-col gap-2"
                  >
                    <div
                      v-for="tool in turn.tools"
                      :key="tool.id"
                      class="rounded-lg border px-3 py-2 text-sm"
                      :class="toolToneClass(tool)"
                    >
                      <div class="flex items-center justify-between gap-3">
                        <span class="flex min-w-0 items-center gap-2">
                          <Wrench
                            class="size-4 shrink-0"
                            :class="toolStatusClass(tool)"
                          />
                          <span class="min-w-0 text-sm font-medium leading-5">{{ tool.label }}</span>
                        </span>
                        <span
                          class="flex shrink-0 items-center gap-1.5 text-xs font-medium"
                          :class="toolStatusClass(tool)"
                        >
                          <CheckCircle2
                            v-if="isToolSuccessful(tool)"
                            class="size-3.5"
                          />
                          <AlertCircle
                            v-else-if="tool.tone === 'denied' || tool.tone === 'failed'"
                            class="size-3.5"
                          />
                          <Loader2
                            v-else-if="isToolLoading(tool)"
                            class="size-3.5 animate-spin"
                          />
                          {{ tool.statusLabel }}
                        </span>
                      </div>
                      <p
                        v-if="tool.detail"
                        class="mt-1.5 text-xs leading-5 opacity-75"
                      >
                        {{ tool.detail }}
                      </p>
                    </div>
                  </div>

                  <div
                    v-if="turn.answer"
                    class="markdown-body"
                    v-html="renderMarkdown(turn.answer)"
                  />
                  <div
                    v-else-if="turn.status !== 'failed'"
                    class="flex items-center gap-2 text-slate-300"
                  >
                    <Sparkles class="size-4 animate-pulse text-sky-200" />
                    {{ turnStatusText(turn) }}
                  </div>

                  <div
                    v-if="turn.status === 'failed'"
                    class="flex flex-col gap-4"
                    role="alert"
                  >
                    <div class="flex items-start gap-3 rounded-lg border border-red-300/20 bg-red-500/10 px-4 py-3 text-sm leading-6 text-red-100">
                      <AlertCircle class="mt-0.5 size-4 shrink-0 text-red-200" />
                      <div>
                        <p class="font-medium">
                          {{ turn.errorTitle }}
                        </p>
                        <p>{{ turn.errorMessage }}</p>
                        <p
                          v-if="turn.missing.length"
                          class="mt-1 text-red-100/78"
                        >
                          Missing: {{ turn.missing.join(', ') }}
                        </p>
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      class="self-start border-white/12 bg-white/[0.06] text-slate-200 hover:bg-white/[0.10] hover:text-white"
                      :disabled="isBusy"
                      @click="retryTurn(turn)"
                    >
                      <RefreshCcw class="size-4" />
                      Retry
                    </Button>
                  </div>
                </div>

                <div
                  v-if="isTurnLoading(turn)"
                  class="flex items-center gap-2 pl-1 text-xs uppercase tracking-[0.18em] text-slate-500"
                >
                  <span class="h-px w-6 bg-sky-200/30" />
                  {{ turnStatusText(turn) }}
                </div>
              </div>
            </div>
          </article>
        </div>
      </div>

      <div class="pointer-events-none absolute inset-x-0 bottom-0 px-10 pb-7 pt-12 [background:linear-gradient(to_top,#070b12_0%,rgba(7,11,18,0.92)_48%,transparent_100%)]">
        <div
          v-if="setupError"
          class="pointer-events-auto mx-auto mb-3 flex max-w-4xl items-center gap-3 rounded-lg border border-amber-300/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100"
        >
          <AlertCircle class="size-4 shrink-0" />
          {{ setupError }}
        </div>

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
            :disabled="isBusy || !draft.trim() || !!setupError"
          >
            <Loader2
              v-if="isBusy"
              class="size-5 animate-spin"
            />
            <SendHorizontal
              v-else
              class="size-5"
            />
            Send
          </Button>
        </form>
      </div>
    </section>
  </main>
</template>
