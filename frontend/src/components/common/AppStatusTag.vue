<template>
  <span class="app-status-tag" :class="`is-${semantic}`">
    <span v-if="dot" class="app-status-tag__dot" />
    <slot>{{ displayLabel }}</slot>
  </span>
</template>

<script>
/**
 * AppStatusTag 统一状态标签
 * Props:
 *  - status: 业务状态码（见 STATUS_MAP），传入后自动匹配语义色与中文文案
 *  - type:   直接指定语义色 success | processing | warning | danger | info | default
 *  - label:  自定义文案（优先于 status 映射）
 *  - dot:    是否显示状态圆点
 * 依据 V2.1 §3.2：状态语义色只表达业务状态。
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
  DISABLED: { label: '已停用', type: 'default' },
  NOT_STARTED: { label: '未开始', type: 'default' }
}

export default {
  name: 'AppStatusTag',
  props: {
    status: { type: String, default: '' },
    type: {
      type: String,
      default: '',
      validator: (v) =>
        !v || ['success', 'processing', 'warning', 'danger', 'info', 'default'].includes(v)
    },
    label: { type: String, default: '' },
    dot: { type: Boolean, default: false }
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
.app-status-tag {
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
.app-status-tag__dot {
  width: 6px;
  height: 6px;
  border-radius: var(--radius-full);
  background: currentColor;
}
.is-success {
  color: var(--success-700);
  background: var(--success-50);
  border-color: var(--success-100);
}
.is-processing {
  color: var(--primary-700);
  background: var(--primary-50);
  border-color: var(--primary-100);
}
.is-warning {
  color: var(--warning-700);
  background: var(--warning-50);
  border-color: var(--warning-100);
}
.is-danger {
  color: var(--danger-600);
  background: var(--danger-50);
  border-color: var(--danger-100);
}
.is-info {
  color: var(--info-700);
  background: var(--info-50);
  border-color: var(--info-100);
}
.is-default {
  color: var(--gray-600);
  background: var(--gray-100);
  border-color: var(--gray-200);
}
</style>
