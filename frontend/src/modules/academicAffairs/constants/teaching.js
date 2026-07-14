/** 教学任务 / 课表 · 前端展示常量（与后端 task/schedule service 枚举一致）。 */

export const TASK_BATCH_STATUS = {
  DRAFT: '草稿',
  COLLEGE_CONFIRMED: '学院确认',
  TEACHER_CONFIRMED: '教师确认',
  SUBMITTED: '已提交',
  APPROVED: '已通过'
}

export const TASK_STATUS = {
  PENDING_ASSIGN: '待分配',
  ASSIGNED: '已分配',
  TEACHER_CONFIRMED: '教师已确认',
  REJECTED_BY_TEACHER: '教师退回'
}

export const SCHEDULE_BATCH_STATUS = {
  DRAFT: '编制中',
  PRE_PUBLISHED: '预发布',
  PUBLISHED: '已发布',
  ARCHIVED: '已作废'
}

export const WEEK_PARITY = { ALL: '全周', ODD: '单周', EVEN: '双周' }

export function taskBatchColor(s) {
  switch (s) {
    case 'APPROVED': return 'success'
    case 'SUBMITTED': return 'primary'
    case 'DRAFT': return 'default'
    default: return 'warning'
  }
}

export function taskColor(s) {
  switch (s) {
    case 'TEACHER_CONFIRMED': return 'success'
    case 'ASSIGNED': return 'primary'
    case 'REJECTED_BY_TEACHER': return 'danger'
    default: return 'default'
  }
}

export function scheduleBatchColor(s) {
  switch (s) {
    case 'PUBLISHED': return 'success'
    case 'PRE_PUBLISHED': return 'primary'
    case 'ARCHIVED': return 'danger'
    default: return 'default'
  }
}
