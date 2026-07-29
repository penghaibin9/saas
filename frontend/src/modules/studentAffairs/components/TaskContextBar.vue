<template>
  <section class="task-context-bar" :class="{ 'is-degraded': degraded }" aria-label="当前任务上下文">
    <div class="task-context-bar__items">
      <span v-if="roleName" class="task-context-bar__item"><b>当前角色</b>{{ roleName }}</span>
      <span v-if="scopeName" class="task-context-bar__item"><b>数据范围</b>{{ scopeName }}</span>
      <span v-if="pending !== null && pending !== undefined" class="task-context-bar__item is-number"><b>待处理</b>{{ pending }}</span>
      <span class="task-context-bar__item is-number"><b>超时</b>{{ overdue === null || overdue === undefined ? '—' : overdue }}</span>
      <span v-if="filterSummary" class="task-context-bar__filter">
        <b>当前筛选</b>{{ filterSummary }}
        <button type="button" @click="$emit('clear-filter')">清除</button>
      </span>
    </div>
    <p v-if="nextHint" class="task-context-bar__hint"><b>下一步</b>{{ nextHint }}</p>
  </section>
</template>

<script>
export default {
  name: 'TaskContextBar',
  props: {
    roleName: { type: String, default: '' },
    scopeName: { type: String, default: '' },
    pending: { type: [Number, String], default: null },
    overdue: { type: [Number, String], default: null },
    filterSummary: { type: String, default: '' },
    nextHint: { type: String, default: '' },
    degraded: { type: Boolean, default: false }
  },
  emits: ['clear-filter']
}
</script>

<style scoped>
.task-context-bar {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(220px, 0.75fr);
  align-items: center;
  gap: var(--space-3, 12px);
  margin-bottom: var(--space-4, 16px);
  padding: 12px 14px;
  border: 1px solid var(--primary-100, #dbeafe);
  border-radius: var(--radius-lg, 12px);
  background: var(--primary-50, #eff6ff);
  color: var(--text-secondary, #475569);
  font-size: var(--font-size-xs, 12px);
}
.task-context-bar.is-degraded {
  border-color: var(--warning-300, #fcd34d);
  background: var(--warning-50, #fffbeb);
}
.task-context-bar__items {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  min-width: 0;
}
.task-context-bar__item,
.task-context-bar__filter {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 30px;
  padding: 5px 9px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: var(--radius-md, 8px);
  background: rgba(255, 255, 255, 0.72);
  white-space: normal;
  line-height: 1.45;
}
.task-context-bar__item.is-number {
  font-variant-numeric: tabular-nums;
  font-weight: var(--font-weight-semibold, 600);
}
.task-context-bar b {
  color: var(--text-tertiary, #64748b);
  font-weight: var(--font-weight-medium, 500);
  white-space: nowrap;
}
.task-context-bar__filter button {
  border: 0;
  padding: 0;
  color: var(--primary-700, #1d4ed8);
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-weight: var(--font-weight-semibold, 600);
}
.task-context-bar__hint {
  margin: 0;
  padding-left: var(--space-3, 12px);
  border-left: 1px solid var(--primary-100, #dbeafe);
  color: var(--text-primary, #0f172a);
  font-size: var(--font-size-sm, 13px);
  line-height: 1.65;
}
.task-context-bar__hint b {
  display: block;
  margin-bottom: 2px;
  color: var(--primary-700, #1d4ed8);
  font-weight: var(--font-weight-semibold, 600);
}
@media (max-width: 900px) {
  .task-context-bar {
    grid-template-columns: 1fr;
    align-items: flex-start;
  }
  .task-context-bar__hint {
    padding-left: 0;
    padding-top: var(--space-2, 8px);
    border-left: 0;
    border-top: 1px solid var(--primary-100, #dbeafe);
  }
}
@media (max-width: 640px) {
  .task-context-bar__items {
    align-items: stretch;
  }
  .task-context-bar__item,
  .task-context-bar__filter {
    width: 100%;
  }
}
</style>
