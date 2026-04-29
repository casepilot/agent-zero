<script setup lang="ts">
import { ArrowRight, Eye, KeyRound, ShieldCheck, UserRound } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

const username = ref('')
const password = ref('')
const showPassword = ref(false)

async function handleContinue() {
  await navigateTo('/flight-change')
}
</script>

<template>
  <main class="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#070b12] px-6 py-10 text-white">
    <div class="absolute inset-0 opacity-85">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_50%_16%,rgba(56,189,248,0.22),transparent_34%),radial-gradient(circle_at_50%_92%,rgba(59,130,246,0.14),transparent_30%),linear-gradient(135deg,#070b12_0%,#0d1320_48%,#05070b_100%)]" />
      <div class="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.045)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(circle_at_50%_44%,black,transparent_72%)]" />
    </div>

    <section class="login-panel login-rise relative w-full max-w-lg rounded-lg border border-white/12 bg-white/[0.075] p-8 shadow-[0_24px_90px_rgba(0,0,0,0.42)] backdrop-blur-2xl sm:p-10">
      <div class="mb-10 flex flex-col items-center text-center">
        <div class="mb-5 flex size-14 items-center justify-center rounded-lg bg-sky-300 text-slate-950 shadow-[0_0_34px_rgba(125,211,252,0.45)]">
          <ShieldCheck class="size-7" />
        </div>
        <p class="text-base font-medium text-sky-100/80">
          IAM Agent
        </p>
        <h1 class="mt-3 text-4xl font-semibold tracking-normal text-white">
          Sign in
        </h1>
      </div>

      <form
        class="space-y-6"
        @submit.prevent="handleContinue"
      >
        <div class="space-y-3">
          <Label
            for="username"
            class="text-base text-white/86"
          >
            Username
          </Label>
          <div class="relative">
            <UserRound class="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-slate-400" />
            <Input
              id="username"
              v-model="username"
              name="username"
              autocomplete="username"
              placeholder="deepak"
              class="h-14 border-white/12 bg-slate-950/52 pl-12 text-base text-white placeholder:text-slate-500 focus-visible:border-sky-300 focus-visible:ring-sky-300/20"
            />
          </div>
        </div>

        <div class="space-y-3">
          <Label
            for="password"
            class="text-base text-white/86"
          >
            Password
          </Label>
          <div class="relative">
            <KeyRound class="pointer-events-none absolute left-4 top-1/2 size-5 -translate-y-1/2 text-slate-400" />
            <Input
              id="password"
              v-model="password"
              name="password"
              :type="showPassword ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="••••••••"
              class="h-14 border-white/12 bg-slate-950/52 pl-12 pr-12 text-base text-white placeholder:text-slate-500 focus-visible:border-sky-300 focus-visible:ring-sky-300/20"
            />
            <button
              type="button"
              class="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-sky-100"
              aria-label="Toggle password visibility"
              @click="showPassword = !showPassword"
            >
              <Eye class="size-5" />
            </button>
          </div>
        </div>

        <div class="flex items-center justify-between gap-4 pt-1 text-base text-slate-300">
          <label class="flex items-center gap-2">
            <input
              type="checkbox"
              class="size-5 rounded border-white/20 bg-slate-950 accent-sky-300"
            >
            Remember me
          </label>
          <button
            type="button"
            class="font-medium text-sky-200/82 transition-colors hover:text-sky-100"
          >
            Reset
          </button>
        </div>

        <Button
          type="submit"
          size="lg"
          class="group h-14 w-full bg-sky-300 text-base text-slate-950 shadow-[0_16px_42px_rgba(56,189,248,0.22)] hover:bg-sky-200"
        >
          Continue
          <ArrowRight class="transition-transform group-hover/button:translate-x-0.5" />
        </Button>
      </form>
    </section>
  </main>
</template>
