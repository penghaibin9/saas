/** 教学任务 / 课表 · 前端展示常量（与后端 task/schedule service 枚举一致）。 */

export const TASK_BATCH_STATUS = {
  DRAFT: '待生成/核对分配中',
  COLLEGE_CONFIRMED: '学院已确认（待教务终审）',
  TEACHER_CONFIRMED: '教师确认',
  SUBMITTED: '已提交',
  APPROVED: '已通过',
  RETURNED: '教务退回',
  ARCHIVED: '已归档'
}

export const TASK_STATUS = {
  PENDING_ASSIGN: '待分配',
  ASSIGNED: '已分配（待教师确认）',
  TEACHER_CONFIRMED: '教师已确认',
  REJECTED_BY_TEACHER: '教师退回',
  READY: '已就绪（可排课）',
  MERGED: '已并入合班'
}

export const SCHEDULE_BATCH_STATUS = {
  DRAFT: '编制中',
  PRE_PUBLISHED: '预发布',
  PUBLISHED: '已发布',
  ARCHIVED: '已归档',
  VOIDED: '已作废'
}

export const WEEK_PARITY = { ALL: '全周', ODD: '单周', EVEN: '双周' }

export function taskBatchColor(s) {
  switch (s) {
    case 'APPROVED': return 'success'
    case 'SUBMITTED':
    case 'COLLEGE_CONFIRMED': return 'processing'
    case 'RETURNED': return 'danger'
    case 'ARCHIVED': return 'info'
    case 'DRAFT': return 'default'
    default: return 'warning'
  }
}

export function taskColor(s) {
  switch (s) {
    case 'TEACHER_CONFIRMED':
    case 'READY': return 'success'
    case 'ASSIGNED': return 'processing'
    case 'REJECTED_BY_TEACHER': return 'danger'
    case 'MERGED': return 'info'
    default: return 'default'
  }
}

export function scheduleBatchColor(s) {
  switch (s) {
    case 'PUBLISHED': return 'success'
    case 'PRE_PUBLISHED': return 'processing'
    case 'ARCHIVED': return 'info'
    case 'VOIDED': return 'danger'
    default: return 'default'
  }
}
