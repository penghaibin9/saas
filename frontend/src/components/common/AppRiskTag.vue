<template>
  <span class="app-risk-tag" :class="`is-${normalized}`">
    <span class="app-risk-tag__dot" />
    {{ displayLabel }}
  </span>
</template>

<script>
/**
 * AppRiskTag 统一风险标签
 * Props:
 *  - level: LOW | MEDIUM | HIGH | CRITICAL（大小写不敏感）
 *  - label: 自定义文案，默认按等级显示 低风险/中风险/高风险/严重风险
 */
const LEVEL_MAP = {
  LOW: '低风险',
  MEDIUM: '中风险',
  HIGH: '高风险',
  CRITICAL: '严重风险'
}

export default {
  name: 'AppRiskTag',
  props: {
    level: {
      type: String,
      required: true,
      validator: (v) => ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].includes(String(v).toUpperCase())
    },
    label: { type: String, default: '' }
  },
  computed: {
    normalized() {
      return String(this.level).toUpperCase()
    },
    displayLabel() {
      return this.label || LEVEL_MAP[this.normalized] || this.level
    }
  }
}
</script>

<style scoped>
.app-risk-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0 var(--space-2);
  height: 22px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  line-height: 22px;
  white-space: nowrap;
  border: 1px solid transparent;
}
.app-risk-tag__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: currentColor;
}
.is-LOW {
  color: var(--success-700);
  background: var(--success-50);
  border-color: var(--success-100);
}
.is-MEDIUM {
  color: var(--warning-700);
  background: var(--warning-50);
  border-color: var(--warning-100);
}
.is-HIGH {
  color: var(--danger-600);
  background: var(--danger-50);
  border-color: var(--danger-100);
  font-weight: var(--font-weight-semibold);
  padding: 0 var(--space-3);
  height: 24px;
  line-height: 24px;
}
.is-CRITICAL {
  color: var(--danger-700);
  background: var(--danger-100);
  border-color: var(--danger-500);
  font-weight: var(--font-weight-bold);
  padding: 0 var(--space-3);
  height: 24px;
  line-height: 24px;
}
</style>
