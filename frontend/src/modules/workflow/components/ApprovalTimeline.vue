<template>
  <ul class="wf-timeline">
    <li v-for="r in records" :key="r.recordId" class="wf-timeline__item">
      <span class="wf-timeline__dot" :class="`is-${dotType(r.action)}`" />
      <div class="wf-timeline__body">
        <div class="wf-timeline__head">
          <span class="wf-timeline__action">{{ actionLabel(r.action) }}</span>
          <span class="wf-timeline__operator">{{ r.operator }}</span>
          <AppBadge v-if="r.nodeName" type="neutral">{{ r.nodeName }}</AppBadge>
        </div>
        <p v-if="r.comment" class="wf-timeline__comment">{{ r.comment }}</p>
        <span class="wf-timeline__time">{{ r.time }}</span>
      </div>
    </li>
    <li v-if="!records.length" class="wf-timeline__empty">暂无审批记录</li>
  </ul>
</template>

<script>
/** ApprovalTimeline —— 审批记录时间线（退回原因在此完整展示） */
import { AppBadge } from '@/components/ui'
import { APPROVAL_ACTION, APPROVAL_ACTION_LABELS } from '../constants/workflow.constants'

export default {
  name: 'ApprovalTimeline',
  components: { AppBadge },
  props: {
    records: { type: Array, default: () => [] }
  },
  methods: {
    actionLabel(action) {
      return APPROVAL_ACTION_LABELS[action] || action
    },
    dotType(action) {
      if (action === APPROVAL_ACTION.APPROVE) return 'success'
      if (action === APPROVAL_ACTION.REJECT) return 'danger'
      if (action === APPROVAL_ACTION.WITHDRAW) return 'neutral'
      return 'primary'
    }
  }
}
</script>

<style scoped>
.wf-timeline { list-style: none; margin: 0; padding: 0; }
.wf-timeline__item { position: relative; padding: 0 0 var(--space-4) var(--space-6); }
.wf-timeline__item::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 14px;
  bottom: 0;
  width: 1px;
  background: var(--border-base);
}
.wf-timeline__item:last-child::before { display: none; }
.wf-timeline__dot {
  position: absolute;
  left: 0;
  top: 5px;
  width: 11px;
  height: 11px;
  border-radius: var(--radius-full);
  background: var(--gray-300);
  box-shadow: 0 0 0 2px var(--bg-card);
}
.wf-timeline__dot.is-success { background: var(--success-500); }
.wf-timeline__dot.is-danger { background: var(--danger-500); }
.wf-timeline__dot.is-primary { background: var(--primary-600); }
.wf-timeline__head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.wf-timeline__action { font-weight: var(--font-weight-medium); color: var(--text-primary); font-size: var(--font-size-base); }
.wf-timeline__operator { color: var(--text-secondary); font-size: var(--font-size-sm); }
.wf-timeline__comment {
  margin: var(--space-1) 0 0;
  padding: var(--space-2) var(--space-3);
  background: var(--gray-50);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  line-height: var(--line-height-base);
}
.wf-timeline__time { display: block; margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wf-timeline__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); padding: var(--space-3) 0; list-style: none; }
</style>
