/**
 * 毕业设计中心 API（P7：真实优先 + mock 兜底）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/graduation/*；后端不可达时自动回退 mock，页面不白屏；业务错误透出。
 */
import { request, shouldTryReal } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions,
  graduationStudents,
  studentDetailMap,
  topicList
} from '@/mocks/graduation/graduation.mock'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: list.slice(start, start + pageSize), total, page, pageSize }
}

async function real(realFn, mockFn) {
  if (!shouldTryReal()) return mockFn()
  try {
    return { code: 0, data: await realFn(), message: 'ok' }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    return mockFn()
  }
}

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

// 生产级 realStrict：仅走真实后端，不回退 mock（开题材料模块已收口）
function toErr(e) {
  if (e?.biz) return { code: e.code || 1, data: null, message: e.message }
  return { code: 503001, data: null, message: e?.message || '真实接口不可用' }
}
async function callStrict(fn) {
  try { return { code: 0, data: await fn(), message: 'ok' } } catch (e) { return toErr(e) }
}
async function listStrict(path, params = {}) {
  try {
    const d = await request(path, { params })
    return { code: 0, message: 'ok',
      data: { list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 } }
  } catch (e) { return toErr(e) }
}

export const graduationApi = {
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
    return callStrict(() => request('/graduation/dashboard'))
  },

  getStudents(params = {}) {
    return realList('/graduation/students', params, () => this._mockStudents(params))
  },
  _mockStudents(params = {}) {
    let list = [...graduationStudents]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((s) => s.name.includes(kw) || s.studentNo.includes(kw) || s.topicTitle.includes(kw))
    }
    if (params.classId) list = list.filter((s) => s.classId === params.classId)
    if (params.advisorId) list = list.filter((s) => s.advisorId === params.advisorId)
    if (params.stage) list = list.filter((s) => s.stage === params.stage)
    if (params.riskLevel) list = list.filter((s) => s.riskLevel === params.riskLevel)
    return ok(paginate(list, params))
  },

  getStudentDetail(id) {
    return real(() => request(`/graduation/students/${id}`), () => {
      const detail = studentDetailMap[id]
      if (!detail) return fail('未找到该学生的毕设档案，或不在当前数据范围内')
      return ok(JSON.parse(JSON.stringify(detail)))
    })
  },

  getTopics(params = {}) {
    return realList('/graduation/gd-topics', { ...params, archiveView: params.archiveView || 'active' }, () => {
      let list = [...topicList]
      if (params.keyword) list = list.filter((t) => t.title.includes(params.keyword.trim()))
      if (params.status) list = list.filter((t) => t.status === params.status)
      return ok(paginate(list, params))
    })
  },

  // ── 开题材料（realStrict：仅真实后端，不 mock 冒充）──
  getProposals(params = {}) {
    return listStrict('/graduation/proposals', params)
  },

  getProposalReviewDetail(id) {
    return callStrict(() => request(`/graduation/proposals/${id}`))
  },

  reviewProposal(id, { action, comment }) {
    return callStrict(() => request(`/graduation/proposals/${id}/review`, { method: 'POST', body: { action, comment } }))
  },

  remindProposal(gdStudentId, channel = '站内消息') {
    return callStrict(() => request('/graduation/proposals/remind', { method: 'POST', body: { gdStudentId, channel } }))
  },

  async downloadProposalsExport(status) {
    const res = await callStrict(() => request('/graduation/proposals/export', { method: 'POST', params: status ? { status } : {} }))
    if (res.code === 0) downloadXlsxFromApi(res.data, '开题材料台账.xlsx')
    return res
  },

  // ── 成果提交（realStrict：仅真实后端，不 mock 冒充）──
  getFinalSubmissions(params = {}) {
    return listStrict('/graduation/finals', params)
  },

  reviewFinal(id, { action, comment }) {
    return callStrict(() => request(`/graduation/finals/${id}/review`, { method: 'POST', body: { action, comment } }))
  },

  remindFinal(gdStudentId, channel = '站内消息') {
    return callStrict(() => request('/graduation/finals/remind', { method: 'POST', body: { gdStudentId, channel } }))
  },

  async downloadFinalsExport(status) {
    const res = await callStrict(() => request('/graduation/finals/export', { method: 'POST', params: status ? { status } : {} }))
    if (res.code === 0) downloadXlsxFromApi(res.data, '成果提交台账.xlsx')
    return res
  },

  // ── 答辩安排（realStrict：仅真实后端，不 mock 冒充）──
  getDefenseSchedules(params = {}) {
    return listStrict('/graduation/defense-groups', params)
  },

  getDefenseGroupDetail(id) {
    return callStrict(() => request(`/graduation/defense-groups/${id}`))
  },

  createDefenseGroup(body) {
    return callStrict(() => request('/graduation/defense-groups', { method: 'POST', body }))
  },

  updateDefenseGroup(id, body) {
    return callStrict(() => request(`/graduation/defense-groups/${id}`, { method: 'PUT', body }))
  },

  getDefenseEligibleStudents(gid, keyword) {
    return listStrict('/graduation/defense-groups/eligible-students', { gid, keyword })
  },

  assignDefenseStudents(id, studentIds) {
    return callStrict(() => request(`/graduation/defense-groups/${id}/assign`, { method: 'POST', body: { studentIds } }))
  },

  unassignDefenseStudents(id, studentIds) {
    return callStrict(() => request(`/graduation/defense-groups/${id}/unassign`, { method: 'POST', body: { studentIds } }))
  },

  publishDefenseSchedule(id) {
    return callStrict(() => request(`/graduation/defense-groups/${id}/publish`, { method: 'POST', body: {} }))
  },

  async downloadDefenseExport() {
    const res = await callStrict(() => request('/graduation/defense-groups/export', { method: 'POST' }))
    if (res.code === 0) downloadXlsxFromApi(res.data, '答辩安排台账.xlsx')
    return res
  }
}

export default graduationApi
