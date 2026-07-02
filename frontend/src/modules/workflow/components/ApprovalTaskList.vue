<template>
  <div class="wf-task-list">
    <button
      v-for="t in tasks"
      :key="t.taskId"
      type="button"
      class="wf-task-list__item"
      :class="{ 'is-active': t.taskId === activeId }"
      @click="$emit('select', t)"
    >
      <div class="wf-task-list__head">
        <span class="wf-task-list__title">{{ t.title }}</span>
        <AppBadge :type="statusType(t.status)">{{ statusText(t.status) }}</AppBadge>
      </div>
      <div class="wf-task-list__meta">
        <AppBadge type="info">{{ moduleLabel(t.businessModule) }}</AppBadge>
        <span>{{ t.initiator }}</span>
        <span>{{ t.businessId }}</span>
        <span class="wf-task-list__node">当前：{{ t.currentNode || '—' }}</span>
        <span class="wf-task-list__time">{{ t.submittedAt }}</span>
      </div>
    </button>
  </div>
</template>

<script>
/** ApprovalTaskList —— 审批任务列表（左栏，点击选中） */
import { AppBadge } from '@/components/ui'
import { getTaskStatusText, getTaskStatusType } from '../helpers/approval.helpers'
import { getModuleLabel } from '../helpers/workflow.helpers'

export default {
  name: 'ApprovalTaskList',
  components: { AppBadge },
  props: {
    tasks: { type: Array, default: () => [] },
    activeId: { type: String, default: '' }
  },
  emits: ['select'],
  methods: {
    statusText: getTaskStatusText,
    statusType: getTaskStatusType,
    moduleLabel: getModuleLabel
  }
}
</script>

<style scoped>
.wf-task-list { display: flex; flex-direction: column; gap: var(--space-2); }
.wf-task-list__item {
  text-align: left;
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
  font: inherit;
}
.wf-task-list__item:hover { border-color: var(--primary-100); background: var(--primary-50); }
.wf-task-list__item.is-active { border-color: var(--primary-600); box-shadow: inset 3px 0 0 var(--primary-600); }
.wf-task-list__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.wf-task-list__title {
  font-size: var(--font-size-base);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.wf-task-list__meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.wf-task-list__node { color: var(--primary-600); }
.wf-task-list__time { color: var(--text-tertiary); font-size: var(--font-size-xs); }
</style>
