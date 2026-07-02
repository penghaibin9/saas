<template>
  <text class="mobile-risk-tag" :class="`is-${normalized}`">{{ displayLabel }}</text>
</template>

<script>
/**
 * MobileRiskTag 移动端风险标签
 * Props: level: LOW | MEDIUM | HIGH | CRITICAL、label（自定义文案）
 */
const LEVEL_MAP = { LOW: '低风险', MEDIUM: '中风险', HIGH: '高风险', CRITICAL: '严重风险' }

export default {
  name: 'MobileRiskTag',
  props: {
    level: { type: String, required: true },
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
.mobile-risk-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  line-height: 1.4;
  white-space: nowrap;
}
.is-LOW { color: var(--success-700); background: var(--success-50); }
.is-MEDIUM { color: var(--warning-700); background: var(--warning-50); }
.is-HIGH { color: var(--danger-600); background: var(--danger-50); }
.is-CRITICAL { color: var(--text-inverse); background: var(--danger-600); }
</style>
