<template>
  <section class="task-context-bar" :class="{ 'is-degraded': degraded }" aria-label="当前任务上下文">
    <div class="task-context-bar__items">
      <span v-if="roleName" class="task-context-bar__item"><b>当前角色</b>{{ roleName }}</span>
      <span v-if="scopeName" class="task-context-bar__item"><b>数据范围</b>{{ scopeName }}</span>
      <span v-if="pending !== null && pending !== undefined" class="task-context-bar__item"><b>待处理</b>{{ pending }}</span>
      <span class="task-context-bar__item"><b>超时</b>{{ overdue === null || overdue === undefined ? '—' : overdue }}</span>
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
.task-context-bar { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3, 12px); margin-bottom: var(--space-3, 12px); padding: var(--space-2, 8px) var(--space-3, 12px); border: 1px solid var(--border-light, #e5e7eb); border-radius: var(--radius-md, 8px); background: var(--bg-secondary, #f8fafc); color: var(--text-secondary, #475569); font-size: var(--font-size-xs, 12px); }
.task-context-bar.is-degraded { border-color: var(--warning-300, #fcd34d); }
.task-context-bar__items { display: flex; flex-wrap: wrap; align-items: center; gap: var(--space-2, 8px) var(--space-4, 16px); min-width: 0; }
.task-context-bar__item, .task-context-bar__filter { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.task-context-bar b { color: var(--text-tertiary, #64748b); font-weight: var(--font-weight-medium, 500); }
.task-context-bar__filter button { border: 0; padding: 0; color: var(--primary-600, #2563eb); background: transparent; cursor: pointer; font: inherit; }
.task-context-bar__hint { margin: 0; flex: 0 1 auto; text-align: right; }
.task-context-bar__hint b { margin-right: 4px; }
@media (max-width: 768px) { .task-context-bar { align-items: flex-start; flex-direction: column; } .task-context-bar__hint { text-align: left; } }
</style>
