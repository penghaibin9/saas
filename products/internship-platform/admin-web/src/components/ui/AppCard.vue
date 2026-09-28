<template>
  <div class="app-card" :class="[`app-card--${variant}`, { 'is-hoverable': hoverable }]">
    <slot />
  </div>
</template>

<script>
export default {
  name: 'AppCard',
  props: {
    variant: {
      type: String,
      default: 'subtle',
      validator: (v) => ['subtle', 'elevated', 'risk'].includes(v)
    },
    hoverable: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
.app-card {
  background: var(--bg-card);
  border: 1px solid var(--card-border);
  border-radius: var(--radius-card-sm);
  box-shadow: var(--shadow-card);
  min-width: 0;
}
.app-card--subtle {
  background: var(--bg-card);
}
.app-card--elevated {
  box-shadow: var(--shadow-card-hover);
}
.app-card--risk {
  background: var(--risk-gradient);
  border-color: var(--danger-100);
}
.app-card.is-hoverable {
  transition:
    transform var(--motion-normal) var(--ease-standard),
    box-shadow var(--motion-normal) var(--ease-standard);
}
.app-card.is-hoverable:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-card-hover);
}
</style>
