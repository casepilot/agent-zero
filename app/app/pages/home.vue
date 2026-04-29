<script setup lang="ts">
import { Bot, ClipboardCheck, KeyRound, ShieldCheck, UsersRound } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const demoAreas = [
  {
    icon: KeyRound,
    title: 'Request access',
    description: 'Ask for temporary AWS access with a clear reason and scoped action.',
  },
  {
    icon: UsersRound,
    title: 'Manage principals',
    description: 'Create human users, AI agents, and their free-text access policies.',
  },
  {
    icon: Bot,
    title: 'Support demo',
    description: 'Run customer support requests through the agent and broker flow.',
  },
]
</script>

<template>
  <main class="min-h-screen bg-[#070b12] text-white">
    <header class="border-b border-white/10 bg-slate-950/42">
      <div class="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
        <div class="flex items-center gap-3">
          <div class="flex size-10 items-center justify-center rounded-lg bg-sky-300 text-slate-950">
            <ShieldCheck class="size-5" />
          </div>
          <div>
            <p class="text-sm font-medium text-sky-100/75">
              IAM Agent
            </p>
            <h1 class="text-lg font-semibold">
              Home
            </h1>
          </div>
        </div>

        <Button
          type="button"
          variant="secondary"
          class="border border-white/12 bg-white/8 text-white hover:bg-white/14"
        >
          <ClipboardCheck class="size-4" />
          View requests
        </Button>
      </div>
    </header>

    <section class="mx-auto grid max-w-6xl gap-8 px-6 py-10 lg:grid-cols-[1.15fr_0.85fr]">
      <div class="rounded-lg border border-white/10 bg-white/[0.06] p-7 shadow-[0_18px_70px_rgba(0,0,0,0.28)]">
        <p class="text-sm font-medium uppercase tracking-normal text-sky-200/80">
          Zero standing privilege
        </p>
        <h2 class="mt-4 max-w-2xl text-3xl font-semibold tracking-normal">
          Temporary AWS access, approved just in time.
        </h2>
        <p class="mt-4 max-w-2xl text-base leading-7 text-slate-300">
          This home route is the post-login landing page for the hackathon UI. The full request, admin, and customer support flows are still being built.
        </p>
      </div>

      <div class="rounded-lg border border-sky-200/14 bg-sky-300/10 p-7">
        <p class="text-sm font-medium text-sky-100/80">
          Demo status
        </p>
        <div class="mt-5 space-y-4 text-sm text-slate-200">
          <p>Login routing is active.</p>
          <p>Root route redirects to this home route.</p>
          <p>Backend approval and STS issuance are planned next.</p>
        </div>
      </div>
    </section>

    <section class="mx-auto grid max-w-6xl gap-4 px-6 pb-10 md:grid-cols-3">
      <article
        v-for="area in demoAreas"
        :key="area.title"
        class="rounded-lg border border-white/10 bg-white/[0.055] p-5"
      >
        <component
          :is="area.icon"
          class="size-5 text-sky-200"
        />
        <h3 class="mt-4 text-base font-semibold">
          {{ area.title }}
        </h3>
        <p class="mt-2 text-sm leading-6 text-slate-300">
          {{ area.description }}
        </p>
      </article>
    </section>
  </main>
</template>
