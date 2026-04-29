<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { cn } from '@/lib/utils'

const model = defineModel<string>()

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()
</script>

<template>
  <input
    v-model="model"
    data-slot="input"
    :class="cn(
      'selection:bg-primary selection:text-primary-foreground placeholder:text-muted-foreground flex h-11 w-full min-w-0 rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground shadow-xs transition-[border-color,box-shadow,background-color] outline-none disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50',
      'focus-visible:border-ring focus-visible:ring-ring/35 focus-visible:ring-4 aria-invalid:border-destructive aria-invalid:ring-destructive/20',
      props.class,
    )"
  >
</template>
