/** 教学任务 / 课表 · 前端展示常量（与后端 task/schedule service 枚举一致）。 */

export const TASK_BATCH_STATUS = {
  DRAFT: '待生成/核对分配中',
  COLLEGE_CONFIRMED: '学院已确认(待教务终审)',
  TEACHER_CONFIRMED: '教师确认',
  SUBMITTED: '已提交',
  APPROVED: '已通过',
  RETURNED: '教务退回'
}

export const TASK_STATUS = {
  PENDING_ASSIGN: '待分配',
  ASSIGNED: '已分配(待教师确认)',
  TEACHER_CONFIRMED: '教师已确认',
  REJECTED_BY_TEACHER: '教师退回',
  READY: '已就绪(可排课)',
  MERGED: '已并入合班'
}

export const SCHEDULE_BATCH_STATUS = {
  DRAFT: '编制中',
  PRE_PUBLISHED: '预发布',
  PUBLISHED: '已发布',
  ARCHIVED: '已作废'
}

export const WEEK_PARITY = { ALL: '全周', ODD: '单周', EVEN: '双周' }

// 注：AppStatusTag 的 type 仅接受 success|processing|warning|danger|info|default（无 primary）；
// 此前 SUBMITTED/ASSIGNED 分支误用 'primary' 会触发 prop 校验告警且渲染为无样式空标签，Tier1 顺带修正。
export function taskBatchColor(s) {
  switch (s) {
    case 'APPROVED': return 'success'
    case 'SUBMITTED':
    case 'COLLEGE_CONFIRMED': return 'processing'
    case 'RETURNED': return 'danger'
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
    case 'MERGED': return 'default'
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
