/**
 * Dashboard Provider — 数据与变更操作的统一入口
 *
 * 当前默认走 mock 实现；接真实后端时仅替换本文件中的实现，
 * 页面、store、组件无需改动。
 */
import {
  fetchDashboardRaw as mockFetchDashboardRaw,
  resolveRiskApiMock as mockResolveRisk,
  remindStudentApiMock as mockRemindStudent,
  completeTaskApiMock as mockCompleteTask
} from '../data/dashboard.mock.js'

/** @typedef {Awaited<ReturnType<typeof fetchDashboardRaw>>} DashboardRawData */

/**
 * 拉取 Dashboard 原始数据（等价于 GET /dashboard）
 * @param {string} [teacherId]
 * @returns {Promise<DashboardRawData>}
 */
export async function fetchDashboardRaw(teacherId = 't-002') {
  return mockFetchDashboardRaw(teacherId)
}

/**
 * 标记风险已处理（等价于 POST /risks/:riskId/resolve）
 * @param {string} riskId
 */
export async function resolveRiskApiMock(riskId) {
  return mockResolveRisk(riskId)
}

/**
 * 向学生发起提醒（等价于 POST /risks/:riskId/remind）
 * @param {string} riskId
 */
export async function remindStudentApiMock(riskId) {
  return mockRemindStudent(riskId)
}

/**
 * 完成待办（等价于 POST /tasks/:taskId/complete）
 * @param {string} taskId
 */
export async function completeTaskApiMock(taskId) {
  return mockCompleteTask(taskId)
}
