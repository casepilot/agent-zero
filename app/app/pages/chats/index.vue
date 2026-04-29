<script setup lang="ts">
useHead({
  title: 'Chats | IAM Agent',
})
</script>

<template>
  <main class="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#070b12] px-8 py-10 text-white">
    <div class="absolute inset-0 opacity-85">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_50%_18%,rgba(56,189,248,0.22),transparent_34%),radial-gradient(circle_at_50%_88%,rgba(59,130,246,0.14),transparent_30%),linear-gradient(135deg,#070b12_0%,#0d1320_48%,#05070b_100%)]" />
      <div class="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.045)_1px,transparent_1px)] bg-[size:48px_48px] [mask-image:radial-gradient(circle_at_50%_44%,black,transparent_72%)]" />
    </div>

    <section class="login-rise relative flex w-full max-w-3xl flex-col items-center text-center">
      <div class="relative mb-10 flex size-56 items-center justify-center">
        <div class="absolute inset-10 rounded-full border border-sky-200/15" />
        <div class="absolute inset-0 rounded-full bg-sky-300/10 blur-3xl" />
        <div class="absolute left-1/2 top-2 size-3 -translate-x-1/2 rounded-full bg-sky-200 shadow-[0_0_22px_rgba(125,211,252,0.78)]" />
        <div class="absolute bottom-8 left-8 size-2 rounded-full bg-sky-300/80 shadow-[0_0_18px_rgba(125,211,252,0.68)]" />
        <div class="absolute bottom-8 right-8 size-2 rounded-full bg-sky-300/80 shadow-[0_0_18px_rgba(125,211,252,0.68)]" />
        <div class="absolute left-[4.6rem] top-[4.6rem] h-px w-24 rotate-45 bg-sky-200/20" />
        <div class="absolute right-[4.6rem] top-[4.6rem] h-px w-24 -rotate-45 bg-sky-200/20" />
        <div class="relative flex size-24 items-center justify-center rounded-lg border border-white/12 bg-white/[0.075] text-sky-200 shadow-[0_0_44px_rgba(125,211,252,0.28)] backdrop-blur-2xl">
          <svg
            class="size-11"
            viewBox="0 0 48 48"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M24 5L39 11V22C39 31.5 32.6 39.8 24 43C15.4 39.8 9 31.5 9 22V11L24 5Z"
              stroke="currentColor"
              stroke-width="3"
              stroke-linejoin="round"
            />
            <path
              d="M18 24L22.2 28L31 18"
              stroke="currentColor"
              stroke-width="3"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </div>
      </div>

      <p class="text-base font-medium text-sky-100/80">
        IAM Agent
      </p>
      <h1 class="mt-3 text-5xl font-semibold leading-tight tracking-normal text-white">
        Select a chat to begin.
      </h1>
      <p class="mt-5 max-w-xl text-base leading-7 text-slate-400">
        This is the empty chat state. Each conversation has its own route, so the active chat is reflected directly in the URL.
      </p>

      <NuxtLink
        to="/chats/flight-change"
        class="mt-9 inline-flex h-12 items-center justify-center rounded-lg bg-sky-300 px-5 text-base font-medium text-slate-950 shadow-[0_16px_42px_rgba(56,189,248,0.22)] transition-colors hover:bg-sky-200"
      >
        Open default chat
      </NuxtLink>
    </section>
  </main>
</template>
