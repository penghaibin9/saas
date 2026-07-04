<template>
  <button
    type="button"
    class="app-button"
    :class="[`app-button--${variant}`, { 'is-loading': loading }]"
    :disabled="disabled || loading"
    @click="$emit('click', $event)"
  >
    <span v-if="loading" class="app-button__spinner" aria-hidden="true" />
    <slot />
  </button>
</template>

<script>
export default {
  name: 'AppButton',
  props: {
    variant: {
      type: String,
      default: 'secondary',
      validator: (v) => ['primary', 'secondary', 'ghost', 'danger', 'warning'].includes(v)
    },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false }
  },
  emits: ['click']
}
</script>

<style scoped>
.app-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  height: 34px;
  padding: 0 14px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  border: 1px solid transparent;
  font-family: inherit;
  white-space: nowrap;
  transition: all 0.12s;
}
.app-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.app-button--primary {
  background: var(--btn-p-bg);
  border-color: transparent;
  color: #fff;
  font-weight: var(--font-weight-semibold);
  box-shadow: var(--btn-p-shadow);
}
.app-button--primary:hover:not(:disabled) {
  background: var(--btn-p-bg-h);
  box-shadow: 0 4px 14px -2px var(--glow);
}
.app-button--secondary {
  background: rgba(255, 255, 255, 0.85);
  border-color: var(--card-b);
  color: var(--t2);
}
.app-button--secondary:hover:not(:disabled) {
  background: var(--bg-card);
  color: var(--t1);
  border-color: var(--glow);
}
.app-button--ghost {
  background: transparent;
  color: var(--t2);
}
.app-button--ghost:hover:not(:disabled) {
  background: var(--pri-bg);
  color: var(--pri);
}
.app-button--danger {
  background: rgba(255, 255, 255, 0.85);
  border-color: rgba(220, 38, 38, 0.3);
  color: var(--err);
}
.app-button--danger:hover:not(:disabled) {
  background: var(--err-l);
}
.app-button--warning {
  background: rgba(255, 255, 255, 0.85);
  border-color: rgba(217, 119, 6, 0.32);
  color: var(--warning-700);
}
.app-button--warning:hover:not(:disabled) {
  background: var(--warn-l);
}
.app-button__spinner {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: var(--radius-full);
  animation: app-btn-spin var(--motion-slow) linear infinite;
}
@keyframes app-btn-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
