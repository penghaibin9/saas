/**
 * 岗位实习中心 API（生产级：仅走真实后端，不回退 mock）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/internship/*；字典/权限动作仍从静态配置加载，品牌/角色/范围在线时由 enrichContext 合入。
 */
import { request, requestUpload, requestBlob, shouldTryReal } from '@/services/http/client'
import { enrichContext } from '@/services/http/adapters'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions
} from '@/mocks/internship/internship.mock'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message, code = 1) {
  return Promise.resolve({ code, data: null, message })
}

function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (e) {
    return toErr(e)
  }
}

async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) {
    return toErr(e)
  }
}

function clone(v) {
  return JSON.parse(JSON.stringify(v))
}

export const internshipApi = {
  /** 品牌 / 角色 / 数据范围 / 权限动作 / 字典（布局初始化）；后端在线时合入真实品牌/角色/范围 */
  getContext() {
    return ok({
      tenantBrandConfig: clone(tenantBrandConfig),
      currentRole: clone(currentRole),
      dataScope: clone(dataScope),
      permissionActions: clone(permissionActions),
      statusOptions: clone(statusOptions)
    }).then((res) => {
      if (!shouldTryReal()) return res
      return enrichContext(res).catch(() => res)
    })
  },

  getDashboardSummary() {
    return call(() => request('/internship/dashboard'))
  },

  getBatches(params = {}) {
    return callList('/internship/batches', params)
  },

  getBatchDetail(id) {
    return call(() => request(`/internship/batches/${id}`))
  },

  createBatch(body) {
    return call(() => request('/internship/batches', { method: 'POST', body }))
  },

  updateBatch(id, body) {
    return call(() => request(`/internship/batches/${id}`, { method: 'PUT', body }))
  },

  activateBatch(id) {
    return call(() => request(`/internship/batches/${id}/activate`, { method: 'POST' }))
  },

  closeBatch(id) {
    return call(() => request(`/internship/batches/${id}/close`, { method: 'POST' }))
  },

  archiveBatch(id) {
    return call(() => request(`/internship/batches/${id}/archive`, { method: 'POST' }))
  },

  voidBatch(id, reason) {
    return call(() => request(`/internship/batches/${id}/void`, { method: 'POST', body: { reason } }))
  },

  exportBatches(params = {}) {
    return call(() => request('/internship/batches/export', { method: 'POST', params }))
  },

  async downloadBatchExport(params = {}) {
    const res = await this.exportBatches(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '实习批次台账.xlsx')
    return res
  },

  getStudents(params = {}) {
    return callList('/internship/students', params)
  },

  getStudentDetail(id) {
    return call(() => request(`/internship/students/${id}`))
  },

  getAttendanceExceptions(params = {}) {
    return callList('/internship/exceptions', params)
  },

  getAttendanceExceptionDetail(id) {
    return call(() => request(`/internship/exceptions/${id}`))
  },

  handleAttendanceException(id, { action, comment }) {
    return call(() => request(`/internship/exceptions/${id}/handle`, { method: 'POST', body: { action, comment } }))
  },

  getWeeklyReports(params = {}) {
    return callList('/internship/reports', params)
  },

  getWeeklyReportDetail(id) {
    return call(() => request(`/internship/reports/${id}`))
  },

  reviewWeeklyReport(id, { action, comment }) {
    return call(() => request(`/internship/reports/${id}/review`, { method: 'POST', body: { action, comment } }))
  },

  exportWeeklyReports(params = {}) {
    return call(() => request('/internship/reports/export', { method: 'POST', params }))
  },

  batchReviewWeeklyReports(ids, { action = 'APPROVE', comment = '' } = {}) {
    return call(() => request('/internship/reports/batch-review', {
      method: 'POST', body: { ids, action, comment }
    }))
  },

  remindWeeklyReport(id, { channel = '站内消息' } = {}) {
    return call(() => request(`/internship/reports/${id}/remind`, {
      method: 'POST', body: { channel }
    }))
  },

  getProcessReports(params = {}) {
    return callList('/internship/process-reports', params)
  },

  getProcessReportDetail(id) {
    return call(() => request(`/internship/process-reports/${id}`))
  },

  reviewProcessReport(id, { action, comment }) {
    return call(() => request(`/internship/process-reports/${id}/review`, {
      method: 'POST', body: { action, comment }
    }))
  },

  exportProcessReports(params = {}) {
    return call(() => request('/internship/process-reports/export', { method: 'POST', params }))
  },

  getChangeRequests(params = {}) {
    return callList('/internship/change-requests', params)
  },

  getChangeRequestDetail(id) {
    return call(() => request(`/internship/change-requests/${id}`))
  },

  reviewChangeRequest(id, { action, comment }) {
    const mapped = action === 'APPROVE' ? 'APPROVE' : 'RETURN'
    return call(() => request(`/internship/change-requests/${id}/review`, {
      method: 'POST', body: { action: mapped, comment }
    }))
  },

  getRiskStudents(params = {}) {
    return callList('/internship/risks', params)
  },

  getEnterprises(params = {}) {
    return callList('/internship/enterprises', params)
  },

  getEnterpriseDetail(id) {
    return call(() => request(`/internship/enterprises/${id}`))
  },

  createEnterprise(body) {
    return call(() => request('/internship/enterprises', { method: 'POST', body }))
  },

  updateEnterprise(id, body) {
    return call(() => request(`/internship/enterprises/${id}`, { method: 'PUT', body }))
  },

  reviewEnterprise(id, { action, comment }) {
    return call(() => request(`/internship/enterprises/${id}/review`, { method: 'POST', body: { action, comment } }))
  },

  setEnterpriseCooperation(id, { action, reason }) {
    return call(() => request(`/internship/enterprises/${id}/cooperation`, { method: 'POST', body: { action, reason } }))
  },

  setEnterpriseBlacklist(id, { on, reason }) {
    return call(() => request(`/internship/enterprises/${id}/blacklist`, { method: 'POST', body: { on, reason } }))
  },

  getEnterpriseContacts(id) {
    return call(() => request(`/internship/enterprises/${id}/contacts`).then((d) => ({ items: d.items || [] })))
  },

  addEnterpriseContact(id, body) {
    return call(() => request(`/internship/enterprises/${id}/contacts`, { method: 'POST', body }))
  },

  updateEnterpriseContact(id, contactId, body) {
    return call(() => request(`/internship/enterprises/${id}/contacts/${contactId}`, { method: 'PUT', body }))
  },

  deleteEnterpriseContact(id, contactId) {
    return call(() => request(`/internship/enterprises/${id}/contacts/${contactId}`, { method: 'DELETE' }))
  },

  getEnterpriseStats() {
    return call(() => request('/internship/enterprises/stats'))
  },

  importEnterprisesDryRun(rows) {
    return call(() => request('/internship/enterprises/import/dry-run', { method: 'POST', body: { rows } }))
  },

  importEnterprisesConfirm(rows) {
    return call(() => request('/internship/enterprises/import/confirm', { method: 'POST', body: { rows } }))
  },

  exportEnterprises(params = {}) {
    return call(() => request('/internship/enterprises/export', { method: 'POST', params }))
  },

  downloadEnterpriseImportErrors(rows, errors) {
    return call(() => request('/internship/enterprises/import/errors-xlsx', {
      method: 'POST', body: { rows, errors }
    }))
  },

  async downloadEnterpriseExport(params = {}) {
    const res = await this.exportEnterprises(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, '企业库台账.xlsx')
    return res
  },

  async importEnterprisesXlsx(file) {
    try {
      return ok(await requestUpload('/internship/enterprises/import/xlsx', file))
    } catch (e) {
      return toErr(e)
    }
  },

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
