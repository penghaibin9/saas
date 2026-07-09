<template>
  <div class="app-op-result" :class="`is-${status}`">
    <div class="app-op-result__icon">{{ iconChar }}</div>
    <h3 class="app-op-result__title">{{ title }}</h3>
    <p v-if="description" class="app-op-result__desc">{{ description }}</p>

    <div v-if="stats.length" class="app-op-result__stats">
      <div v-for="(s, i) in stats" :key="i" class="app-op-result__stat" :class="`is-${s.type || 'default'}`">
        <span class="app-op-result__stat-value">{{ s.value }}</span>
        <span class="app-op-result__stat-label">{{ s.label }}</span>
      </div>
    </div>

    <div v-if="$slots.default" class="app-op-result__body"><slot /></div>
    <div v-if="$slots.actions" class="app-op-result__actions"><slot name="actions" /></div>
  </div>
</template>

<script>
/**
 * AppOperationResult — 操作结果页（Excel 导入完成、批量提交完成、审核完成、导出完成）。
 * Props:
 *  - status: success | error | warning | info
 *  - title / description
 *  - stats: [{ label, value, type?(success|danger|warning|default) }]（如 成功 120 / 失败 3）
 * Slots: default（明细，如错误行下载入口）/ actions（底部按钮）
 */
const ICONS = { success: '✓', error: '✕', warning: '!', info: 'ℹ' }
export default {
  name: 'AppOperationResult',
  props: {
    status: { type: String, default: 'success', validator: (v) => ['success', 'error', 'warning', 'info'].includes(v) },
    title: { type: String, required: true },
    description: { type: String, default: '' },
    stats: { type: Array, default: () => [] }
  },
  computed: {
    iconChar() { return ICONS[this.status] || ICONS.info }
  }
}
</script>

<style scoped>
.app-op-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--space-8, 40px) var(--space-5);
  gap: var(--space-2);
}
.app-op-result__icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #fff;
  margin-bottom: var(--space-2);
}
.is-success .app-op-result__icon { background: var(--success-500); }
.is-error .app-op-result__icon { background: var(--danger-500); }
.is-warning .app-op-result__icon { background: var(--warning-500); }
.is-info .app-op-result__icon { background: var(--primary-500); }
.app-op-result__title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.app-op-result__desc {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  max-width: 480px;
}
.app-op-result__stats {
  display: flex;
  gap: var(--space-4);
  margin: var(--space-3) 0;
  flex-wrap: wrap;
  justify-content: center;
}
.app-op-result__stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 72px;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  background: var(--bg-subtle);
}
.app-op-result__stat-value { font-size: var(--font-size-xl); font-weight: var(--font-weight-bold); color: var(--text-primary); font-variant-numeric: tabular-nums; }
.app-op-result__stat.is-success .app-op-result__stat-value { color: var(--success-600); }
.app-op-result__stat.is-danger .app-op-result__stat-value { color: var(--danger-600); }
.app-op-result__stat.is-warning .app-op-result__stat-value { color: var(--warning-700); }
.app-op-result__stat-label { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.app-op-result__body { margin-top: var(--space-2); }
.app-op-result__actions { display: flex; gap: var(--space-2); margin-top: var(--space-4); flex-wrap: wrap; justify-content: center; }
</style>
