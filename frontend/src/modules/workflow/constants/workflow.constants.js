/**
 * 11 权限与流程中心 — 集中枚举（全系统底座）
 * 禁止页面散写字符串；后续业务模块（实习/毕设/迎新等）一律从此处 import。
 * 上位依据：docs/source-design/11-权限与流程中心深化设计、docs/commercialization/03-模块开关权限菜单控制模型
 */

/** 业务模块编码（与总册 V3.0 §3.2 / route-freeze moduleCode 对齐） */
export const WORKFLOW_MODULE_CODE = Object.freeze({
  STUDENT: 'STUDENT',
  INTERNSHIP: 'INTERNSHIP',
  GRADUATION: 'GRADUATION',
  ONBOARDING: 'ONBOARDING',
  CAMPUS_SERVICE: 'CAMPUS_SERVICE',
  ACADEMIC: 'ACADEMIC',
  EMPLOYMENT: 'EMPLOYMENT',
  DASHBOARD: 'DASHBOARD',
  WORKFLOW: 'WORKFLOW'
})

export const MODULE_LABELS = Object.freeze({
  STUDENT: '学生主档',
  INTERNSHIP: '岗位实习',
  GRADUATION: '毕业设计',
  ONBOARDING: '数字迎新',
  CAMPUS_SERVICE: '在校服务',
  ACADEMIC: '学业过程',
  EMPLOYMENT: '毕业就业',
  DASHBOARD: '数据驾驶舱',
  WORKFLOW: '权限与流程'
})

/** 流程模板状态 */
export const PROCESS_STATUS = Object.freeze({
  ENABLED: 'ENABLED',
  DISABLED: 'DISABLED',
  DRAFT: 'DRAFT'
})

export const PROCESS_STATUS_LABELS = Object.freeze({
  ENABLED: '已启用',
  DISABLED: '已停用',
  DRAFT: '草稿'
})

/** 审批任务状态 */
export const TASK_STATUS = Object.freeze({
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  WITHDRAWN: 'WITHDRAWN',
  COMPLETED: 'COMPLETED',
  CANCELED: 'CANCELED'
})

export const TASK_STATUS_LABELS = Object.freeze({
  PENDING: '待处理',
  APPROVED: '已通过',
  REJECTED: '已退回',
  WITHDRAWN: '已撤回',
  COMPLETED: '已完成',
  CANCELED: '已取消'
})

/** 任务状态 → AppBadge type（success/warning/danger/info/neutral） */
export const TASK_STATUS_BADGE = Object.freeze({
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
  WITHDRAWN: 'neutral',
  COMPLETED: 'success',
  CANCELED: 'neutral'
})

/** 流程实例状态 */
export const PROCESS_INSTANCE_STATUS = Object.freeze({
  RUNNING: 'RUNNING',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  WITHDRAWN: 'WITHDRAWN',
  COMPLETED: 'COMPLETED',
  CANCELED: 'CANCELED'
})

export const PROCESS_INSTANCE_STATUS_LABELS = Object.freeze({
  RUNNING: '流转中',
  APPROVED: '已通过',
  REJECTED: '已退回',
  WITHDRAWN: '已撤回',
  COMPLETED: '已完成',
  CANCELED: '已取消'
})

/** 审批动作 */
export const APPROVAL_ACTION = Object.freeze({
  APPROVE: 'APPROVE',
  REJECT: 'REJECT',
  WITHDRAW: 'WITHDRAW',
  TRANSFER: 'TRANSFER',
  CC: 'CC',
  ADD_SIGN: 'ADD_SIGN',
  COMMENT: 'COMMENT',
  SUBMIT: 'SUBMIT'
})

export const APPROVAL_ACTION_LABELS = Object.freeze({
  APPROVE: '通过',
  REJECT: '退回',
  WITHDRAW: '撤回',
  TRANSFER: '转办',
  CC: '抄送',
  ADD_SIGN: '加签',
  COMMENT: '评论',
  SUBMIT: '提交'
})

/** 权限点类型 */
export const PERMISSION_TYPE = Object.freeze({
  MENU: 'MENU',
  PAGE: 'PAGE',
  BUTTON: 'BUTTON',
  DATA: 'DATA'
})

export const PERMISSION_TYPE_LABELS = Object.freeze({
  MENU: '菜单',
  PAGE: '页面',
  BUTTON: '按钮',
  DATA: '数据'
})

/** 角色编码（对齐 03 开关模型 / 老系统 ROLE_MAP 扩展） */
export const ROLE_CODE = Object.freeze({
  PLATFORM_OPERATOR: 'PLATFORM_OPERATOR',
  SCHOOL_ADMIN: 'SCHOOL_ADMIN',
  COLLEGE_ADMIN: 'COLLEGE_ADMIN',
  TEACHER: 'TEACHER',
  COUNSELOR: 'COUNSELOR',
  STUDENT: 'STUDENT',
  ENTERPRISE_MENTOR: 'ENTERPRISE_MENTOR'
})

export const ROLE_LABELS = Object.freeze({
  PLATFORM_OPERATOR: '平台运营',
  SCHOOL_ADMIN: '学校管理员',
  COLLEGE_ADMIN: '二级学院管理员',
  TEACHER: '指导教师',
  COUNSELOR: '辅导员',
  STUDENT: '学生',
  ENTERPRISE_MENTOR: '企业导师'
})

/** 数据范围（对齐总册 §10.5） */
export const DATA_SCOPE = Object.freeze({
  ALL: 'ALL',
  SCHOOL: 'SCHOOL',
  COLLEGE: 'COLLEGE',
  CLASS: 'CLASS',
  SELF: 'SELF',
  ASSIGNED: 'ASSIGNED'
})

export const DATA_SCOPE_LABELS = Object.freeze({
  ALL: '全平台',
  SCHOOL: '本校',
  COLLEGE: '本学院',
  CLASS: '本班级',
  SELF: '仅本人',
  ASSIGNED: '被指派对象'
})

/** 流程节点类型（本次不做可视化设计器，仅结构化预留） */
export const NODE_TYPE = Object.freeze({
  START: 'START',
  APPROVAL: 'APPROVAL',
  CC: 'CC',
  CONDITION: 'CONDITION',
  END: 'END'
})

export const NODE_TYPE_LABELS = Object.freeze({
  START: '发起',
  APPROVAL: '审批',
  CC: '抄送',
  CONDITION: '条件',
  END: '结束'
})

/**
 * 页面授权视图状态。
 * 与 licenseContext 冻结优先级兼容（03 模型 §1）：
 * 租户停用 > 到期只读 > 模块未授权 > 试用限制 > 功能开关 > 角色权限 > 按钮权限 > 数据范围。
 * 当前 licenseContext 为预留关系，本次不接真实授权中心（P6-2 落地 /platform 后替换来源）。
 */
export const LICENSE_VIEW_STATE = Object.freeze({
  NORMAL: 'NORMAL',
  READONLY: 'READONLY',
  NO_LICENSE: 'NO_LICENSE'
})

/** 操作审计对象类型 */
export const AUDIT_TARGET_TYPE = Object.freeze({
  PROCESS_TEMPLATE: 'PROCESS_TEMPLATE',
  PERMISSION: 'PERMISSION',
  ROLE: 'ROLE',
  APPROVAL_TASK: 'APPROVAL_TASK',
  PROCESS_INSTANCE: 'PROCESS_INSTANCE'
})

export const AUDIT_TARGET_LABELS = Object.freeze({
  PROCESS_TEMPLATE: '流程模板',
  PERMISSION: '权限点',
  ROLE: '角色',
  APPROVAL_TASK: '审批任务',
  PROCESS_INSTANCE: '流程实例'
})

/** 退回原因最小字数（V2.1 §11.2 冻结） */
export const REJECT_REASON_MIN_LENGTH = 5

/** 任务筛选页签（审批任务中心） */
export const TASK_FILTER_TABS = Object.freeze([
  { key: 'ALL', label: '全部' },
  { key: 'MINE_PENDING', label: '待我处理' },
  { key: TASK_STATUS.APPROVED, label: '已通过' },
  { key: TASK_STATUS.REJECTED, label: '已退回' },
  { key: TASK_STATUS.WITHDRAWN, label: '已撤回' },
  { key: TASK_STATUS.COMPLETED, label: '已完成' }
])
