/**
 * Dashboard API 契约 — 路径、错误码、统一响应信封
 *
 * 本文档为前后端协作的单一事实来源（实现见 API-CONTRACT.md）。
 * 当前运行链路使用 dashboard.api.mock.js，不发起真实网络请求。
 */

/** @typedef {0 | string} ApiCode */

/**
 * 统一成功/失败响应信封
 * @template T
 * @typedef {Object} ApiResponse
 * @property {ApiCode} code
 * @property {string} message
 * @property {T | null} data
 */

/**
 * @typedef {Object} DashboardOverviewData
 * @property {import('../types/dashboard.types.js').TeacherProfile} teacher
 * @property {import('../types/dashboard.types.js').Student[]} students
 * @property {import('../types/dashboard.types.js').RiskEvent[]} risks
 * @property {import('../types/dashboard.types.js').TeacherTask[]} tasks
 * @property {import('../types/dashboard.types.js').OperationLog[]} operationLogs
 * @property {import('../types/dashboard.types.js').LifecycleStage[]} lifecycleStages
 * @property {import('../types/dashboard.types.js').LifecycleStage[]} lifecycleBannerStages
 * @property {import('../types/dashboard.types.js').DashboardMetric[]} overviewMetrics
 * @property {import('../types/dashboard.types.js').DashboardMetric[]} gdMetrics
 * @property {import('../types/dashboard.types.js').DashboardMetric[]} internshipMetrics
 * @property {import('../types/dashboard.types.js').DataQualityInfo} dataQuality
 * @property {string} today
 */

/**
 * @typedef {Object} DashboardRisksQuery
 * @property {import('../types/dashboard.types.js').RiskStatus} [status]
 * @property {import('../types/dashboard.types.js').RiskLevel} [riskLevel]
 * @property {string} [studentId]
 * @property {string} [module]
 */

/**
 * @typedef {Object} RemindRiskPayload
 * @property {string} channel
 * @property {string} [message]
 * @property {string} operatorId
 */

/**
 * @typedef {Object} FollowUpRiskPayload
 * @property {string} content
 * @property {string} [nextAction]
 * @property {string} operatorId
 */

/**
 * @typedef {Object} ResolveRiskPayload
 * @property {string} [result]
 * @property {string} [remark]
 * @property {string} operatorId
 */

/**
 * @typedef {Object} CompleteTaskPayload
 * @property {string} [result]
 * @property {string} [remark]
 * @property {string} operatorId
 */

/**
 * @typedef {Object} OperationLogsQuery
 * @property {string} [studentId]
 * @property {string} [riskId]
 * @property {string} [taskId]
 * @property {number} [limit]
 */

export const DASHBOARD_API_PATHS = {
  overview: 'GET /api/dashboard/overview',
  risks: 'GET /api/dashboard/risks',
  remindRisk: 'POST /api/dashboard/risks/:riskId/remind',
  followUpRisk: 'POST /api/dashboard/risks/:riskId/follow-up',
  resolveRisk: 'POST /api/dashboard/risks/:riskId/resolve',
  completeTask: 'POST /api/dashboard/tasks/:taskId/complete',
  operationLogs: 'GET /api/dashboard/operation-logs'
}

export const DASHBOARD_ERROR_CODES = {
  RISK_NOT_FOUND: 'DASHBOARD_RISK_NOT_FOUND',
  TASK_NOT_FOUND: 'DASHBOARD_TASK_NOT_FOUND',
  STUDENT_NOT_FOUND: 'DASHBOARD_STUDENT_NOT_FOUND',
  INVALID_STATUS: 'DASHBOARD_INVALID_STATUS',
  PERMISSION_DENIED: 'DASHBOARD_PERMISSION_DENIED',
  VALIDATION_ERROR: 'DASHBOARD_VALIDATION_ERROR',
  SERVER_ERROR: 'DASHBOARD_SERVER_ERROR'
}

/**
 * @template T
 * @param {T} data
 * @returns {ApiResponse<T>}
 */
export function ok(data) {
  return { code: 0, message: 'ok', data }
}

/**
 * @template T
 * @param {string} code
 * @param {string} message
 * @param {T | null} [data]
 * @returns {ApiResponse<T>}
 */
export function fail(code, message, data = null) {
  return { code, message, data }
}

/**
 * 从统一响应中取出 data；失败时抛出带 code 的 Error（供 provider 使用）
 * @template T
 * @param {ApiResponse<T>} response
 * @returns {T}
 */
export function unwrapResponse(response) {
  if (response.code !== 0) {
    const err = new Error(response.message || '请求失败')
    err.code = response.code
    throw err
  }
  return /** @type {T} */ (response.data)
}
