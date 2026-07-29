<template>
  <span class="app-status-tag" :class="[`is-${semantic}`, { 'is-sm': size === 'sm' }]">
    <span v-if="dot" class="app-status-tag__dot" />
    <slot>{{ displayLabel }}</slot>
  </span>
</template>

<script>
/**
 * AppStatusTag 统一状态标签。
 * ARCHIVED 永远表示“已归档”；业务作废必须使用 VOIDED，禁止再按页面自行改义。
 */
const STATUS_MAP = {
  // 通用审批/流转
  DRAFT: { label: '草稿', type: 'default' },
  PENDING_SUBMIT: { label: '待提交', type: 'default' },
  PENDING: { label: '待处理', type: 'warning' },
  PENDING_REVIEW: { label: '待审核', type: 'warning' },
  PENDING_AUDIT: { label: '待审核', type: 'warning' },
  PENDING_HANDLE: { label: '待处理', type: 'warning' },
  PENDING_APPROVE: { label: '待审批', type: 'warning' },
  SUBMITTED: { label: '已提交', type: 'processing' },
  REVIEWING: { label: '审核中', type: 'processing' },
  PROCESSING: { label: '处理中', type: 'processing' },
  IN_PROGRESS: { label: '进行中', type: 'processing' },
  APPROVED: { label: '已通过', type: 'success' },
  CONFIRMED: { label: '已确认', type: 'success' },
  PASSED: { label: '已通过', type: 'success' },
  COMPLETED: { label: '已完成', type: 'success' },
  FINISHED: { label: '已结束', type: 'success' },
  RETURNED: { label: '已退回', type: 'warning' },
  REJECTED: { label: '已驳回', type: 'danger' },
  FAILED: { label: '未通过', type: 'danger' },
  OVERDUE: { label: '已逾期', type: 'danger' },
  EXPIRED: { label: '已过期', type: 'danger' },
  ABNORMAL: { label: '异常', type: 'danger' },
  CANCELLED: { label: '已取消', type: 'default' },
  PUBLISHED: { label: '已发布', type: 'success' },
  ARCHIVED: { label: '已归档', type: 'info' },
  VOIDED: { label: '已作废', type: 'danger' },
  READONLY: { label: '只读', type: 'info' },
  ENABLED: { label: '启用中', type: 'success' },
  DISABLED: { label: '已停用', type: 'default' },
  NOT_STARTED: { label: '未开始', type: 'default' },

  // 教务·教学任务/课表
  PENDING_ASSIGN: { label: '待分配教师', type: 'warning' },
  ASSIGNED: { label: '待教师确认', type: 'processing' },
  TEACHER_CONFIRMED: { label: '教师已确认', type: 'success' },
  REJECTED_BY_TEACHER: { label: '教师已退回', type: 'danger' },
  COLLEGE_CONFIRMED: { label: '学院已确认', type: 'processing' },
  READY: { label: '已就绪', type: 'success' },
  MERGED: { label: '已并入合班', type: 'info' },
  PRE_PUBLISHED: { label: '预发布', type: 'processing' },

  // 教务·选课
  OPEN: { label: '开放中', type: 'processing' },
  CLOSED: { label: '已截止', type: 'warning' },
  LOCKED: { label: '名单已锁定', type: 'success' },
  SELECTED: { label: '已选中', type: 'success' },
  DROPPED: { label: '已退选', type: 'default' },
  PENDING_LOTTERY: { label: '待摇号', type: 'warning' },
  LOTTERY_LOST: { label: '未中签', type: 'danger' },
  COURSE_CANCELLED: { label: '课程已取消', type: 'danger' },

  // 教务·考务
  COURSE_CONFIRMED: { label: '课程已确认', type: 'processing' },
  ARRANGED: { label: '已编排', type: 'processing' },
  PENDING_CONFIRM: { label: '待确认', type: 'warning' },
  REMOVED: { label: '已移除', type: 'default' },
  ACTIVE: { label: '有效', type: 'success' },
  PRESENT: { label: '到考', type: 'success' },
  ABSENT: { label: '缺考', type: 'danger' },
  LATE: { label: '迟到', type: 'warning' },
  CHEAT: { label: '作弊', type: 'danger' },
  DEFERRED: { label: '缓考', type: 'warning' },
  EXEMPT: { label: '免修', type: 'info' },

  // 教务·成绩审核
  INPUTTING: { label: '录入中', type: 'processing' },
  COLLEGE_REVIEW: { label: '学院审核中', type: 'warning' },
  ACADEMIC_REVIEW: { label: '教务终审中', type: 'processing' },
  CHANGE_REVIEW: { label: '更正审核中', type: 'warning' },

  // 教务·教材征订/发放/费用
  ORDERED: { label: '已征订', type: 'processing' },
  PARTIALLY_ARRIVED: { label: '部分到货', type: 'warning' },
  ARRIVED: { label: '已到货', type: 'success' },
  DISTRIBUTING: { label: '发放中', type: 'processing' },
  RECEIVED: { label: '已签收', type: 'success' },
  EXCLUDED: { label: '不发放', type: 'info' },
  EXCHANGED: { label: '已换领', type: 'info' },
  UNPAID: { label: '未收款', type: 'warning' },
  PARTIAL: { label: '部分收款', type: 'warning' },
  PAID: { label: '已结清', type: 'success' },
  WAIVED: { label: '已减免', type: 'info' },

  // 学工/迎新/毕设/实习
  REPORTED: { label: '已报到', type: 'success' },
  NOT_REPORTED: { label: '未报到', type: 'warning' },
  CHECKED_IN: { label: '已入住', type: 'success' },
  ON_LEAVE: { label: '请假中', type: 'processing' },
  ENROLLED: { label: '在读', type: 'success' },
  GRADED: { label: '已评定', type: 'success' },
  DEFENDING: { label: '答辩中', type: 'processing' },
  SIGNED: { label: '已签订', type: 'success' },
  TERMINATED: { label: '已终止', type: 'danger' }
}

export default {
  name: 'AppStatusTag',
  props: {
    status: { type: String, default: '' },
    type: {
      type: String,
      default: '',
      validator: (v) =>
        !v || ['success', 'processing', 'primary', 'warning', 'danger', 'info', 'default'].includes(v)
    },
    label: { type: String, default: '' },
    dot: { type: Boolean, default: false },
    size: {
      type: String,
      default: 'md',
      validator: (v) => ['sm', 'md'].includes(v)
    }
  },
  computed: {
    mapped() {
      return STATUS_MAP[String(this.status || '').toUpperCase()] || null
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
.app-status-tag.is-sm {
  height: 18px;
  line-height: 18px;
  padding: 0 var(--space-1);
  font-size: 11px;
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
.is-processing,
.is-primary {
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
