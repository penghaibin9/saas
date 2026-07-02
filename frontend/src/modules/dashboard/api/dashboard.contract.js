/**
 * Dashboard API 契约 — 路径、错误码、统一响应信封
 *
 * 本文档为前后端协作的单一事实来源（实现见 API-CONTRACT.md）。
 * 当前运行链路使用 dashboard.api.mock.js，不发起真实网络请求。
 */

/** @typedef {0 | 'SUCCESS' | string} ApiCode */

/**
 * 统一成功/失败响应信封
 * @template T
 * @typedef {Object} ApiResponse
 * @property {ApiCode} code
 * @property {string} message
 * @property {T | null} data
 * @property {string} timestamp
 * @property {string} [requestId]
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

/** @typedef {ApiResponse<DashboardOverviewData>} DashboardResponse */

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
  statistics: 'GET /api/dashboard/statistics',
  trends: 'GET /api/dashboard/trends',
  todos: 'GET /api/dashboard/todos',
  alerts: 'GET /api/dashboard/alerts',
  quickEntries: 'GET /api/dashboard/quick-entries',
  risks: 'GET /api/dashboard/risks',
  remindRisk: 'POST /api/dashboard/risks/:riskId/remind',
  followUpRisk: 'POST /api/dashboard/risks/:riskId/follow-up',
  resolveRisk: 'POST /api/dashboard/risks/:riskId/resolve',
  completeTask: 'POST /api/dashboard/tasks/:taskId/complete',
  operationLogs: 'GET /api/dashboard/operation-logs'
}

export const DASHBOARD_ERROR_CODES = {
  SUCCESS: 'SUCCESS',
  UNAUTHORIZED: 'UNAUTHORIZED',
  FORBIDDEN: 'FORBIDDEN',
  BAD_REQUEST: 'BAD_REQUEST',
  SERVER_ERROR: 'SERVER_ERROR',
  MOCK_ERROR: 'MOCK_ERROR',
  RISK_NOT_FOUND: 'DASHBOARD_RISK_NOT_FOUND',
  TASK_NOT_FOUND: 'DASHBOARD_TASK_NOT_FOUND',
  STUDENT_NOT_FOUND: 'DASHBOARD_STUDENT_NOT_FOUND',
  INVALID_STATUS: 'DASHBOARD_INVALID_STATUS',
  PERMISSION_DENIED: 'DASHBOARD_PERMISSION_DENIED',
  VALIDATION_ERROR: 'DASHBOARD_VALIDATION_ERROR',
  DASHBOARD_SERVER_ERROR: 'DASHBOARD_SERVER_ERROR'
}

/**
 * @typedef {Object} DashboardStatisticCard
 * @property {string} metricId
 * @property {string} title
 * @property {number|string} value
 * @property {string} [unit]
 * @property {string} [status]
 */

/**
 * @typedef {Object} DashboardTrendItem
 * @property {string} trendId
 * @property {string} name
 * @property {number|string} value
 * @property {string} [deltaText]
 * @property {'up'|'down'|'flat'} [trend]
 */

/**
 * @typedef {Object} DashboardTodoItem
 * @property {string} taskId
 * @property {string} title
 * @property {string} module
 * @property {import('../types/dashboard.types.js').TaskStatus} status
 * @property {string} [deadline]
 */

/**
 * @typedef {Object} DashboardAlertItem
 * @property {string} riskId
 * @property {string} riskTitle
 * @property {import('../types/dashboard.types.js').RiskLevel} riskLevel
 * @property {import('../types/dashboard.types.js').RiskStatus} status
 */

/**
 * @typedef {Object} DashboardQuickEntry
 * @property {string} key
 * @property {string} label
 * @property {string} value
 */

/**
 * @template T
 * @param {T} data
 * @param {string} [requestId]
 * @returns {ApiResponse<T>}
 */
export function ok(data, requestId) {
  return {
    code: DASHBOARD_ERROR_CODES.SUCCESS,
    message: 'ok',
    data,
    timestamp: new Date().toISOString(),
    requestId
  }
}

/**
 * @template T
 * @param {string} code
 * @param {string} message
 * @param {T | null} [data]
 * @param {string} [requestId]
 * @returns {ApiResponse<T>}
 */
export function fail(code, message, data = null, requestId) {
  return { code, message, data, timestamp: new Date().toISOString(), requestId }
}

/**
 * 从统一响应中取出 data；失败时抛出带 code 的 Error（供 provider 使用）
 * @template T
 * @param {ApiResponse<T>} response
 * @returns {T}
 */
export function unwrapResponse(response) {
  if (response.code !== 0 && response.code !== DASHBOARD_ERROR_CODES.SUCCESS) {
    const err = new Error(response.message || '请求失败')
    err.code = response.code
    throw err
  }
  return /** @type {T} */ (response.data)
}
