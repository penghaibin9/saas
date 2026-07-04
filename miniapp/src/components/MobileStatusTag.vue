<template>
  <text class="mobile-status-tag" :class="`is-${semantic}`">{{ displayLabel }}</text>
</template>

<script>
/**
 * MobileStatusTag 移动端统一状态标签
 * Props 与 PC 端 AppStatusTag 一致：status（状态码）/ type（语义色）/ label（自定义文案）
 */
const STATUS_MAP = {
  DRAFT: { label: '草稿', type: 'default' },
  PENDING_SUBMIT: { label: '待提交', type: 'default' },
  PENDING_REVIEW: { label: '待审核', type: 'warning' },
  PENDING_HANDLE: { label: '待处理', type: 'warning' },
  REVIEWING: { label: '审核中', type: 'processing' },
  PROCESSING: { label: '处理中', type: 'processing' },
  APPROVED: { label: '已通过', type: 'success' },
  COMPLETED: { label: '已完成', type: 'success' },
  RETURNED: { label: '已退回', type: 'warning' },
  REJECTED: { label: '已驳回', type: 'danger' },
  OVERDUE: { label: '已逾期', type: 'danger' },
  ABNORMAL: { label: '异常', type: 'danger' },
  PUBLISHED: { label: '已发布', type: 'success' },
  ARCHIVED: { label: '已归档', type: 'info' },
  READONLY: { label: '只读', type: 'info' },
  NOT_STARTED: { label: '未开始', type: 'default' }
}

export default {
  name: 'MobileStatusTag',
  props: {
    status: { type: String, default: '' },
    type: { type: String, default: '' },
    label: { type: String, default: '' }
  },
  computed: {
    mapped() {
      return STATUS_MAP[this.status] || null
    },
    semantic() {
      return this.type || (this.mapped ? this.mapped.type : 'default')
    },
    displayLabel() {
      return this.label || (this.mapped ? this.mapped.label : this.status) || '—'
    }
  }
}
</script>

<style scoped>
.mobile-status-tag {
  display: inline-flex;
  align-items: center;
  padding: 2px var(--space-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
  line-height: 1.4;
  white-space: nowrap;
}
.is-success { color: var(--success-700); background: var(--success-50); }
.is-processing { color: var(--primary-700); background: var(--primary-50); }
.is-warning { color: var(--warning-700); background: var(--warning-50); }
.is-danger { color: var(--danger-700); background: var(--danger-50); }
.is-info { color: var(--info-700); background: var(--info-50); }
.is-default { color: var(--gray-600); background: var(--gray-100); }
</style>
