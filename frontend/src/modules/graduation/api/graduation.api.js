/**
 * 毕业设计中心 API（仅真实后端）。
 * 学校端业务请求统一绑定当前毕业设计批次；旧链接或缓存对象跨批时由后端 409 拒绝。
 */
import { request, shouldTryReal, currentUserFromToken } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { setPermissionPatterns } from '@/security/permissionGate'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions
} from '@/mocks/graduation/graduation.mock'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function toErr(e) {
  if (e?.biz) return { code: e.code || 1, data: null, message: e.message }
  return { code: 503001, data: null, message: e?.message || '真实接口不可用' }
}
async function callStrict(fn) {
  try { return { code: 0, data: await fn(), message: 'ok' } } catch (e) { return toErr(e) }
}
function withBatch(params = {}, required = true) {
  const store = useGraduationBatchStore()
  const batchId = params.batchId || store.selectedBatchId
  if (required && !batchId) throw new Error('请先选择毕业设计批次')
  return batchId ? { ...params, batchId: String(batchId) } : { ...params }
}
async function listStrict(path, params = {}, required = true) {
  try {
    const d = await request(path, { params: withBatch(params, required) })
    return { code: 0, message: 'ok',
      data: { list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 } }
  } catch (e) { return toErr(e) }
}
function denyAllActions(pa, reason) {
  Object.keys(pa).forEach((key) => { pa[key] = { ...pa[key], allowed: false, reason } })
}

export const graduationApi = {
  async getContext() {
    const user = currentUserFromToken()
    const isTeacher = user && user.userType === 'TEACHER'
    const pa = JSON.parse(JSON.stringify(permissionActions))
    denyAllActions(pa, '权限上下文加载中，写操作暂不可用')

    let scopeName = isTeacher ? '本人指导学生' : '本校毕设数据（按后端数据范围）'
    let scopeHint = ''
    let orgScope = { roleNeedsOrgScope: false, scopeConfigured: true, collegeId: null, majorId: null }
    const brand = { ...tenantBrandConfig }
    let roleName = isTeacher ? '指导教师' : currentRole.roleName
    let permissionPatterns = null
    let ctxKey = ''
    let permissionReady = false
    let permissionError = ''
    let readonlyTenant = false

    try {
      if (shouldTryReal()) {
        const me = await request('/auth/me')
        const tenantName = me?.tenantName || me?.user?.tenantName || me?.tenant?.name
        if (tenantName) brand.schoolName = tenantName
        const realName = me?.realName || me?.user?.realName
        try {
          const rc = await request('/rbac/current-context')
          if (rc && Array.isArray(rc.permissionPatterns)) {
            permissionPatterns = rc.permissionPatterns
            readonlyTenant = !!rc.readonlyTenant
            const role = rc.currentRole || {}
            if (role.roleName) roleName = role.roleName
            const tenantId = me?.tenantId || me?.user?.tenantId || ''
            ctxKey = `${tenantId}|${role.contextId || ''}|${role.permissionVersion || ''}`
          }
        } catch { /* 继续尝试毕业设计上下文 */ }
        if (realName) roleName = `${realName} · ${roleName}`
      }
    } catch { /* 品牌壳仍可展示 */ }

    setPermissionPatterns(permissionPatterns)
    try {
      if (shouldTryReal()) {
        const ctx = await request('/graduation/context')
        if (ctx && ctx.permissionActions) {
          Object.keys(pa).forEach((key) => {
            if (key in ctx.permissionActions) {
              const allowed = !!ctx.permissionActions[key] && !readonlyTenant
              pa[key] = {
                ...pa[key], allowed,
                reason: allowed ? '' : (readonlyTenant ? '当前环境为只读，不可修改' : (pa[key].reason || '当前角色无该操作权限'))
              }
            }
          })
          permissionReady = true
        } else {
          permissionError = '权限上下文缺少 permissionActions'
          denyAllActions(pa, permissionError)
        }
        if (typeof ctx?.fullScope === 'boolean') {
          scopeName = ctx.fullScope ? '本校毕设数据（按后端数据范围）' : '本人业务范围内数据（按角色收敛）'
        }
        if (ctx?.roleNeedsOrgScope && ctx.scopeConfigured === false) {
          scopeName = '未配置学院/专业数据范围（fail-closed）'
        } else if (ctx?.collegeId && !ctx.fullScope) {
          scopeName = `学院范围 collegeId=${ctx.collegeId}` + (ctx.majorId ? ` / majorId=${ctx.majorId}` : '')
        } else if (ctx?.majorId && !ctx.fullScope) {
          scopeName = `专业范围 majorId=${ctx.majorId}`
        }
        scopeHint = ctx?.scopeHint || ''
        orgScope = {
          roleNeedsOrgScope: !!ctx?.roleNeedsOrgScope,
          scopeConfigured: ctx?.scopeConfigured !== false,
          collegeId: ctx?.collegeId || null,
          majorId: ctx?.majorId || null
        }
      } else {
        permissionError = '未启用真实接口，写操作已禁用'
        denyAllActions(pa, permissionError)
      }
    } catch (error) {
      permissionReady = false
      permissionError = error?.message || '毕业设计权限上下文不可用'
      denyAllActions(pa, permissionError)
    }

    return ok({
      tenantBrandConfig: brand,
      currentRole: { ...currentRole, roleName },
      dataScope: { ...dataScope, scopeName },
      permissionActions: pa,
      permissionPatterns,
      ctxKey,
      permissionReady,
      permissionError,
      readonlyTenant,
      statusOptions: JSON.parse(JSON.stringify(statusOptions)),
      scopeHint,
      ...orgScope
    })
  },

  getDashboardSummary(params = {}) {
    return callStrict(() => request('/graduation/dashboard', { params: withBatch(params) }))
  },
  getStudents(params = {}) { return listStrict('/graduation/students', params) },
  getStudentDetail(id, params = {}) {
    return callStrict(() => request(`/graduation/students/${id}`, { params: withBatch(params) }))
  },
  getTopics(params = {}) {
    return listStrict('/graduation/gd-topics', withBatch({ ...params, archiveView: params.archiveView || 'active' }))
  },

  getProposals(params = {}) { return listStrict('/graduation/proposals', params) },
  getProposalReviewDetail(id, params = {}) {
    return callStrict(() => request(`/graduation/proposals/${id}`, { params: withBatch(params) }))
  },
  reviewProposal(id, { action, comment }) {
    return callStrict(() => request(`/graduation/proposals/${id}/review`, {
      method: 'POST', params: withBatch(), body: { action, comment }
    }))
  },
  holdProposalDefense(id, { result, comment }) {
    return callStrict(() => request(`/graduation/proposals/${id}/defense`, {
      method: 'POST', params: withBatch(), body: { result, comment }
    }))
  },
  remindProposal(gdStudentId, channel = '站内消息') {
    return callStrict(() => request('/graduation/proposals/remind', {
      method: 'POST', params: withBatch(), body: { gdStudentId, channel }
    }))
  },
  exportProposals(params = {}) {
    const value = typeof params === 'string' ? { status: params } : (params || {})
    return callStrict(() => request('/graduation/proposals/export', { method: 'POST', params: withBatch(value) }))
  },
  async downloadProposalsExport(params = {}) {
    const res = await this.exportProposals(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, res.data?.filename || '开题材料台账.xlsx')
    return res
  },

  getFinalSubmissions(params = {}) { return listStrict('/graduation/finals', params) },
  getFinalDetail(id, params = {}) {
    return callStrict(() => request(`/graduation/finals/${id}`, { params: withBatch(params) }))
  },
  reviewFinal(id, { action, comment }) {
    return callStrict(() => request(`/graduation/finals/${id}/review`, {
      method: 'POST', params: withBatch(), body: { action, comment }
    }))
  },
  remindFinal(gdStudentId, channel = '站内消息') {
    return callStrict(() => request('/graduation/finals/remind', {
      method: 'POST', params: withBatch(), body: { gdStudentId, channel }
    }))
  },
  exportFinals(params = {}) {
    const value = typeof params === 'string' ? { status: params } : (params || {})
    return callStrict(() => request('/graduation/finals/export', { method: 'POST', params: withBatch(value) }))
  },
  async downloadFinalsExport(params = {}) {
    const res = await this.exportFinals(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, res.data?.filename || '成果提交台账.xlsx')
    return res
  },

  getDefenseSchedules(params = {}) { return listStrict('/graduation/defense-groups', params) },
  getDefenseGroupDetail(id, params = {}) {
    return callStrict(() => request(`/graduation/defense-groups/${id}`, { params: withBatch(params) }))
  },
  createDefenseGroup(body) {
    return callStrict(() => request('/graduation/defense-groups', {
      method: 'POST', params: withBatch(), body: { ...body, batchId: Number(withBatch().batchId) }
    }))
  },
  updateDefenseGroup(id, body) {
    return callStrict(() => request(`/graduation/defense-groups/${id}`, {
      method: 'PUT', params: withBatch(), body
    }))
  },
  async getDefenseEligibleStudents(gid, keyword) {
    try {
      const data = await request('/graduation/defense-groups/eligible-students', {
        params: withBatch({ gid, keyword })
      })
      return { code: 0, data: { list: Array.isArray(data) ? data : (data?.items || []), total: Array.isArray(data) ? data.length : (data?.total || 0) }, message: 'ok' }
    } catch (error) { return toErr(error) }
  },
  assignDefenseStudents(id, studentIds) {
    return callStrict(() => request(`/graduation/defense-groups/${id}/assign`, {
      method: 'POST', params: withBatch(), body: { studentIds }
    }))
  },
  unassignDefenseStudents(id, studentIds) {
    return callStrict(() => request(`/graduation/defense-groups/${id}/unassign`, {
      method: 'POST', params: withBatch(), body: { studentIds }
    }))
  },
  publishDefenseSchedule(id) {
    return callStrict(() => request(`/graduation/defense-groups/${id}/publish`, {
      method: 'POST', params: withBatch(), body: {}
    }))
  },
  notifyDefenseSchedule(id) {
    return callStrict(() => request(`/graduation/defense-groups/${id}/notify`, {
      method: 'POST', params: withBatch(), body: {}
    }))
  },
  exportDefenseGroups(params = {}) {
    return callStrict(() => request('/graduation/defense-groups/export', {
      method: 'POST', params: withBatch(params)
    }))
  },
  async downloadDefenseExport(params = {}) {
    const res = await this.exportDefenseGroups(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, res.data?.filename || '答辩安排台账.xlsx')
    return res
  },

  getAuditLogs(params = {}) { return listStrict('/graduation/audit-logs', params) }
}

export default graduationApi
