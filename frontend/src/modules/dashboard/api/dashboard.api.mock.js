/**
 * Dashboard Mock API — 与 dashboard.contract.js 契约一致的本地实现
 *
 * 数据源：data/dashboard.mock.js（不复制 mock 数据）
 * 不发起真实网络请求，不直接操作组件或 store。
 */
import {
  fetchDashboardRaw as loadDashboardRaw,
  resolveRiskApiMock as mockResolveDelay,
  remindStudentApiMock as mockRemindDelay,
  completeTaskApiMock as mockCompleteDelay
} from '../data/dashboard.mock.js'
import {
  normalizeDashboardData
} from '../adapter/dashboard.adapter.js'
import { ok, fail, DASHBOARD_ERROR_CODES } from './dashboard.contract.js'

/** @typedef {import('./dashboard.contract.js').ApiResponse} ApiResponse */

/**
 * GET /api/dashboard/overview
 * @param {string} [teacherId]
 * @returns {Promise<ApiResponse<import('../data/dashboard.mock.js').fetchDashboardRaw extends (...args: any) => Promise<infer R> ? R : never>>}
 */
export async function fetchDashboardOverview(teacherId = 't-002') {
  try {
    const raw = await loadDashboardRaw(teacherId)
    return ok(raw)
  } catch (e) {
    return fail(
      DASHBOARD_ERROR_CODES.SERVER_ERROR,
      e instanceof Error ? e.message : '首页数据加载失败'
    )
  }
}

/**
 * GET /api/dashboard/risks
 * @param {import('./dashboard.contract.js').DashboardRisksQuery} [params]
 */
export async function fetchDashboardRisks(params = {}) {
  try {
    const raw = await loadDashboardRaw()
    const vm = normalizeDashboardData(raw)
    let list = vm.risks

    if (params.status) {
      list = list.filter((r) => r.status === params.status)
    }
    if (params.riskLevel) {
      list = list.filter((r) => r.riskLevel === params.riskLevel)
    }
    if (params.studentId) {
      list = list.filter((r) => r.studentId === params.studentId)
    }
    if (params.module) {
      const riskIdsForModule = new Set(
        vm.tasks.filter((t) => t.module === params.module).map((t) => t.relatedRiskId).filter(Boolean)
      )
      list = list.filter((r) => r.riskType === params.module || riskIdsForModule.has(r.riskId))
    }

    return ok({ risks: list, total: list.length })
  } catch (e) {
    return fail(
      DASHBOARD_ERROR_CODES.SERVER_ERROR,
      e instanceof Error ? e.message : '风险列表加载失败'
    )
  }
}

/**
 * POST /api/dashboard/risks/:riskId/remind
 * @param {string} riskId
 * @param {import('./dashboard.contract.js').RemindRiskPayload} payload
 */
export async function remindRisk(riskId, payload) {
  if (!payload?.operatorId) {
    return fail(DASHBOARD_ERROR_CODES.VALIDATION_ERROR, 'operatorId 不能为空')
  }

  const raw = await loadDashboardRaw()
  const vm = normalizeDashboardData(raw)
  const risk = vm.risks.find((r) => r.riskId === riskId)
  if (!risk) {
    return fail(DASHBOARD_ERROR_CODES.RISK_NOT_FOUND, '风险记录不存在')
  }
  if (risk.status === 'resolved') {
    return fail(DASHBOARD_ERROR_CODES.INVALID_STATUS, '风险已处理，无法再次提醒')
  }

  await mockRemindDelay(riskId)

  if (risk.status === 'pending') {
    risk.status = 'processing'
    risk.statusLabel = '处理中'
  }

  const student = risk.studentId
    ? vm.students.find((s) => s.studentId === risk.studentId)
    : null

  const operationLog = {
    recordId: `rec-remind-${Date.now()}`,
    time: `${raw.today} 12:00`,
    operator: payload.operatorId,
    action: `发起提醒：${risk.riskTitle}`,
    target: student?.name || risk.riskTitle,
    result: '已发送',
    status: 'processing',
    relatedRiskId: risk.riskId,
    studentId: risk.studentId,
    closed: false
  }

  return ok({ risk, operationLog })
}

/**
 * POST /api/dashboard/risks/:riskId/follow-up
 * @param {string} riskId
 * @param {import('./dashboard.contract.js').FollowUpRiskPayload} payload
 */
export async function followUpRisk(riskId, payload) {
  if (!payload?.operatorId) {
    return fail(DASHBOARD_ERROR_CODES.VALIDATION_ERROR, 'operatorId 不能为空')
  }
  if (!payload?.content?.trim()) {
    return fail(DASHBOARD_ERROR_CODES.VALIDATION_ERROR, '跟进内容不能为空')
  }

  const raw = await loadDashboardRaw()
  const vm = normalizeDashboardData(raw)
  const risk = vm.risks.find((r) => r.riskId === riskId)
  if (!risk) {
    return fail(DASHBOARD_ERROR_CODES.RISK_NOT_FOUND, '风险记录不存在')
  }
  if (risk.status === 'resolved') {
    return fail(DASHBOARD_ERROR_CODES.INVALID_STATUS, '风险已处理，无法添加跟进')
  }

  if (risk.status === 'pending') {
    risk.status = 'processing'
    risk.statusLabel = '处理中'
  }

  const student = risk.studentId
    ? vm.students.find((s) => s.studentId === risk.studentId)
    : null

  const operationLog = {
    recordId: `rec-follow-${Date.now()}`,
    time: `${raw.today} 12:00`,
    operator: payload.operatorId,
    action: `填写跟进：${payload.content}`,
    target: student?.name || risk.riskTitle,
    result: '已记录',
    status: 'processing',
    relatedRiskId: risk.riskId,
    studentId: risk.studentId,
    closed: false
  }

  return ok({ risk, operationLog })
}

/**
 * POST /api/dashboard/risks/:riskId/resolve
 * @param {string} riskId
 * @param {import('./dashboard.contract.js').ResolveRiskPayload} payload
 */
export async function resolveRisk(riskId, payload) {
  if (!payload?.operatorId) {
    return fail(DASHBOARD_ERROR_CODES.VALIDATION_ERROR, 'operatorId 不能为空')
  }

  const raw = await loadDashboardRaw()
  const vm = normalizeDashboardData(raw)
  const risk = vm.risks.find((r) => r.riskId === riskId)
  if (!risk) {
    return fail(DASHBOARD_ERROR_CODES.RISK_NOT_FOUND, '风险记录不存在')
  }
  if (risk.status === 'resolved') {
    return fail(DASHBOARD_ERROR_CODES.INVALID_STATUS, '风险已处理')
  }

  await mockResolveDelay(riskId)

  risk.status = 'resolved'
  risk.statusLabel = '已处理'

  const updatedTasks = vm.tasks
    .filter(
      (t) => t.relatedRiskId === riskId || (risk.relatedTaskIds || []).includes(t.taskId)
    )
    .map((t) => {
      t.status = 'done'
      return t
    })

  const student = risk.studentId
    ? vm.students.find((s) => s.studentId === risk.studentId)
    : null

  const operationLog = {
    recordId: `rec-resolve-${Date.now()}`,
    time: `${raw.today} 12:00`,
    operator: payload.operatorId,
    action: `处理风险：${risk.riskTitle}`,
    target: student?.name || risk.riskTitle,
    result: payload.result || '已跟进',
    status: 'done',
    relatedRiskId: riskId,
    studentId: risk.studentId,
    closed: true
  }

  return ok({ risk, updatedTasks, operationLog })
}

/**
 * POST /api/dashboard/tasks/:taskId/complete
 * @param {string} taskId
 * @param {import('./dashboard.contract.js').CompleteTaskPayload} payload
 */
export async function completeDashboardTask(taskId, payload) {
  if (!payload?.operatorId) {
    return fail(DASHBOARD_ERROR_CODES.VALIDATION_ERROR, 'operatorId 不能为空')
  }

  const raw = await loadDashboardRaw()
  const vm = normalizeDashboardData(raw)
  const task = vm.tasks.find((t) => t.taskId === taskId)
  if (!task) {
    return fail(DASHBOARD_ERROR_CODES.TASK_NOT_FOUND, '待办任务不存在')
  }
  if (task.status === 'done') {
    return fail(DASHBOARD_ERROR_CODES.INVALID_STATUS, '待办已完成')
  }

  await mockCompleteDelay(taskId)

  task.status = 'done'

  const operationLog = {
    recordId: `rec-task-${Date.now()}`,
    time: `${raw.today} 12:00`,
    operator: payload.operatorId,
    action: `处理待办：${task.title}`,
    target: task.studentName || task.title,
    result: payload.result || '已跟进',
    status: 'done',
    relatedTaskId: task.taskId,
    studentId: task.studentId,
    relatedRiskId: task.relatedRiskId,
    closed: true
  }

  return ok({ task, operationLog })
}

/**
 * GET /api/dashboard/operation-logs
 * @param {import('./dashboard.contract.js').OperationLogsQuery} [params]
 */
export async function fetchOperationLogs(params = {}) {
  try {
    const raw = await loadDashboardRaw()
    const vm = normalizeDashboardData(raw)
    let logs = vm.operationLogs

    if (params.studentId) {
      logs = logs.filter((l) => l.studentId === params.studentId)
    }
    if (params.riskId) {
      logs = logs.filter((l) => l.relatedRiskId === params.riskId || l.riskId === params.riskId)
    }
    if (params.taskId) {
      logs = logs.filter((l) => l.relatedTaskId === params.taskId || l.taskId === params.taskId)
    }
    if (params.limit && params.limit > 0) {
      logs = logs.slice(0, params.limit)
    }

    return ok({ logs, total: logs.length })
  } catch (e) {
    return fail(
      DASHBOARD_ERROR_CODES.SERVER_ERROR,
      e instanceof Error ? e.message : '处理记录加载失败'
    )
  }
}
