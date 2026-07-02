/**
 * 11 权限与流程中心 — API Contract（冻结）
 * 数据流：页面 → provider → api(mock|real) → 本契约
 * 统一响应包裹：{ code, message, data, timestamp, requestId }
 * code=0 成功；非 0 见 WORKFLOW_ERROR_CODES。
 * 空态：列表类 data.list=[] 且 data.total=0；详情类 data=null + 业务错误码。
 * 错误态：HTTP 200 + code!==0（业务错误）或网络层异常（由调用侧捕获）。
 */

export const RESPONSE_ENVELOPE = Object.freeze({
  code: 'number  0=成功',
  message: 'string 人类可读信息',
  data: 'object|array|null 业务数据',
  timestamp: 'number 服务端毫秒时间戳',
  requestId: 'string 链路追踪 id'
})

/** 业务错误码（40xxx 客户端 / 41xxx 权限 / 42xxx 状态冲突 / 50xxx 服务端） */
export const WORKFLOW_ERROR_CODES = Object.freeze({
  OK: 0,
  NOT_FOUND: 40401, // 对象不存在
  INVALID_PARAM: 40001, // 参数非法
  REJECT_REASON_TOO_SHORT: 40002, // 退回原因不足最小字数
  NO_PERMISSION: 41001, // 无操作权限
  MODULE_NO_LICENSE: 41002, // 模块未授权（licenseContext 预留）
  MODULE_READONLY: 41003, // 模块到期只读（licenseContext 预留）
  TASK_ALREADY_FINISHED: 42001, // 任务已终态，不可重复处理
  TASK_NOT_WITHDRAWABLE: 42002, // 当前节点不允许撤回
  TEMPLATE_HAS_RUNNING_INSTANCE: 42003, // 模板有在途实例，停用需确认
  SERVER_ERROR: 50000
})

/**
 * 18 个接口契约。
 * 字段：path / method / params(query) / body / responseData(data 结构) / errors(可能业务码)
 * real 实现必须与此逐一对齐（见 workflow.api.real.example.js）。
 */
export const WORKFLOW_API_CONTRACT = Object.freeze({
  /** 1. 流程中心概览 */
  getWorkflowOverview: {
    path: '/api/v1/workflow/overview',
    method: 'GET',
    params: {},
    body: null,
    responseData:
      '{ pendingTaskCount, templateCount, enabledTemplateCount, roleCount, permissionCount, moduleUsage:[{moduleCode,enabledTemplates,pendingTasks}], recentRecords:[ApprovalRecord], abnormalHints:[{type,text,level}] }',
    errors: ['SERVER_ERROR']
  },
  /** 2. 流程模板列表 */
  getProcessTemplates: {
    path: '/api/v1/workflow/process-templates',
    method: 'GET',
    params: { moduleCode: 'string?', status: 'string?', keyword: 'string?', page: 'number?', pageSize: 'number?' },
    body: null,
    responseData: '{ list:[ProcessTemplate], total }',
    errors: ['INVALID_PARAM']
  },
  /** 3. 流程模板详情 */
  getProcessTemplateDetail: {
    path: '/api/v1/workflow/process-templates/{id}',
    method: 'GET',
    params: {},
    body: null,
    responseData: 'ProcessTemplate（含结构化 nodes[]）',
    errors: ['NOT_FOUND']
  },
  /** 4. 更新流程模板状态 */
  updateProcessTemplateStatus: {
    path: '/api/v1/workflow/process-templates/{id}/status',
    method: 'PATCH',
    params: {},
    body: { status: 'PROCESS_STATUS' },
    responseData: 'ProcessTemplate（更新后）',
    errors: ['NOT_FOUND', 'NO_PERMISSION', 'MODULE_READONLY', 'TEMPLATE_HAS_RUNNING_INSTANCE']
  },
  /** 5. 审批任务列表 */
  getApprovalTasks: {
    path: '/api/v1/workflow/approval-tasks',
    method: 'GET',
    params: { tab: 'ALL|MINE_PENDING|TASK_STATUS?', moduleCode: 'string?', keyword: 'string?', page: 'number?', pageSize: 'number?' },
    body: null,
    responseData: '{ list:[ApprovalTask], total }',
    errors: ['INVALID_PARAM']
  },
  /** 6. 审批任务详情 */
  getApprovalTaskDetail: {
    path: '/api/v1/workflow/approval-tasks/{id}',
    method: 'GET',
    params: {},
    body: null,
    responseData: 'ApprovalTask（含 records 时间线）',
    errors: ['NOT_FOUND']
  },
  /** 7. 审批通过 */
  approveTask: {
    path: '/api/v1/workflow/approval-tasks/{id}/approve',
    method: 'POST',
    params: {},
    body: { comment: 'string?' },
    responseData: 'ApprovalTask（更新后）',
    errors: ['NOT_FOUND', 'NO_PERMISSION', 'MODULE_READONLY', 'TASK_ALREADY_FINISHED']
  },
  /** 8. 审批退回（原因必填，≥REJECT_REASON_MIN_LENGTH 字） */
  rejectTask: {
    path: '/api/v1/workflow/approval-tasks/{id}/reject',
    method: 'POST',
    params: {},
    body: { reason: 'string 必填≥5字' },
    responseData: 'ApprovalTask（更新后，业务回到可编辑）',
    errors: ['NOT_FOUND', 'REJECT_REASON_TOO_SHORT', 'NO_PERMISSION', 'MODULE_READONLY', 'TASK_ALREADY_FINISHED']
  },
  /** 9. 审批撤回（发起人） */
  withdrawTask: {
    path: '/api/v1/workflow/approval-tasks/{id}/withdraw',
    method: 'POST',
    params: {},
    body: { reason: 'string?' },
    responseData: 'ApprovalTask（更新后）',
    errors: ['NOT_FOUND', 'TASK_NOT_WITHDRAWABLE', 'TASK_ALREADY_FINISHED', 'MODULE_READONLY']
  },
  /** 10. 流程实例列表 */
  getProcessInstances: {
    path: '/api/v1/workflow/process-instances',
    method: 'GET',
    params: { moduleCode: 'string?', status: 'string?', page: 'number?', pageSize: 'number?' },
    body: null,
    responseData: '{ list:[ProcessInstance], total }',
    errors: []
  },
  /** 11. 流程实例详情 */
  getProcessInstanceDetail: {
    path: '/api/v1/workflow/process-instances/{id}',
    method: 'GET',
    params: {},
    body: null,
    responseData: 'ProcessInstance',
    errors: ['NOT_FOUND']
  },
  /** 12. 角色列表 */
  getRoles: {
    path: '/api/v1/workflow/roles',
    method: 'GET',
    params: { keyword: 'string?' },
    body: null,
    responseData: '{ list:[Role], total }',
    errors: []
  },
  /** 13. 角色详情 */
  getRoleDetail: {
    path: '/api/v1/workflow/roles/{id}',
    method: 'GET',
    params: {},
    body: null,
    responseData: 'Role（含 permissionKeys 全量）',
    errors: ['NOT_FOUND']
  },
  /** 14. 更新角色权限 */
  updateRolePermissions: {
    path: '/api/v1/workflow/roles/{id}/permissions',
    method: 'PUT',
    params: {},
    body: { permissionKeys: 'string[]', dataScope: 'DATA_SCOPE?' },
    responseData: 'Role（更新后）',
    errors: ['NOT_FOUND', 'NO_PERMISSION', 'MODULE_READONLY']
  },
  /** 15. 权限点列表 */
  getPermissions: {
    path: '/api/v1/workflow/permissions',
    method: 'GET',
    params: { moduleCode: 'string?', type: 'PERMISSION_TYPE?', keyword: 'string?', page: 'number?', pageSize: 'number?' },
    body: null,
    responseData: '{ list:[Permission], total }',
    errors: []
  },
  /** 16. 更新权限点状态 */
  updatePermissionStatus: {
    path: '/api/v1/workflow/permissions/{id}/status',
    method: 'PATCH',
    params: {},
    body: { status: 'ENABLED|DISABLED' },
    responseData: 'Permission（更新后）',
    errors: ['NOT_FOUND', 'NO_PERMISSION', 'MODULE_READONLY']
  },
  /** 17. 操作审计日志 */
  getAuditLogs: {
    path: '/api/v1/workflow/audit-logs',
    method: 'GET',
    params: { targetType: 'AUDIT_TARGET_TYPE?', page: 'number?', pageSize: 'number?' },
    body: null,
    responseData: '{ list:[AuditLog], total }',
    errors: []
  },
  /** 18. 当前 permissionContext */
  getPermissionContext: {
    path: '/api/v1/workflow/permission-context',
    method: 'GET',
    params: {},
    body: null,
    responseData: 'PermissionContext（角色/学校/院系/班级/可访问模块/权限点/数据范围/菜单与按钮权限）',
    errors: []
  }
})
