/**
 * 数据中心（数据驾驶舱）API（mock 实现）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 真实后端阶段仅替换实现，方法签名冻结不变（与 internship 模块同约定）。
 * 页面禁止直接 import mocks，必须经本文件获取数据；写操作真实变更内存数据并写入审计日志。
 */
import {
  tenantBrandConfig,
  mockRuntime,
  roleProfiles,
  statusOptions,
  filterOptions,
  exportOptions,
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
  reportList,
  reportDetailMap,
  auditLogs
} from '@/mocks/dataCenter/dataCenter.mock'
import { request, shouldTryReal } from '@/services/http/client'

import { MOCK_DELAY_MS } from '@/utils/mockDelay'

const DELAY = MOCK_DELAY_MS

function ok(data) {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ code: 0, data, message: 'ok' }), DELAY)
  })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: list.slice(start, start + pageSize), total, page, pageSize }
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

function activeProfile() {
  return roleProfiles[mockRuntime.activeRoleCode] || roleProfiles.PRINCIPAL
}

/** 导出范围 → 权限动作键（api 侧兜底校验，与页面按钮权限一致） */
const EXPORT_PERMISSION_MAP = {
  OVERVIEW: 'exportOverview',
  LIFECYCLE: 'exportLifecycle',
  RANKING: 'exportRanking',
  RISK: 'exportRisk',
  REPORT: 'exportReport'
}

const RANKING_MAP = { COLLEGE: collegeRankings, MAJOR: majorRankings, CLASS: classRankings }

let exportSeq = 1201
let auditSeq = 100
let reportSeq = 6

function pushAudit({ action, target, targetId = '', detail }) {
  const role = activeProfile().currentRole
  const entry = {
    id: 'al-' + ++auditSeq,
    time: '刚刚',
    userName: role.userName,
    roleName: role.roleName,
    action,
    target,
    targetId,
    detail
  }
  auditLogs.unshift(entry)
  return entry
}

function findLabel(options, value) {
  const hit = options.find((o) => o.value === value)
  return hit ? hit.label : value || '—'
}

export const dataCenterApi = {
  /** 品牌 / 当前角色 / 数据范围 / 权限动作 / 字典 / 可切换角色（页面初始化统一获取） */
  getContext() {
    const profile = activeProfile()
    return ok({
      tenantBrandConfig: { ...tenantBrandConfig },
      currentRole: { ...profile.currentRole },
      dataScope: { ...profile.dataScope },
      permissionActions: clone(profile.permissionActions),
      visibleMetricKeys: [...profile.visibleMetricKeys],
      statusOptions: clone(statusOptions),
      filterOptions: clone(filterOptions),
      exportOptions: clone(exportOptions),
      availableRoles: Object.values(roleProfiles).map((p) => ({
        value: p.currentRole.roleCode,
        label: p.currentRole.roleName + ' · ' + p.dataScope.scopeName
      }))
    })
  },

  /** 切换演示角色（mock 内部 activeRoleCode，切换后需重新 getContext） */
  switchRole(roleCode) {
    const profile = roleProfiles[roleCode]
    if (!profile) return fail('角色不存在或未开通数据中心访问权限')
    mockRuntime.activeRoleCode = roleCode
    return ok({ roleCode, roleName: profile.currentRole.roleName })
  },

  /** 全景概览（caliber：REGISTERED 在册口径 / NATURAL 自然口径） */
  async getOverview({ caliber = 'REGISTERED' } = {}) {
    if (shouldTryReal()) {
      try { return Promise.resolve({ code: 0, data: await request('/stats/overview', { params: { caliber } }), message: 'ok' }) }
      catch (e) { if (e.biz) return Promise.resolve({ code: e.code || 1, data: null, message: e.message }) }
    }
    const data = overviewMetrics[caliber]
    if (!data) return fail('未知统计口径，请刷新后重试')
    return ok(clone(data))
  },

  /** 生命周期漏斗 + 各阶段统计（选择学院时按学院在册占比折算漏斗） */
  getLifecycle(params = {}) {
    const funnel = clone(lifecycleFunnel)
    let scopeLabel = '全校'
    if (params.collegeId) {
      const college = collegeRankings.rows.find((r) => r.id === params.collegeId)
      if (college) {
        const ratio = college.studentCount / collegeRankings.totalCount
        funnel.totalCount = Math.round(funnel.totalCount * ratio)
        funnel.stages = funnel.stages.map((s) => {
          const count = Math.round(s.count * ratio)
          return {
            ...s,
            count,
            abnormal: Math.max(1, Math.round(s.abnormal * ratio)),
            rate: Math.round((count / funnel.totalCount) * 1000) / 10
          }
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

  /** 排行分析（level：COLLEGE / MAJOR / CLASS） */
  getRankings(params = {}) {
    const level = params.level || 'COLLEGE'
    const data = RANKING_MAP[level]
    if (!data) return fail('未知排行维度')
    return ok(clone(data))
  },

  /** 风险预警统计（来源分布 / 等级分布 / 处理进度 / 近 6 月趋势） */
  getRiskStats(params = {}) {
    const data = clone(riskStats)
    data.timeRangeLabel = findLabel(filterOptions.timeRanges, params.timeRange || 'LAST_6M')
    return ok(data)
  },

  /** 下钻学生清单（重点关注学生样本，分页；字段由页面展示时脱敏） */
  getDrilldownStudents(params = {}) {
    let list = [...drilldownStudents]
    if (params.metricKey && params.metricKey !== 'ALL') {
      list = list.filter((s) => s.metricKeys.includes(params.metricKey))
    }
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

  /** 专题报表列表（筛选 + 分页） */
  getReports(params = {}) {
    let list = [...reportList]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((r) => r.name.includes(kw) || r.id.includes(kw))
    }
    if (params.category) list = list.filter((r) => r.category === params.category)
    if (params.status) list = list.filter((r) => r.status === params.status)
    return ok(paginate(clone(list), params))
  },

  getReportDetail(id) {
    const detail = reportDetailMap[id]
    if (!detail) return fail('报表不存在或已被删除，请返回列表刷新后重试')
    return ok(clone(detail))
  },

  /** 新增报表配置（写操作：入列表 + 建详情 + 审计留痕） */
  createReport(payload = {}) {
    const name = (payload.name || '').trim()
    if (name.length < 4) return fail('报表名称必填且不少于 4 个字')
    const id = 'rpt-' + String(++reportSeq).padStart(3, '0')
    const row = {
      id,
      name,
      category: payload.category || 'ACADEMIC',
      categoryLabel: findLabel(filterOptions.reportCategories, payload.category || 'ACADEMIC'),
      cycle: payload.cycle || 'MONTHLY',
      cycleLabel: findLabel(statusOptions.reportCycles, payload.cycle || 'MONTHLY'),
      scopeName: (payload.scopeName || '').trim() || activeProfile().dataScope.scopeName,
      ownerName: activeProfile().currentRole.userName,
      updatedAt: '刚刚',
      status: 'DRAFT',
      statusLabel: '草稿',
      statusTone: 'default',
      metricCount: 0,
      description: (payload.description || '').trim() || '新建报表配置，指标接入后按周期自动汇聚'
    }
    reportList.unshift(row)
    reportDetailMap[id] = {
      id,
      name: row.name,
      status: row.status,
      statusLabel: row.statusLabel,
      statusTone: row.statusTone,
      description: row.description,
      config: {
        reportNo: 'RPT-NEW-' + id.toUpperCase(),
        cycleLabel: row.cycleLabel + '（发布后生效）',
        caliberLabel: '在册口径',
        scopeName: row.scopeName,
        ownerName: row.ownerName,
        createdAt: '刚刚',
        updatedAt: '刚刚',
        shareScope: '创建人 / 系统管理员',
        metricCount: 0
      },
      metrics: [],
      trend: null
    }
    pushAudit({
      action: '新增报表配置',
      target: row.name,
      targetId: id,
      detail: '统计周期：' + row.cycleLabel + ' · 数据范围：' + row.scopeName
    })
    return ok(clone(row))
  },

  /** 编辑报表配置（写操作：同步列表与详情 + 审计留痕） */
  updateReport(id, payload = {}) {
    const row = reportList.find((r) => r.id === id)
    const detail = reportDetailMap[id]
    if (!row || !detail) return fail('报表不存在或已被删除')
    if (row.status === 'VOIDED') return fail('已作废的报表不可编辑')
    const name = (payload.name || '').trim()
    if (name.length < 4) return fail('报表名称必填且不少于 4 个字')
    row.name = name
    if (payload.category) {
      row.category = payload.category
      row.categoryLabel = findLabel(filterOptions.reportCategories, payload.category)
    }
    if (payload.cycle) {
      row.cycle = payload.cycle
      row.cycleLabel = findLabel(statusOptions.reportCycles, payload.cycle)
    }
    if (payload.scopeName !== undefined && payload.scopeName.trim()) row.scopeName = payload.scopeName.trim()
    if (payload.description !== undefined) row.description = payload.description.trim()
    row.updatedAt = '刚刚'
    detail.name = row.name
    detail.description = row.description || detail.description
    detail.config.updatedAt = '刚刚'
    detail.config.scopeName = row.scopeName
    detail.config.cycleLabel = row.cycleLabel
    pushAudit({
      action: '更新报表配置',
      target: row.name,
      targetId: id,
      detail: '调整项：名称 / 周期 / 范围 / 说明（变更前版本已存档）'
    })
    return ok(clone(row))
  },

  /** 作废报表（逻辑删除：状态置 VOIDED，原因必填 ≥5 字，永久留痕） */
  voidReport(id, { reason } = {}) {
    if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 个字')
    const row = reportList.find((r) => r.id === id)
    const detail = reportDetailMap[id]
    if (!row || !detail) return fail('报表不存在或已被删除')
    if (row.status === 'VOIDED') return fail('该报表已是作废状态，无需重复操作')
    const trimmed = reason.trim()
    row.status = 'VOIDED'
    row.statusLabel = '已作废'
    row.statusTone = 'danger'
    row.voidReason = trimmed
    row.updatedAt = '刚刚'
    detail.status = 'VOIDED'
    detail.statusLabel = '已作废'
    detail.statusTone = 'danger'
    detail.voidInfo = {
      reason: trimmed,
      by: activeProfile().currentRole.userName + ' · ' + activeProfile().currentRole.roleName,
      time: '刚刚'
    }
    pushAudit({ action: '作废报表', target: row.name, targetId: id, detail: '作废原因：' + trimmed })
    return ok({ id, status: 'VOIDED', statusLabel: '已作废' })
  },

  /** 批量生成风险提醒建议（写操作：审计留痕，提醒建议下发责任教师工作台） */
  sendRiskReminder({ studentIds = [], note = '' } = {}) {
    if (!studentIds.length) return fail('请先勾选需要生成提醒建议的学生')
    const entry = pushAudit({
      action: '生成风险提醒建议',
      target: '风险学生 ' + studentIds.length + ' 人',
      detail: '提醒建议已下发至相关责任教师工作台' + (note ? '；备注：' + note : '')
    })
    return ok({ count: studentIds.length, auditId: entry.id })
  },

  /**
   * 导出数据（统一出口：默认脱敏 + 追踪水印 + 审计留痕）。
   * scope：OVERVIEW / LIFECYCLE / RANKING / RISK / REPORT；purpose 必填（导出用途）。
   */
  exportData({ scope, purpose, targetId = '', targetName = '' } = {}) {
    const scopeLabel = findLabel(exportOptions.scopes, scope)
    const purposeLabel = findLabel(exportOptions.purposes, purpose)
    if (!purpose) return fail('请选择导出用途，导出用途将写入审计日志')
    const permKey = EXPORT_PERMISSION_MAP[scope]
    const pa = permKey ? activeProfile().permissionActions[permKey] : null
    if (pa && (!pa.visible || !pa.allowed)) {
      return fail(pa.reason || '当前角色无权导出该范围数据')
    }
    const taskId = 'EXP-2026-' + ++exportSeq
    const entry = pushAudit({
      action: '导出' + scopeLabel,
      target: targetName || scopeLabel,
      targetId,
      detail: '用途：' + purposeLabel + ' · 已脱敏 + 追踪水印（任务 ' + taskId + '）'
    })
    return ok({ taskId, masked: true, watermark: true, auditId: entry.id })
  },

  /** 审计日志（targetId 可选：仅取某报表 / 对象相关记录） */
  getAuditLogs(params = {}) {
    let list = [...auditLogs]
    if (params.targetId) list = list.filter((l) => l.targetId === params.targetId)
    if (params.limit) list = list.slice(0, params.limit)
    return ok(clone(list))
  }
}

export default dataCenterApi
