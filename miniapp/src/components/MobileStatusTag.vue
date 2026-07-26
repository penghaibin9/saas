<template>
  <text class="mobile-status-tag" :class="`is-${semantic}`">{{ displayLabel }}</text>
</template>

<script>
/**
 * 学生/教师微信端共用状态词表。
 * ARCHIVED=已归档；VOIDED=已作废。未知状态原样显示，禁止静默翻译成“已完成”。
 */
const STATUS_MAP = {
  DRAFT: { label: '草稿', type: 'default' },
  PENDING_SUBMIT: { label: '待提交', type: 'default' },
  PENDING: { label: '待处理', type: 'warning' },
  PENDING_REVIEW: { label: '待审核', type: 'warning' },
  PENDING_HANDLE: { label: '待处理', type: 'warning' },
  PENDING_CONFIRM: { label: '待确认', type: 'warning' },
  SUBMITTED: { label: '已提交', type: 'processing' },
  WITHDRAWN: { label: '已撤回', type: 'default' },
  REVIEWING: { label: '审核中', type: 'processing' },
  PROCESSING: { label: '处理中', type: 'processing' },
  APPROVED: { label: '已通过', type: 'success' },
  CONFIRMED: { label: '已确认', type: 'success' },
  COMPLETED: { label: '已完成', type: 'success' },
  FINISHED: { label: '已结束', type: 'success' },
  RETURNED: { label: '已退回', type: 'warning' },
  REJECTED: { label: '已驳回', type: 'danger' },
  FAILED: { label: '未通过', type: 'danger' },
  OVERDUE: { label: '已逾期', type: 'danger' },
  ABNORMAL: { label: '异常', type: 'danger' },
  PUBLISHED: { label: '已发布', type: 'success' },
  ARCHIVED: { label: '已归档', type: 'info' },
  VOIDED: { label: '已作废', type: 'danger' },
  READONLY: { label: '只读', type: 'info' },
  NOT_STARTED: { label: '未开始', type: 'default' },

  // 教学任务 / 课表
  PENDING_ASSIGN: { label: '待分配教师', type: 'warning' },
  ASSIGNED: { label: '待教师确认', type: 'processing' },
  TEACHER_CONFIRMED: { label: '教师已确认', type: 'success' },
  REJECTED_BY_TEACHER: { label: '教师已退回', type: 'danger' },
  COLLEGE_CONFIRMED: { label: '学院已确认', type: 'processing' },
  READY: { label: '已就绪', type: 'success' },
  MERGED: { label: '已并入合班', type: 'info' },
  PRE_PUBLISHED: { label: '预发布', type: 'processing' },

  // 选课
  OPEN: { label: '开放中', type: 'processing' },
  CLOSED: { label: '已截止', type: 'warning' },
  LOCKED: { label: '名单已锁定', type: 'success' },
  SELECTED: { label: '已选中', type: 'success' },
  DROPPED: { label: '已退选', type: 'default' },
  PENDING_LOTTERY: { label: '待摇号', type: 'warning' },
  LOTTERY_LOST: { label: '未中签', type: 'danger' },
  COURSE_CANCELLED: { label: '课程已取消', type: 'danger' },

  // 考务 / 考勤
  COURSE_CONFIRMED: { label: '课程已确认', type: 'processing' },
  ARRANGED: { label: '已编排', type: 'processing' },
  REMOVED: { label: '已移除', type: 'default' },
  ACTIVE: { label: '有效', type: 'success' },
  PRESENT: { label: '到考', type: 'success' },
  ABSENT: { label: '缺考', type: 'danger' },
  LATE: { label: '迟到', type: 'warning' },
  LEAVE: { label: '请假', type: 'info' },
  CHEAT: { label: '作弊', type: 'danger' },
  DEFERRED: { label: '缓考', type: 'warning' },
  EXEMPT: { label: '免修', type: 'info' },

  // 成绩审核
  INPUTTING: { label: '录入中', type: 'processing' },
  COLLEGE_REVIEW: { label: '学院审核中', type: 'warning' },
  ACADEMIC_REVIEW: { label: '教务终审中', type: 'processing' },
  CHANGE_REVIEW: { label: '更正审核中', type: 'warning' },

  // 缓考审批节点
  COUNSELOR_REVIEW: { label: '辅导员审批中', type: 'warning' },
  TEACHER_CONFIRM: { label: '任课教师确认中', type: 'warning' },
  ACADEMIC_FINAL: { label: '教务处终审中', type: 'processing' }
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
