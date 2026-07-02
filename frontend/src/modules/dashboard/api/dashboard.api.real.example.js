/**
 * Dashboard 真实 API 示例 — 当前不启用，仅供后端接入参考
 *
 * ⚠️ 请勿在生产代码中 import 本文件。
 * 接真实后端时，在 provider/dashboard.provider.js 中将 mock 调用替换为下方示例实现。
 */
import {
  DASHBOARD_API_PATHS,
  DASHBOARD_ERROR_CODES,
  ok,
  fail
} from './dashboard.contract.js'

/** @typedef {import('./dashboard.contract.js').ApiResponse} ApiResponse */

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

/**
 * 示例 HTTP 客户端（可替换为 axios / ofetch 等）
 * @template T
 * @param {string} path
 * @param {RequestInit} [options]
 * @returns {Promise<ApiResponse<T>>}
 */
async function httpClient(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    ...options
  })

  if (!response.ok) {
    return fail(DASHBOARD_ERROR_CODES.SERVER_ERROR, `HTTP ${response.status}`)
  }

  return response.json()
}

/**
 * GET /api/dashboard/overview
 * @param {string} [teacherId]
 */
export async function fetchDashboardOverview(teacherId = 't-002') {
  const query = teacherId ? `?teacherId=${encodeURIComponent(teacherId)}` : ''
  return httpClient(`/dashboard/overview${query}`)
}

/**
 * GET /api/dashboard/risks
 * @param {import('./dashboard.contract.js').DashboardRisksQuery} [params]
 */
export async function fetchDashboardRisks(params = {}) {
  const search = new URLSearchParams()
  if (params.status) search.set('status', params.status)
  if (params.riskLevel) search.set('riskLevel', params.riskLevel)
  if (params.studentId) search.set('studentId', params.studentId)
  if (params.module) search.set('module', params.module)
  const qs = search.toString()
  return httpClient(`/dashboard/risks${qs ? `?${qs}` : ''}`)
}

/**
 * POST /api/dashboard/risks/:riskId/remind
 * @param {string} riskId
 * @param {import('./dashboard.contract.js').RemindRiskPayload} payload
 */
export async function remindRisk(riskId, payload) {
  return httpClient(`/dashboard/risks/${encodeURIComponent(riskId)}/remind`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

/**
 * POST /api/dashboard/risks/:riskId/follow-up
 * @param {string} riskId
 * @param {import('./dashboard.contract.js').FollowUpRiskPayload} payload
 */
export async function followUpRisk(riskId, payload) {
  return httpClient(`/dashboard/risks/${encodeURIComponent(riskId)}/follow-up`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

/**
 * POST /api/dashboard/risks/:riskId/resolve
 * @param {string} riskId
 * @param {import('./dashboard.contract.js').ResolveRiskPayload} payload
 */
export async function resolveRisk(riskId, payload) {
  return httpClient(`/dashboard/risks/${encodeURIComponent(riskId)}/resolve`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

/**
 * POST /api/dashboard/tasks/:taskId/complete
 * @param {string} taskId
 * @param {import('./dashboard.contract.js').CompleteTaskPayload} payload
 */
export async function completeDashboardTask(taskId, payload) {
  return httpClient(`/dashboard/tasks/${encodeURIComponent(taskId)}/complete`, {
    method: 'POST',
    body: JSON.stringify(payload)
  })
}

/**
 * GET /api/dashboard/operation-logs
 * @param {import('./dashboard.contract.js').OperationLogsQuery} [params]
 */
export async function fetchOperationLogs(params = {}) {
  const search = new URLSearchParams()
  if (params.studentId) search.set('studentId', params.studentId)
  if (params.riskId) search.set('riskId', params.riskId)
  if (params.taskId) search.set('taskId', params.taskId)
  if (params.limit) search.set('limit', String(params.limit))
  const qs = search.toString()
  return httpClient(`/dashboard/operation-logs${qs ? `?${qs}` : ''}`)
}

// 路径常量导出，便于后端对照
export { DASHBOARD_API_PATHS, DASHBOARD_ERROR_CODES, ok, fail }
