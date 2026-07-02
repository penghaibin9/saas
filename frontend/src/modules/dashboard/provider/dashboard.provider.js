/**
 * Dashboard Provider — 数据与变更操作的统一入口
 *
 * 调用链：store → provider → api/dashboard.api.mock.js → data/dashboard.mock.js
 *
 * 接真实后端时：仅替换本文件中的 api 引用（mock → real），
 * 页面、store、组件无需改动。
 */
import {
  fetchDashboardOverview,
  fetchDashboardRisks,
  remindRisk as apiRemindRisk,
  followUpRisk as apiFollowUpRisk,
  resolveRisk as apiResolveRisk,
  completeDashboardTask as apiCompleteTask,
  fetchOperationLogs
} from '../api/dashboard.api.mock.js'
import { unwrapResponse } from '../api/dashboard.contract.js'

/** @typedef {Awaited<ReturnType<typeof fetchDashboardOverview>>['data']} DashboardOverviewRaw */

/**
 * 拉取 Dashboard 原始数据（等价于 GET /api/dashboard/overview）
 * @param {string} [teacherId]
 * @returns {Promise<NonNullable<DashboardOverviewRaw>>}
 */
export async function fetchDashboardRaw(teacherId = 't-002') {
  const response = await fetchDashboardOverview(teacherId)
  return unwrapResponse(response)
}

/**
 * 获取风险列表（等价于 GET /api/dashboard/risks）
 * @param {import('../api/dashboard.contract.js').DashboardRisksQuery} [params]
 */
export async function fetchRisks(params) {
  const response = await fetchDashboardRisks(params)
  return unwrapResponse(response)
}

/**
 * 获取处理记录（等价于 GET /api/dashboard/operation-logs）
 * @param {import('../api/dashboard.contract.js').OperationLogsQuery} [params]
 */
export async function fetchLogs(params) {
  const response = await fetchOperationLogs(params)
  return unwrapResponse(response)
}

/**
 * 向学生发起提醒（等价于 POST /api/dashboard/risks/:riskId/remind）
 * @param {string} riskId
 * @param {import('../api/dashboard.contract.js').RemindRiskPayload} [payload]
 */
export async function remindRisk(riskId, payload = {}) {
  const response = await apiRemindRisk(riskId, {
    channel: payload.channel || 'app',
    message: payload.message || '',
    operatorId: payload.operatorId || 'current-user'
  })
  return unwrapResponse(response)
}

/**
 * 添加风险跟进（等价于 POST /api/dashboard/risks/:riskId/follow-up）
 * @param {string} riskId
 * @param {import('../api/dashboard.contract.js').FollowUpRiskPayload} payload
 */
export async function followUpRisk(riskId, payload) {
  const response = await apiFollowUpRisk(riskId, payload)
  return unwrapResponse(response)
}

/**
 * 标记风险已处理（等价于 POST /api/dashboard/risks/:riskId/resolve）
 * @param {string} riskId
 * @param {import('../api/dashboard.contract.js').ResolveRiskPayload} [payload]
 */
export async function resolveRisk(riskId, payload = {}) {
  const response = await apiResolveRisk(riskId, {
    result: payload.result || '已跟进',
    remark: payload.remark || '',
    operatorId: payload.operatorId || 'current-user'
  })
  return unwrapResponse(response)
}

/**
 * 完成待办（等价于 POST /api/dashboard/tasks/:taskId/complete）
 * @param {string} taskId
 * @param {import('../api/dashboard.contract.js').CompleteTaskPayload} [payload]
 */
export async function completeTask(taskId, payload = {}) {
  const response = await apiCompleteTask(taskId, {
    result: payload.result || '已跟进',
    remark: payload.remark || '',
    operatorId: payload.operatorId || 'current-user'
  })
  return unwrapResponse(response)
}

/** @deprecated 使用 remindRisk */
export const remindStudentApiMock = remindRisk

/** @deprecated 使用 resolveRisk */
export const resolveRiskApiMock = resolveRisk

/** @deprecated 使用 completeTask */
export const completeTaskApiMock = completeTask
