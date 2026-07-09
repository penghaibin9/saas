/**
 * 岗位实习中心 API（P7：真实优先 + mock 兜底）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/internship/*；后端不可达时自动回退 mock，页面不白屏。
 * 业务错误（如意见<5字 422001 / 已处理 409001）直接透出，不回退 mock。
 */
import { request, shouldTryReal, requestUpload, requestBlob } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions,
  dashboardSummary,
  internshipStudents,
  studentDetailMap,
  attendanceExceptions,
  attendanceExceptionDetailMap,
  weeklyReports,
  weeklyReportDetailMap,
  riskStudents
} from '@/mocks/internship/internship.mock'

const DELAY = 120

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

/** 真实接口：失败直接透出，不回退 mock（生产级模块：实习批次 / 企业库） */
async function realStrict(realFn) {
  try {
    const data = await realFn()
    return { code: 0, data, message: 'ok' }
  } catch (e) {
    return { code: e.code || 1, data: null, message: e.message || '真实接口不可用' }
  }
}

async function realListStrict(path, params = {}) {
  try {
    const d = await request(path, { params })
    return {
      code: 0,
      message: 'ok',
      data: { list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 }
    }
  } catch (e) {
    return { code: e.code || 1, data: null, message: e.message || '真实接口不可用' }
  }
}

/** 真实优先：object 型返回。失败→mock；业务错误→透出 */
async function real(realFn, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try {
    const data = await realFn()
    return { code: 0, data, message: 'ok' }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    return mockFn()
  }
}

/** 真实优先：分页型返回，后端 items → 前端 list 映射 */
async function realList(path, params, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try {
    const d = await request(path, { params })
    return { code: 0, message: 'ok',
      data: { list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 } }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    return mockFn()
  }
}

export const internshipApi = {
  /** 品牌 / 角色 / 数据范围 / 权限动作 / 字典（页面初始化统一获取，走 mock 上下文） */
  getContext() {
    return ok({
      tenantBrandConfig: { ...tenantBrandConfig },
      currentRole: { ...currentRole },
      dataScope: { ...dataScope },
      permissionActions: JSON.parse(JSON.stringify(permissionActions)),
      statusOptions: JSON.parse(JSON.stringify(statusOptions))
    })
  },

  getDashboardSummary() {
    return real(() => request('/internship/dashboard'),
      () => ok(JSON.parse(JSON.stringify(dashboardSummary))))
  },

  // ═══════════ 实习批次（生产级：仅真实后端，不回退 mock）═══════════
  getBatches(params = {}) {
    return realListStrict('/internship/batches', params)
  },

  getBatchDetail(id) {
    return realStrict(() => request(`/internship/batches/${id}`))
  },

  createBatch(body) {
    return realStrict(() => request('/internship/batches', { method: 'POST', body }))
  },

  updateBatch(id, body) {
    return realStrict(() => request(`/internship/batches/${id}`, { method: 'PUT', body }))
  },

  activateBatch(id) {
    return realStrict(() => request(`/internship/batches/${id}/activate`, { method: 'POST' }))
  },

  closeBatch(id) {
    return realStrict(() => request(`/internship/batches/${id}/close`, { method: 'POST' }))
  },

  archiveBatch(id) {
    return realStrict(() => request(`/internship/batches/${id}/archive`, { method: 'POST' }))
  },

  voidBatch(id, reason) {
    return realStrict(() => request(`/internship/batches/${id}/void`, { method: 'POST', body: { reason } }))
  },

  exportBatches(params = {}) {
    return realStrict(() => request('/internship/batches/export', { method: 'POST', params }))
  },

  async downloadBatchExport(params = {}) {
    const res = await this.exportBatches(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '实习批次台账.xlsx')
    return res
  },

  getStudents(params = {}) {
    return realList('/internship/students', params, () => this._mockStudents(params))
  },
  _mockStudents(params = {}) {
    let list = [...internshipStudents]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((s) => s.name.includes(kw) || s.studentNo.includes(kw) || (s.enterpriseName || '').includes(kw))
    }
    if (params.classId) list = list.filter((s) => s.classId === params.classId)
    if (params.enterpriseId) list = list.filter((s) => s.enterpriseId === params.enterpriseId)
    if (params.status) list = list.filter((s) => s.status === params.status)
    if (params.riskLevel) list = list.filter((s) => s.riskLevel === params.riskLevel)
    return ok(paginate(list, params))
  },

  getStudentDetail(id) {
    return real(() => request(`/internship/students/${id}`), () => {
      const detail = studentDetailMap[id]
      if (!detail) return fail('未找到该学生的实习档案，或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  getAttendanceExceptions(params = {}) {
    return realList('/internship/exceptions', params, () => this._mockExceptions(params))
  },
  _mockExceptions(params = {}) {
    let list = [...attendanceExceptions]
    if (params.type) list = list.filter((e) => e.type === params.type)
    if (params.status) list = list.filter((e) => e.status === params.status)
    if (params.keyword) list = list.filter((e) => e.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  getAttendanceExceptionDetail(id) {
    return real(() => request(`/internship/exceptions/${id}`), () => {
      const detail = attendanceExceptionDetailMap[id]
      if (!detail) return fail('异常记录不存在或已被处理归档')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  handleAttendanceException(id, { action, comment }) {
    return real(
      () => request(`/internship/exceptions/${id}/handle`, { method: 'POST', body: { action, comment } }),
      () => this._mockHandleException(id, { action, comment })
    )
  },
  _mockHandleException(id, { action, comment }) {
    if (!comment || comment.trim().length < 5) return fail('处理意见必填且不少于 5 个字')
    const row = attendanceExceptions.find((e) => e.id === id)
    const detail = attendanceExceptionDetailMap[id]
    if (!row || !detail) return fail('异常记录不存在')
    const label = { REASONABLE: '已标记合理', ABNORMAL: '已记为异常', TO_RISK: '已转风险' }[action]
    if (!label) return fail('非法处理动作')
    row.status = 'COMPLETED'
    row.statusLabel = label
    detail.status = 'COMPLETED'
    detail.trail.push({
      title: currentRole.userName + ' · ' + label,
      desc: '处理意见：' + comment.trim() + '（已同步学生端打卡状态）',
      time: '刚刚',
      tone: action === 'REASONABLE' ? 'success' : 'danger'
    })
    return ok({ id, status: 'COMPLETED', statusLabel: label })
  },

  getWeeklyReports(params = {}) {
    return realList('/internship/reports', params, () => this._mockReports(params))
  },
  _mockReports(params = {}) {
    let list = [...weeklyReports]
    if (params.status) list = list.filter((r) => r.status === params.status)
    if (params.keyword) list = list.filter((r) => r.studentName.includes(params.keyword.trim()))
    return ok(paginate(list, params))
  },

  getWeeklyReportDetail(id) {
    return real(() => request(`/internship/reports/${id}`), () => {
      const detail = weeklyReportDetailMap[id]
      if (!detail) return fail('周报不存在或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  reviewWeeklyReport(id, { action, comment }) {
    return real(
      () => request(`/internship/reports/${id}/review`, { method: 'POST', body: { action, comment } }),
      () => this._mockReviewReport(id, { action, comment })
    )
  },
  _mockReviewReport(id, { action, comment }) {
    if (action === 'RETURN' && (!comment || comment.trim().length < 5)) {
      return fail('退回原因必填且不少于 5 个字')
    }
    const row = weeklyReports.find((r) => r.id === id)
    const detail = weeklyReportDetailMap[id]
    if (!row || !detail) return fail('周报不存在')
    const next = action === 'APPROVE' ? { status: 'APPROVED', label: '已通过' } : { status: 'RETURNED', label: '已退回' }
    row.status = next.status
    row.statusLabel = next.label
    detail.status = next.status
    detail.trail.push({
      who: currentRole.userName,
      time: '刚刚',
      action: (action === 'APPROVE' ? '通过 ' : '退回 ') + detail.version,
      affected: (comment ? (action === 'APPROVE' ? '评语：' : '退回原因：') + comment.trim() + '；' : '') + '结果已同步学生端（P12）'
    })
    return ok({ id, status: next.status, statusLabel: next.label })
  },

  getRiskStudents(params = {}) {
    return realList('/internship/risks', params, () => this._mockRisks(params))
  },
  _mockRisks(params = {}) {
    let list = [...riskStudents]
    if (params.level) list = list.filter((r) => r.level === params.level)
    if (params.status) list = list.filter((r) => r.status === params.status)
    return ok(paginate(list, params))
  },

  // ═══════════ 企业库（生产级：仅真实后端，不回退 mock）═══════════
  getEnterprises(params = {}) {
    return realListStrict('/internship/enterprises', params)
  },

  getEnterpriseDetail(id) {
    return realStrict(() => request(`/internship/enterprises/${id}`))
  },

  createEnterprise(body) {
    return realStrict(() => request('/internship/enterprises', { method: 'POST', body }))
  },

  updateEnterprise(id, body) {
    return realStrict(() => request(`/internship/enterprises/${id}`, { method: 'PUT', body }))
  },

  reviewEnterprise(id, { action, comment }) {
    return realStrict(() => request(`/internship/enterprises/${id}/review`, { method: 'POST', body: { action, comment } }))
  },

  setEnterpriseCooperation(id, { action, reason }) {
    return realStrict(() => request(`/internship/enterprises/${id}/cooperation`, { method: 'POST', body: { action, reason } }))
  },

  setEnterpriseBlacklist(id, { on, reason }) {
    return realStrict(() => request(`/internship/enterprises/${id}/blacklist`, { method: 'POST', body: { on, reason } }))
  },

  getEnterpriseContacts(id) {
    return realStrict(() => request(`/internship/enterprises/${id}/contacts`).then((d) => ({ items: d.items || [] })))
  },

  addEnterpriseContact(id, body) {
    return realStrict(() => request(`/internship/enterprises/${id}/contacts`, { method: 'POST', body }))
  },

  updateEnterpriseContact(id, contactId, body) {
    return realStrict(() => request(`/internship/enterprises/${id}/contacts/${contactId}`, { method: 'PUT', body }))
  },

  deleteEnterpriseContact(id, contactId) {
    return realStrict(() => request(`/internship/enterprises/${id}/contacts/${contactId}`, { method: 'DELETE' }))
  },

  getEnterpriseStats() {
    return realStrict(() => request('/internship/enterprises/stats'))
  },

  importEnterprisesDryRun(rows) {
    return realStrict(() => request('/internship/enterprises/import/dry-run', { method: 'POST', body: { rows } }))
  },

  importEnterprisesConfirm(rows) {
    return realStrict(() => request('/internship/enterprises/import/confirm', { method: 'POST', body: { rows } }))
  },

  exportEnterprises(params = {}) {
    return realStrict(() => request('/internship/enterprises/export', { method: 'POST', params }))
  },

  downloadEnterpriseImportErrors(rows, errors) {
    return realStrict(() => request('/internship/enterprises/import/errors-xlsx', {
      method: 'POST', body: { rows, errors }
    }))
  },

  async downloadEnterpriseExport(params = {}) {
    const res = await this.exportEnterprises(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '企业库台账.xlsx')
    return res
  },

  /** 上传 Excel(.xlsx) 解析+预校验，返回 { rows, validRows, invalidRows, errors } */
  async importEnterprisesXlsx(file) {
    try {
      return { code: 0, data: await requestUpload('/internship/enterprises/import/xlsx', file), message: 'ok' }
    } catch (e) {
      return { code: e.code || 1, data: null, message: e.message || '上传失败' }
    }
  },

  /** 下载企业导入 Excel 模板(.xlsx) */
  async downloadEnterpriseTemplate() {
    const blob = await requestBlob('/internship/enterprises/import/template')
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = '企业导入模板.xlsx'
    a.click()
    URL.revokeObjectURL(url)
  }
}

export default internshipApi
