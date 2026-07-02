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
  height: 36px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
  cursor: pointer;
  border: 1px solid transparent;
  transition:
    background var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    color var(--motion-fast) var(--ease-standard);
}
.app-button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.app-button--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: var(--text-inverse);
}
.app-button--primary:hover:not(:disabled) {
  background: var(--primary-700);
}
.app-button--secondary {
  background: var(--bg-card);
  border-color: var(--border-base);
  color: var(--text-secondary);
}
.app-button--secondary:hover:not(:disabled) {
  border-color: var(--primary-100);
  color: var(--primary-600);
  background: var(--primary-50);
}
.app-button--ghost {
  background: transparent;
  color: var(--text-secondary);
}
.app-button--ghost:hover:not(:disabled) {
  background: var(--gray-100);
}
.app-button--danger {
  background: var(--danger-50);
  border-color: var(--danger-100);
  color: var(--danger-600);
}
.app-button--warning {
  background: var(--warning-50);
  border-color: var(--warning-100);
  color: var(--warning-700);
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
