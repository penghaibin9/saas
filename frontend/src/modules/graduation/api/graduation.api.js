/**
 * 毕业设计中心 API（P7：真实优先 + mock 兜底）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/graduation/*；后端不可达时自动回退 mock，页面不白屏；业务错误透出。
 */
import { request, shouldTryReal, canUseMockFallback, currentUserFromToken } from '@/services/http/client'
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
  if (!shouldTryReal()) {
    if (canUseMockFallback()) return mockFn()
    return toErr({ code: 503001, message: '真实接口不可用，生产环境已禁用 mock fallback' })
  }
  try {
    return { code: 0, data: await realFn(), message: 'ok' }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    if (canUseMockFallback()) return mockFn()
    return toErr(e)
  }
}

async function realList(path, params, mockFn) {
  if (!shouldTryReal()) {
    if (canUseMockFallback()) return mockFn()
    return toErr({ code: 503001, message: '真实接口不可用，生产环境已禁用 mock fallback' })
  }
  try {
    const d = await request(path, { params })
    return { code: 0, message: 'ok',
      data: { list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 } }
  } catch (e) {
    if (e.biz) return { code: e.code || 1, data: null, message: e.message }
    if (canUseMockFallback()) return mockFn()
    return toErr(e)
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
  /**
   * 上下文：权限动作以后端 GET /graduation/context 的真实 permissionCode 判定为准
   * （每个按钮键映射到后端 graduation_permissions.py 同款 permissionCode，逐项 has_permission 计算）。
   * 下面的 isTeacher 粗粒度推断仅作真实接口不可达时（离线/mock）的静态兜底，不再是生产口径。
   */
  async getContext() {
    const u = currentUserFromToken()
    const isTeacher = u && u.userType === 'TEACHER'
    const pa = JSON.parse(JSON.stringify(permissionActions))
    if (isTeacher) {
      pa.reviewProposal = { visible: true, allowed: true, reason: '' }
      pa.reviewFinal = { visible: true, allowed: true, reason: '' }
      ;['createBatch', 'importStudents', 'batchAssignAdvisor', 'batchArchive', 'voidProject', 'manageDefense', 'publishDefense', 'importTopics'].forEach((k) => {
        if (pa[k]) pa[k] = { ...pa[k], allowed: false, reason: '需毕设管理员角色，教师身份仅查看' }
      })
    }
    let scopeName = isTeacher ? '本人指导学生' : '本校毕设数据（按后端数据范围）'
    // 品牌与姓名优先取真实 /auth/me（含 tenantName），后端不可达时回退 token/静态兜底，不阻塞页面
    const brand = { ...tenantBrandConfig }
    let roleName = isTeacher ? '指导教师' : currentRole.roleName
    try {
      if (shouldTryReal()) {
        const me = await request('/auth/me')
        const tenantName = me?.tenantName || me?.user?.tenantName || me?.tenant?.name
        if (tenantName) brand.schoolName = tenantName
        const realName = me?.realName || me?.user?.realName
        if (realName) roleName = `${realName} · ${roleName}`
      }
    } catch {
      /* 离线/未登录场景静默回退 */
    }
    // 真实权限上下文：后端按当前角色逐项判定每个按钮的 permissionCode，覆盖上面的粗粒度静态兜底
    try {
      if (shouldTryReal()) {
        const ctx = await request('/graduation/context')
        if (ctx && ctx.permissionActions) {
          Object.keys(pa).forEach((key) => {
            if (key in ctx.permissionActions) {
              const allowed = !!ctx.permissionActions[key]
              pa[key] = { ...pa[key], allowed, reason: allowed ? '' : (pa[key].reason || '当前角色无该操作权限') }
            }
          })
        }
        if (typeof ctx?.fullScope === 'boolean') {
          scopeName = ctx.fullScope ? '本校毕设数据（按后端数据范围）' : '本人业务范围内数据（按角色收敛）'
        }
      }
    } catch {
      /* 后端不可达时静默保留上面的粗粒度静态兜底，不阻塞页面 */
    }
    return ok({
      tenantBrandConfig: brand,
      currentRole: { ...currentRole, roleName },
      dataScope: { ...dataScope, scopeName },
      permissionActions: pa,
      statusOptions: JSON.parse(JSON.stringify(statusOptions))
    })
  },

  getDashboardSummary() {
    return callStrict(() => request('/graduation/dashboard'))
  },

  getStudents(params = {}) {
    return listStrict('/graduation/students', params)
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
    return callStrict(() => request(`/graduation/students/${id}`))
  },

  getTopics(params = {}) {
    return listStrict('/graduation/gd-topics', { ...params, archiveView: params.archiveView || 'active' })
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

  exportProposals(status) {
    return callStrict(() => request('/graduation/proposals/export', { method: 'POST', params: status ? { status } : {} }))
  },

  async downloadProposalsExport(status) {
    const res = await this.exportProposals(status)
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

  exportFinals(status) {
    return callStrict(() => request('/graduation/finals/export', { method: 'POST', params: status ? { status } : {} }))
  },

  async downloadFinalsExport(status) {
    const res = await this.exportFinals(status)
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

  exportDefenseGroups() {
    return callStrict(() => request('/graduation/defense-groups/export', { method: 'POST' }))
  },

  async downloadDefenseExport() {
    const res = await this.exportDefenseGroups()
    if (res.code === 0) downloadXlsxFromApi(res.data, '答辩安排台账.xlsx')
    return res
  },

  getAuditLogs(params = {}) {
    return listStrict('/graduation/audit-logs', params)
  }
}

export default graduationApi
