/**
 * A4 / P0-06 数据驾驶舱正式 facade。
 *
 * 正式事实只来自服务端：
 * - 角色 / dataScope / 品牌 / 权限动作：/data-center/context；
 * - 专题报表 / 发布版本 / 审计：/data-center/* MySQL 真值；
 * - 校级驾驶舱指标：/stats/* 真实聚合。
 *
 * 本 facade 不再 import 数据驾驶舱 mock，也不根据运行环境回退浏览器指标。
 * 服务端不可用、口径未实现或参数不受支持时必须明确失败，禁止本地估算、补 0、假成功。
 */
import { request } from '@/services/http/client'

function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}

async function real(path, options) {
  try {
    return { code: 0, data: await request(path, options), message: 'ok' }
  } catch (e) {
    return { code: e.code || 1, bizCode: e.bizCode, data: null, message: e.message || '服务请求失败' }
  }
}

const viewedReportVersions = new Map()

function rememberReport(row) {
  if (row && row.id !== undefined && row.version !== undefined && row.version !== null) {
    viewedReportVersions.set(String(row.id), Number(row.version))
  }
  return row
}

function viewedVersion(id, explicit) {
  if (explicit !== undefined && explicit !== null) return Number(explicit)
  return viewedReportVersions.get(String(id))
}

function hasUnsupportedLifecycleFilter(params = {}) {
  return Boolean(params.collegeId || params.majorId || params.classId || params.grade || params.timeRange)
}

export const dataCenterApi = {
  /** 当前身份与数据范围只读服务端认证上下文。 */
  getContext() {
    return real('/data-center/context')
  },

  /** 角色切换统一走全站身份上下文，不在数据驾驶舱维护第二套角色状态。 */
  switchRole() {
    return fail('数据驾驶舱不维护本地角色切换；请使用系统统一身份切换入口')
  },

  getOverview({ caliber = 'REGISTERED' } = {}) {
    return real('/stats/overview', { params: { caliber } })
  },

  getLifecycle(params = {}) {
    if (hasUnsupportedLifecycleFilter(params)) {
      return fail('当前生命周期真实统计仅支持校级全量口径；学院/专业/班级/年级/时间筛选尚未服务端化，已禁止浏览器估算')
    }
    return real('/stats/lifecycle-board', { params: { caliber: params.caliber || 'REGISTERED' } })
  },

  getRankings(params = {}) {
    return real('/stats/rankings', {
      params: {
        level: params.level || 'COLLEGE',
        collegeId: params.collegeId,
        majorId: params.majorId
      }
    })
  },

  getRiskStats() {
    return real('/stats/risk-board')
  },

  getDrilldownStudents(params = {}) {
    const metricKey = params.metricKey || 'ALL'
    if (metricKey !== 'ALL') {
      return fail('该业务阶段/风险下钻尚未形成服务端统一口径，已禁止返回全校学生冒充命中名单')
    }
    if (params.riskLevel) {
      return fail('风险等级下钻尚未形成服务端统一口径，已禁止浏览器筛选冒充服务端结果')
    }
    return real('/stats/drilldown', {
      params: {
        collegeId: params.collegeId,
        majorId: params.majorId,
        classId: params.classId,
        stage: params.stage,
        keyword: params.keyword,
        page: params.page || 1,
        pageSize: params.pageSize || 10
      }
    })
  },

  async getReports(params = {}) {
    const res = await real('/data-center/reports', { params })
    if (res.code === 0) {
      const list = Array.isArray(res.data.items) ? res.data.items.map(rememberReport) : []
      res.data = { ...res.data, list }
    }
    return res
  },

  async getReportDetail(id) {
    const res = await real(`/data-center/reports/${encodeURIComponent(id)}`)
    if (res.code === 0) rememberReport(res.data)
    return res
  },

  async createReport(payload = {}) {
    const res = await real('/data-center/reports', { method: 'POST', body: payload })
    if (res.code === 0) rememberReport(res.data)
    return res
  },

  async updateReport(id, payload = {}) {
    const version = viewedVersion(id, payload.version)
    if (version === undefined) return fail('缺少报表版本，请刷新列表后重试')
    const res = await real(`/data-center/reports/${encodeURIComponent(id)}`, {
      method: 'PUT', body: { ...payload, version }
    })
    if (res.code === 0) rememberReport(res.data)
    return res
  },

  async publishReport(id, version) {
    const expected = viewedVersion(id, version)
    if (expected === undefined) return fail('缺少报表版本，请刷新详情后重试')
    const res = await real(`/data-center/reports/${encodeURIComponent(id)}/publish`, {
      method: 'POST', body: { version: expected }
    })
    if (res.code === 0) rememberReport(res.data)
    return res
  },

  async withdrawReport(id, version) {
    const expected = viewedVersion(id, version)
    if (expected === undefined) return fail('缺少报表版本，请刷新详情后重试')
    const res = await real(`/data-center/reports/${encodeURIComponent(id)}/withdraw`, {
      method: 'POST', body: { version: expected }
    })
    if (res.code === 0) rememberReport(res.data)
    return res
  },

  async voidReport(id, { reason, version } = {}) {
    const expected = viewedVersion(id, version)
    if (expected === undefined) return fail('缺少报表版本，请刷新列表后重试')
    const res = await real(`/data-center/reports/${encodeURIComponent(id)}/void`, {
      method: 'POST', body: { reason, version: expected }
    })
    if (res.code === 0) rememberReport(res.data)
    return res
  },

  getReportVersions(id) {
    return real(`/data-center/reports/${encodeURIComponent(id)}/versions`)
  },

  getAuditLogs(params = {}) {
    return real('/data-center/audit-logs', { params })
  },

  /** 未接正式消息任务链：明确失败，禁止生成浏览器提醒结果。 */
  sendRiskReminder() {
    return fail('风险提醒尚未接入正式消息任务链，已禁止本地假成功')
  },

  /** 未接正式文件任务链：明确失败，禁止生成浏览器导出任务。 */
  exportData() {
    return fail('数据驾驶舱导出尚未接入正式文件任务链，已禁止本地假任务')
  }
}

export default dataCenterApi
