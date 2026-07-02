<template>
  <div class="app-inline-alert" :class="`is-${type}`" role="alert">
    <span class="app-inline-alert__icon">{{ icon }}</span>
    <div class="app-inline-alert__content">
      <div v-if="title" class="app-inline-alert__title">{{ title }}</div>
      <div class="app-inline-alert__desc">
        <slot>{{ description }}</slot>
      </div>
      <div v-if="$slots.actions" class="app-inline-alert__actions">
        <slot name="actions" />
      </div>
    </div>
    <button
      v-if="closable"
      type="button"
      class="app-inline-alert__close"
      aria-label="关闭"
      @click="$emit('close')"
    >
      ×
    </button>
  </div>
</template>

<script>
/**
 * AppInlineAlert 行内提示
 * 依据 V2.1 §11.3：材料被退回时页面顶部必须显示不可关闭的 AppInlineAlert，
 * 因此 closable 默认 false，退回场景禁止传 closable=true。
 * Props: type: info|success|warning|danger、title、description、closable
 * Emits: close
 * Slots: default（正文，覆盖 description）、actions（如“重新提交”按钮）
 */
const ICONS = { info: 'ℹ', success: '✓', warning: '!', danger: '!' }

export default {
  name: 'AppInlineAlert',
  props: {
    type: {
      type: String,
      default: 'info',
      validator: (v) => ['info', 'success', 'warning', 'danger'].includes(v)
    },
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    closable: { type: Boolean, default: false }
  },
  emits: ['close'],
  computed: {
    icon() {
      return ICONS[this.type]
    }
  }
}
</script>

<style scoped>
.app-inline-alert {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  font-size: var(--font-size-base);
  line-height: var(--line-height-base);
}
.is-info {
  background: var(--info-50);
  border-color: var(--info-100);
  color: var(--info-700);
}
.is-success {
  background: var(--success-50);
  border-color: var(--success-100);
  color: var(--success-700);
}
.is-warning {
  background: var(--warning-50);
  border-color: var(--warning-100);
  color: var(--warning-700);
}
.is-danger {
  background: var(--danger-50);
  border-color: var(--danger-100);
  color: var(--danger-700);
}
.app-inline-alert__icon {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  background: currentColor;
  color: var(--text-inverse);
  font-size: var(--font-size-xs);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 2px;
}
.is-info .app-inline-alert__icon {
  background: var(--info-500);
}
.is-success .app-inline-alert__icon {
  background: var(--success-500);
}
.is-warning .app-inline-alert__icon {
  background: var(--warning-500);
}
.is-danger .app-inline-alert__icon {
  background: var(--danger-500);
}
.app-inline-alert__content {
  flex: 1;
  min-width: 0;
}
.app-inline-alert__title {
  font-weight: var(--font-weight-medium);
  margin-bottom: var(--space-1);
}
.app-inline-alert__desc {
  color: var(--text-secondary);
}
.app-inline-alert__actions {
  margin-top: var(--space-2);
  display: flex;
  gap: var(--space-2);
}
.app-inline-alert__close {
  border: none;
  background: none;
  font-size: var(--font-size-lg);
  color: var(--text-tertiary);
  cursor: pointer;
  line-height: 1;
  padding: 0;
}
.app-inline-alert__close:hover {
  color: var(--text-secondary);
}
</style>
