<template>
  <p v-if="hasContent" class="app-field-hint" :class="`is-${type}`">
    <span v-if="showIcon" class="app-field-hint__ico">{{ iconChar }}</span>
    <span class="app-field-hint__text"><slot>{{ text }}</slot></span>
  </p>
</template>

<script>
/**
 * AppFieldHint — 表单字段辅助/校验提示（输入框下方）。
 * Props: text、type: hint|error|success|warning、showIcon
 * 统一表单提示口径：默认灰色提示，error 红、success 绿、warning 橙。
 */
const ICONS = { hint: 'ℹ', error: '⚠', success: '✓', warning: '⚠' }
export default {
  name: 'AppFieldHint',
  props: {
    text: { type: String, default: '' },
    type: {
      type: String,
      default: 'hint',
      validator: (v) => ['hint', 'error', 'success', 'warning'].includes(v)
    },
    showIcon: { type: Boolean, default: true }
  },
  computed: {
    iconChar() {
      return ICONS[this.type] || ICONS.hint
    },
    hasContent() {
      return !!this.text || !!this.$slots.default
    }
  }
}
</script>

<style scoped>
.app-field-hint {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1);
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-xs);
  line-height: 1.5;
}
.app-field-hint__ico { flex-shrink: 0; }
.app-field-hint.is-hint { color: var(--text-tertiary); }
.app-field-hint.is-error { color: var(--danger-600); }
.app-field-hint.is-success { color: var(--success-600); }
.app-field-hint.is-warning { color: var(--warning-700); }
</style>
