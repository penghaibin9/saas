/**
 * A4 / P0-06 数据驾驶舱正式 facade。
 *
 * 生产正式事实：
 * - 角色 / dataScope / 品牌 / 权限动作：/data-center/context；
 * - 专题报表 / 发布版本 / 审计：/data-center/* MySQL 真值；
 * - 校级驾驶舱指标：既有 /stats/* 真实聚合。
 *
 * 开发环境仍允许只读指标使用既有 mock 便于纯前端调试；context、报表写入、审计、导出等
 * 权威事实永不回落浏览器内存，避免真实接口失败后继续“成功”。
 */
import {
  overviewMetrics,
  lifecycleFunnel,
  orientationStats,
  serviceStats,
  academicStats,
  internshipStats,
  graduationStats,
  employmentStats,
  riskStats,
  collegeRankings,
  majorRankings,
  classRankings,
  trendCharts,
  drilldownStudents,
  filterOptions
} from '@/mocks/dataCenter/dataCenter.mock'
import { request, shouldTryReal } from '@/services/http/client'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: list.slice(start, start + pageSize), total, page, pageSize }
}

function findLabel(options, value) {
  const hit = (options || []).find((o) => o.value === value)
  return hit ? hit.label : value || '—'
}

async function real(path, options) {
  try {
    return { code: 0, data: await request(path, options), message: 'ok' }
  } catch (e) {
    return { code: e.code || 1, bizCode: e.bizCode, data: null, message: e.message || '服务请求失败' }
  }
}

const RANKING_MAP = { COLLEGE: collegeRankings, MAJOR: majorRankings, CLASS: classRankings }
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

export const dataCenterApi = {
  /** 权威上下文：禁止 mockRuntime / roleProfiles 充当当前身份。 */
  getContext() {
    return real('/data-center/context')
  },

  /** 角色切换统一走全站身份上下文，不在数据驾驶舱内部维护第二套角色状态。 */
  switchRole() {
    return fail('数据驾驶舱不维护本地角色切换；请使用系统统一身份切换入口')
  },

  async getOverview({ caliber = 'REGISTERED' } = {}) {
    if (shouldTryReal()) return real('/stats/overview', { params: { caliber } })
    const data = overviewMetrics[caliber]
    return data ? ok(clone(data)) : fail('未知统计口径，请刷新后重试')
  },

  async getLifecycle(params = {}) {
    if (shouldTryReal()) {
      return real('/stats/lifecycle-board', { params: { caliber: params.caliber || 'REGISTERED' } })
    }
    const funnel = clone(lifecycleFunnel)
    let scopeLabel = '全校'
    if (params.collegeId) {
      const college = collegeRankings.rows.find((r) => r.id === params.collegeId)
      if (college) {
        const ratio = college.studentCount / collegeRankings.totalCount
        funnel.totalCount = Math.round(funnel.totalCount * ratio)
        funnel.stages = funnel.stages.map((s) => {
          const count = Math.round(s.count * ratio)
          return { ...s, count, abnormal: Math.max(1, Math.round(s.abnormal * ratio)),
            rate: Math.round((count / funnel.totalCount) * 1000) / 10 }
        })
        funnel.cohortLabel = college.name + ' · 2023 级（2026 届）'
        scopeLabel = college.name
      }
    }
    if (params.majorId) scopeLabel += ' · ' + findLabel(filterOptions.majors, params.majorId)
    if (params.classId) scopeLabel += ' · ' + findLabel(filterOptions.classes, params.classId)
    if (params.grade) scopeLabel += ' · ' + findLabel(filterOptions.grades, params.grade)
    return ok({
      funnel,
      stageStats: clone({
        ORIENTATION: orientationStats,
        SERVICE: serviceStats,
        ACADEMIC: academicStats,
        INTERNSHIP: internshipStats,
        GRADUATION: graduationStats,
        EMPLOYMENT: employmentStats
      }),
      scopeLabel,
      timeRangeLabel: findLabel(filterOptions.timeRanges, params.timeRange || 'LAST_6M'),
      trendCharts: clone(trendCharts)
    })
  },

  async getRankings(params = {}) {
    if (shouldTryReal()) {
      return real('/stats/rankings', { params: {
        level: params.level || 'COLLEGE', collegeId: params.collegeId, majorId: params.majorId
      } })
    }
    const data = RANKING_MAP[params.level || 'COLLEGE']
    return data ? ok(clone(data)) : fail('未知排行维度')
  },

  async getRiskStats(params = {}) {
    if (shouldTryReal()) return real('/stats/risk-board')
    const data = clone(riskStats)
    data.timeRangeLabel = findLabel(filterOptions.timeRanges, params.timeRange || 'LAST_6M')
    return ok(data)
  },

  async getDrilldownStudents(params = {}) {
    if (shouldTryReal()) {
      return real('/stats/drilldown', { params: {
        collegeId: params.collegeId,
        majorId: params.majorId,
        classId: params.classId,
        stage: params.stage,
        keyword: params.keyword,
        page: params.page || 1,
        pageSize: params.pageSize || 10
      } })
    }
    let list = [...drilldownStudents]
    if (params.metricKey && params.metricKey !== 'ALL') list = list.filter((s) => s.metricKeys.includes(params.metricKey))
    if (params.collegeId) list = list.filter((s) => s.collegeId === params.collegeId)
    if (params.majorId) list = list.filter((s) => s.majorId === params.majorId)
    if (params.classId) list = list.filter((s) => s.classId === params.classId)
    if (params.riskLevel) list = list.filter((s) => s.riskLevel === params.riskLevel)
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((s) => s.name.includes(kw) || s.studentNo.includes(kw))
    }
    return ok(paginate(clone(list), params))
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

  /** 未接正式消息任务链：明确失败，禁止生成浏览器假提醒。 */
  sendRiskReminder() {
    return fail('风险提醒尚未接入正式消息任务链，已禁止本地假成功')
  },

  /** 未接正式文件任务链：明确失败，禁止生成浏览器假 taskId。 */
  exportData() {
    return fail('数据驾驶舱导出尚未接入正式文件任务链，已禁止本地假任务')
  }
}

export default dataCenterApi
