<template>
  <span class="app-badge" :class="`app-badge--${type}`">
    <slot />
  </span>
</template>

<script>
export default {
  name: 'AppBadge',
  props: {
    type: {
      type: String,
      default: 'neutral',
      validator: (v) => ['success', 'warning', 'danger', 'info', 'neutral'].includes(v)
    }
  }
}
</script>

<style scoped>
.app-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 20px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}
.app-badge--success {
  background: var(--success-50);
  color: var(--success-700);
}
.app-badge--warning {
  background: var(--warning-50);
  color: var(--warning-700);
}
.app-badge--danger {
  background: var(--danger-50);
  color: var(--danger-700);
}
.app-badge--info {
  background: var(--info-50);
  color: var(--info-700);
}
.app-badge--neutral {
  background: var(--gray-100);
  color: var(--text-secondary);
}
</style>
