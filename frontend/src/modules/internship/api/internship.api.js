/**
 * 岗位实习中心 API（生产级：仅走真实后端，不回退 mock）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；方法签名冻结不变。
 * 真实接口 /api/v1/internship/*；字典/权限动作从静态配置加载，角色/范围由 JWT 身份推导（见 getContext），品牌取 /auth/me。
 */
import { request, requestUpload, requestBlob, shouldTryReal, currentUserFromToken } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  ACTION_PERMISSION_CODES,
  ACTION_DENY_REASONS,
  statusOptions
} from '@/modules/internship/constants/context.constants'
import { allowByPatterns, isWriteCode } from '@/modules/internship/composables/permission'
import {
  setPermissionPatterns,
  setModuleEntitlements,
  setModuleAccessHealth,
  setRbacLoadFailed
} from '@/security/permissionGate'

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
  async getContext() {
    // 角色名/范围名仅用于展示；细粒度按钮 allowed 由后端 permissionPatterns 判定（见下），
    // 不再用 userType==='TEACHER' 二分猜角色。真实越权拦截始终以后端接口为准。
    const u = currentUserFromToken()
    const isTeacher = !!(u && u.userType === 'TEACHER')
    let roleName = isTeacher ? '实习指导教师' : '实习管理员'
    const scopeName = isTeacher ? '本人指导的实习学生' : '本校实习数据（按后端数据范围）'
    const brand = { ...tenantBrandConfig }
    // permissionPatterns：当前身份的权限码模式集，来自后端 /rbac/current-context（与 enforce_permission 同一套码）。
    // 角色菜单投影(getVisibleNavPlan/canSeeLeaf)与按钮态(permissionActions)据此收敛；取不到时降级（离线/兼容）。
    let permissionPatterns = null
    let roleCtx = { ...currentRole, roleName }
    let ctxKey = ''
    // BUG-001：只读演示租户由后端下发，前端据此禁用全部写按钮（不再「点了才 403」）
    let readonlyTenant = false
    let readonlyReason = ''
    let moduleEntitlements = null
    let moduleAccessHealthy = true
    let moduleAccessError = ''
    let permissionServiceError = ''
    try {
      if (shouldTryReal()) {
        const me = await request('/auth/me')
        const tenantName = me?.tenantName || me?.user?.tenantName || me?.tenant?.name
        if (tenantName) brand.schoolName = tenantName
        const realName = me?.realName || me?.user?.realName
        try {
          const rc = await request('/rbac/current-context')
          setRbacLoadFailed(false)
          if (rc && rc.moduleAccessHealthy === false) {
            moduleAccessHealthy = false
            moduleAccessError = rc.moduleAccessError || '模块授权计算失败'
            setModuleAccessHealth(false, moduleAccessError)
            setModuleEntitlements(null)
          } else {
            setModuleAccessHealth(true, '')
            if (Array.isArray(rc?.moduleEntitlements)) {
              moduleEntitlements = rc.moduleEntitlements
              setModuleEntitlements(moduleEntitlements)
            }
          }
          if (rc && Array.isArray(rc.permissionPatterns)) {
            permissionPatterns = rc.permissionPatterns
            readonlyTenant = !!rc.readonlyTenant
            readonlyReason = rc.readonlyReason || ''
            const cr = rc.currentRole || {}
            // 优先用后端返回的真实角色名，退回 userType 猜测名仅作离线兜底。
            if (cr.roleName) roleName = cr.roleName
            roleCtx = { ...currentRole, roleCode: cr.roleCode || roleCtx.roleCode }
            const tid = me?.tenantId || me?.user?.tenantId || ''
            ctxKey = `${tid}|${cr.contextId || ''}|${cr.permissionVersion || ''}`
          }
        } catch (e) {
          permissionServiceError = e?.message || '权限服务加载失败'
          setRbacLoadFailed(true, permissionServiceError)
          /* current-context 不可用：不得伪装成无权限；布局展示服务错误 */
        }
        if (realName) roleName = `${realName} · ${roleName}`
        roleCtx = { ...roleCtx, roleName }
      }
    } catch {
      /* 离线/未登录静默回退，不阻塞布局 */
    }
    // 落库给路由守卫消费（岗位实习路由 meta.permissionKey 拦截，见 @/security/permissionGate）
    setPermissionPatterns(permissionPatterns)
    // 细粒度按钮态：拿到真实 permissionPatterns 时逐项由后端权限码判定；取不到时走 allowByPatterns 降级
    //（开发构建放开便于联调 / 正式构建禁用，不 all-allow，符合 §8.4.3）。
    const pa = clone(permissionActions)
    const roText = readonlyReason || '正式演示环境为只读，数据不可修改。需要动手体验请用沙箱账号登录'
    Object.keys(pa).forEach((k) => {
      const code = ACTION_PERMISSION_CODES[k]
      let allowed = allowByPatterns(permissionPatterns, code)
      let reason = allowed ? '' : (ACTION_DENY_REASONS[k] || '无操作权限，请联系管理员')
      // BUG-001：只读租户下写按钮直接禁用并说明原因，与后端 403 判定同源
      if (allowed && readonlyTenant && isWriteCode(code)) {
        allowed = false
        reason = roText
      }
      pa[k] = { visible: true, allowed, reason }
    })
    return ok({
      tenantBrandConfig: brand,
      currentRole: roleCtx,
      dataScope: { ...dataScope, scopeName, name: scopeName },
      permissionActions: pa,
      permissionPatterns,
      moduleEntitlements,
      moduleAccessHealthy,
      moduleAccessError,
      permissionServiceError,
      readonlyTenant,
      readonlyReason: readonlyTenant ? roText : '',
      ctxKey,
      statusOptions: clone(statusOptions)
    })
  },

  getDashboardSummary(params = {}) {
    return call(() => request('/internship/dashboard', { params }))
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

  activateBatch(id, { expectedVersion, version } = {}) {
    return call(() => request(`/internship/batches/${id}/activate`, {
      method: 'POST', body: { expectedVersion: expectedVersion ?? version }
    }))
  },

  closeBatch(id, { expectedVersion, version } = {}) {
    return call(() => request(`/internship/batches/${id}/close`, {
      method: 'POST', body: { expectedVersion: expectedVersion ?? version }
    }))
  },

  archiveBatch(id, { expectedVersion, version } = {}) {
    return call(() => request(`/internship/batches/${id}/archive`, {
      method: 'POST', body: { expectedVersion: expectedVersion ?? version }
    }))
  },

  voidBatch(id, { reason, expectedVersion, version } = {}) {
    return call(() => request(`/internship/batches/${id}/void`, {
      method: 'POST',
      body: { reason, expectedVersion: expectedVersion ?? version }
    }))
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
    return callList('/internship/intern-students', params)
  },

  getStudentDetail(id) {
    return call(() => request(`/internship/intern-students/${id}`))
  },

  getAttendanceExceptions(params = {}) {
    return callList('/internship/exceptions', params)
  },

  getAttendanceExceptionDetail(id) {
    return call(() => request(`/internship/exceptions/${id}`))
  },

  handleAttendanceException(id, { action, comment, expectedVersion, version }) {
    return call(() => request(`/internship/exceptions/${id}/handle`, {
      method: 'POST', body: { action, comment, expectedVersion: expectedVersion ?? version }
    }))
  },

  getWeeklyReports(params = {}) {
    return callList('/internship/reports', params)
  },

  getWeeklyReportDetail(id) {
    return call(() => request(`/internship/reports/${id}`))
  },

  reviewWeeklyReport(id, { action, comment, expectedVersion, version }) {
    return call(() => request(`/internship/reports/${id}/review`, {
      method: 'POST', body: { action, comment, expectedVersion: expectedVersion ?? version }
    }))
  },

  exportWeeklyReports(params = {}) {
    return call(() => request('/internship/reports/export', { method: 'POST', params }))
  },

  batchReviewWeeklyReports(itemsOrIds, { action = 'APPROVE', comment = '', versions } = {}) {
    const items = Array.isArray(itemsOrIds) && itemsOrIds.length && typeof itemsOrIds[0] === 'object'
      ? itemsOrIds.map((it) => ({
        id: it.id,
        expectedVersion: it.expectedVersion ?? it.version
      }))
      : (itemsOrIds || []).map((id, i) => ({
        id,
        expectedVersion: Array.isArray(versions) ? versions[i] : undefined
      }))
    return call(() => request('/internship/reports/batch-review', {
      method: 'POST', body: { items, action, comment }
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

  reviewProcessReport(id, { action, comment, expectedVersion, version }) {
    return call(() => request(`/internship/process-reports/${id}/review`, {
      method: 'POST', body: { action, comment, expectedVersion: expectedVersion ?? version }
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

  reviewChangeRequest(id, { action, comment, expectedVersion, version } = {}) {
    return call(() => request(`/internship/change-requests/${id}/review`, {
      method: 'POST',
      body: {
        action: action === 'APPROVE' ? 'APPROVE' : 'REJECT',
        comment,
        expectedVersion: expectedVersion ?? version
      }
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
