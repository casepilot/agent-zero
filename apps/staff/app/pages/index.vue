<script setup lang="ts">
import { KeyRound, ScrollText, ShieldCheck, UserPlus } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

const stats = [
  { label: 'Pending requests', value: '0', tone: 'border-blue-200 bg-blue-50 text-blue-900' },
  { label: 'Active sessions', value: '0', tone: 'border-emerald-200 bg-emerald-50 text-emerald-900' },
  { label: 'Policy records', value: '0', tone: 'border-amber-200 bg-amber-50 text-amber-900' }
]
</script>

<template>
  <main class="min-h-screen bg-background text-foreground">
    <section class="mx-auto flex w-full max-w-6xl flex-col gap-8 px-6 py-8">
      <header class="flex flex-col gap-4 border-b border-border pb-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p class="text-sm font-medium text-muted-foreground">
            IAM Agent
          </p>
          <h1 class="mt-2 text-3xl font-semibold tracking-normal">
            Staff access console
          </h1>
        </div>

        <div class="flex flex-wrap gap-2">
          <Button>
            <UserPlus />
            Add principal
          </Button>
          <Button variant="outline">
            <KeyRound />
            Request access
          </Button>
        </div>
      </header>

      <div class="grid gap-4 md:grid-cols-3">
        <article
          v-for="stat in stats"
          :key="stat.label"
          class="rounded-lg border p-4"
          :class="stat.tone"
        >
          <p class="text-sm font-medium">
            {{ stat.label }}
          </p>
          <p class="mt-3 text-3xl font-semibold">
            {{ stat.value }}
          </p>
        </article>
      </div>

      <section class="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div class="rounded-lg border border-border bg-card p-5 text-card-foreground">
          <div class="flex items-center gap-3">
            <span class="flex size-9 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ShieldCheck class="size-4" />
            </span>
            <div>
              <h2 class="text-lg font-semibold">
                Just-in-time access
              </h2>
              <p class="text-sm text-muted-foreground">
                Human and agent requests will be reviewed before temporary AWS access is issued.
              </p>
            </div>
          </div>
        </div>

        <div class="rounded-lg border border-border bg-card p-5 text-card-foreground">
          <div class="flex items-center gap-3">
            <span class="flex size-9 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
              <ScrollText class="size-4" />
            </span>
            <div>
              <h2 class="text-lg font-semibold">
                Request log
              </h2>
              <p class="text-sm text-muted-foreground">
                Access decisions and session details will appear here as the broker API comes online.
              </p>
            </div>
          </div>
        </div>
      </section>
    </section>
  </main>
</template>
