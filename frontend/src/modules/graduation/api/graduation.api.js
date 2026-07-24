/**
 * 毕业设计中心 API（生产路径：callStrict / listStrict，仅真实后端）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/graduation/*；失败透出业务码或 503001，不回退 mock 业务数据。
 * getContext：品牌壳可显示；permissionReady=false 时写按钮禁用，不得用静态 mock 冒充权限成功。
 */
import { request, shouldTryReal, currentUserFromToken } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { setPermissionPatterns } from '@/security/permissionGate'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions
} from '@/mocks/graduation/graduation.mock'

function ok(data) {
  return Promise.resolve({ code: 0, data, message: 'ok' })
}

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

function denyAllActions(pa, reason) {
  Object.keys(pa).forEach((k) => {
    pa[k] = { ...pa[k], allowed: false, reason }
  })
}

export const graduationApi = {
  /**
   * 上下文：权限动作以后端 GET /graduation/context 为准；
   * 同时拉取 /rbac/current-context 的 permissionPatterns 供侧栏投影。
   * 真实权限失败时 permissionReady=false，全部写动作禁用。
   */
  async getContext() {
    const u = currentUserFromToken()
    const isTeacher = u && u.userType === 'TEACHER'
    const pa = JSON.parse(JSON.stringify(permissionActions))
    // 默认 fail-closed：在真实权限加载成功前全部禁止写
    denyAllActions(pa, '权限上下文加载中，写操作暂不可用')

    let scopeName = isTeacher ? '本人指导学生' : '本校毕设数据（按后端数据范围）'
    let scopeHint = ''
    let orgScope = {
      roleNeedsOrgScope: false,
      scopeConfigured: true,
      collegeId: null,
      majorId: null
    }
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
            const cr = rc.currentRole || {}
            if (cr.roleName) roleName = cr.roleName
            const tid = me?.tenantId || me?.user?.tenantId || ''
            ctxKey = `${tid}|${cr.contextId || ''}|${cr.permissionVersion || ''}`
          }
        } catch {
          /* rbac 不可达时继续尝试 graduation/context */
        }
        if (realName) roleName = `${realName} · ${roleName}`
      }
    } catch {
      /* 离线场景保留品牌壳 */
    }

    setPermissionPatterns(permissionPatterns)

    try {
      if (shouldTryReal()) {
        const ctx = await request('/graduation/context')
        if (ctx && ctx.permissionActions) {
          Object.keys(pa).forEach((key) => {
            if (key in ctx.permissionActions) {
              const allowed = !!ctx.permissionActions[key] && !readonlyTenant
              pa[key] = {
                ...pa[key],
                allowed,
                reason: allowed
                  ? ''
                  : (readonlyTenant
                    ? '当前环境为只读，不可修改'
                    : (pa[key].reason || '当前角色无该操作权限'))
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
    } catch (e) {
      permissionReady = false
      permissionError = e?.message || '毕业设计权限上下文不可用'
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
    return callStrict(() => request('/graduation/dashboard', { params }))
  },

  getStudents(params = {}) {
    return listStrict('/graduation/students', params)
  },

  getStudentDetail(id) {
    return callStrict(() => request(`/graduation/students/${id}`))
  },

  getTopics(params = {}) {
    return listStrict('/graduation/gd-topics', { ...params, archiveView: params.archiveView || 'active' })
  },

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

  exportProposals(params = {}) {
    const p = typeof params === 'string' ? { status: params } : (params || {})
    return callStrict(() => request('/graduation/proposals/export', { method: 'POST', params: p }))
  },

  async downloadProposalsExport(params = {}) {
    const res = await this.exportProposals(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, res.data?.filename || '开题材料台账.xlsx')
    return res
  },

  getFinalSubmissions(params = {}) {
    return listStrict('/graduation/finals', params)
  },

  reviewFinal(id, { action, comment }) {
    return callStrict(() => request(`/graduation/finals/${id}/review`, { method: 'POST', body: { action, comment } }))
  },

  remindFinal(gdStudentId, channel = '站内消息') {
    return callStrict(() => request('/graduation/finals/remind', { method: 'POST', body: { gdStudentId, channel } }))
  },

  exportFinals(params = {}) {
    const p = typeof params === 'string' ? { status: params } : (params || {})
    return callStrict(() => request('/graduation/finals/export', { method: 'POST', params: p }))
  },

  async downloadFinalsExport(params = {}) {
    const res = await this.exportFinals(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, res.data?.filename || '成果提交台账.xlsx')
    return res
  },

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

  exportDefenseGroups(params = {}) {
    return callStrict(() => request('/graduation/defense-groups/export', { method: 'POST', params }))
  },

  async downloadDefenseExport(params = {}) {
    const res = await this.exportDefenseGroups(params)
    if (res.code === 0) downloadXlsxFromApi(res.data, res.data?.filename || '答辩安排台账.xlsx')
    return res
  },

  getAuditLogs(params = {}) {
    return listStrict('/graduation/audit-logs', params)
  }
}

export default graduationApi
