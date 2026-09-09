<template>
  <div class="atp">
    <div v-if="!logs.length" class="atp__empty">暂无操作留痕</div>
    <ol v-else class="atp__list">
      <li v-for="log in logs" :key="log.id" class="atp__item">
        <span class="atp__dot" />
        <div class="atp__main">
          <div class="atp__head">
            <span class="atp__action">{{ actionLabel(log) }}</span>
            <span class="atp__time">{{ log.time }}</span>
          </div>
          <div class="atp__detail">{{ log.detail }}</div>
          <div class="atp__meta">
            {{ log.operator }}<template v-if="log.roleName">（{{ log.roleName }}）</template>
            <template v-if="log.before || log.after"> · {{ log.before || '—' }} → {{ log.after || '—' }}</template>
          </div>
        </div>
      </li>
    </ol>
  </div>
</template>

<script>
import { safeLocalizedText } from '@/utils/presentationSafety'

const ACTION_LABELS = { CREATE: '创建', UPDATE: '修改', DELETE: '删除', SUBMIT: '提交', APPROVE: '审核通过', REJECT: '审核驳回', RETURN: '退回修改', PUBLISH: '发布', ARCHIVE: '归档', CANCEL: '取消', CLOSE: '关闭' }

/**
 * AuditTrailPanel — 操作留痕时间线（模块局部组件）。
 * Props: logs [{ id, time, operator, roleName?, action, detail, before?, after? }]（来自迎新审计 API）
 */
export default {
  name: 'AuditTrailPanel',
  props: {
    logs: { type: Array, default: () => [] }
  },
  methods: {
    actionLabel(log) {
      return log?.actionLabel || safeLocalizedText({ value: log?.action, dictionary: ACTION_LABELS, unknownLabel: '业务操作' })
    }
  }
}
</script>

<style scoped>
.atp__empty {
  padding: var(--space-6);
  text-align: center;
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.atp__list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.atp__item {
  position: relative;
  display: flex;
  gap: var(--space-3);
  padding: var(--space-3) 0;
}
.atp__item + .atp__item {
  border-top: 1px dashed var(--border-light);
}
.atp__dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: var(--radius-full);
  background: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.atp__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--space-3);
}
.atp__action {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.atp__time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.atp__detail {
  margin-top: 2px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.atp__meta {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
</style>
