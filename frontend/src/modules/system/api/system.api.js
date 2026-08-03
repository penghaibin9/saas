/**
 * 系统管理中心 API（正式页面只读取真实后端；写操作禁止 mock 成功）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 页面不得直接读取演示数据，所有运行态事实必须经本文件访问真实接口。
 * 留痕规则：所有写操作（含导入导出）均由后端审计；前端不伪造写成功。
 */
/* P2 · 真实后端桥 */
import { request, requestBlob, requestUpload } from '@/services/http/client'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import {
  SYSTEM_STATUS_OPTIONS,
  SYSTEM_FIELD_COLUMNS,
  SYSTEM_BATCH_ACTIONS,
  SYSTEM_IMPORT_TEMPLATES,
  SYSTEM_EXPORT_OPTIONS
} from '@/modules/system/system.ui-config'

/** 最近一次权限树展开得到的全部可见 permissionCode（保存角色权限时提交） */
let _lastPermissionTreeVisibleCodes = []
/** 最近一次权限树原始结构（角色详情拆分 menuKeys/buttonKeys 用） */
let _lastPermissionTree = []

function ok(data, message = 'ok') {
  return Promise.resolve({ code: 0, data, message })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function apiError(error) {
  return { code: error?.code || 1, data: null, message: error?.message || '请求失败' }
}

function saveBlob(blob, filename) {
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

function clone(v) {
  return JSON.parse(JSON.stringify(v))
}

/** 树节点 key 即后端 permissionCode，直接合并去重 */
function permissionCodesFromSelection(menuKeys = [], buttonKeys = []) {
  return [...new Set([...menuKeys, ...buttonKeys].filter(Boolean))]
}

function selectionFromPermissionCodes(permissionCodes = [], tree = []) {
  const menuKeySet = new Set()
  const buttonKeySet = new Set()
  ;(tree || []).forEach((mod) => (mod.children || []).forEach((menu) => {
    menuKeySet.add(menu.key)
    ;(menu.children || []).forEach((btn) => buttonKeySet.add(btn.key))
  }))
  return {
    menuKeys: permissionCodes.filter((c) => menuKeySet.has(c)),
    buttonKeys: permissionCodes.filter((c) => buttonKeySet.has(c))
  }
}

function flattenPermissionTreeVisibleCodes(tree = []) {
  const codes = []
  ;(tree || []).forEach((mod) => {
    if (mod?.key) codes.push(mod.key)
    ;(mod.children || []).forEach((menu) => {
      if (menu?.key) codes.push(menu.key)
      ;(menu.children || []).forEach((btn) => {
        if (btn?.key) codes.push(btn.key)
      })
    })
  })
  return [...new Set(codes.filter(Boolean))]
}

function now() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function mergeContextUiScaffold(data) {
  return {
    tenantBrandConfig: data.tenantBrandConfig || {},
    currentRole: data.currentRole || {},
    dataScope: data.dataScope || {},
    permissionActions: data.permissionActions || {},
    permissionPatterns: data.permissionPatterns || [],
    statusOptions: { ...clone(SYSTEM_STATUS_OPTIONS), ...(data.statusOptions || {}) },
    filterOptions: {
      roles: data.filterOptions?.roles || [],
      colleges: data.filterOptions?.colleges || [],
      classes: data.filterOptions?.classes || [],
      grades: data.filterOptions?.grades || [],
      logModules: data.filterOptions?.logModules || [],
      logActions: data.filterOptions?.logActions || []
    },
    fieldColumns: (data.fieldColumns && Object.keys(data.fieldColumns).length)
      ? data.fieldColumns
      : clone(SYSTEM_FIELD_COLUMNS),
    batchActions: (data.batchActions && Object.keys(data.batchActions).length)
      ? data.batchActions
      : clone(SYSTEM_BATCH_ACTIONS),
    importTemplates: (data.importTemplates && Object.keys(data.importTemplates).length)
      ? data.importTemplates
      : clone(SYSTEM_IMPORT_TEMPLATES),
    exportOptions: (data.exportOptions && Object.keys(data.exportOptions).length)
      ? data.exportOptions
      : clone(SYSTEM_EXPORT_OPTIONS)
  }
}

export const systemApi = {
  /** 品牌 / 角色 / 数据范围 / 权限动作 / 字典 / 列配置（页面初始化统一获取） */
  async getContext() {
    try {
      const data = await request('/system/context')
      return ok(mergeContextUiScaffold(data || {}))
    } catch (error) {
      return fail(error.message || '系统管理上下文加载失败')
    }
  },

  async getDashboardSummary() {
    try {
      const [board, auditPage] = await Promise.all([
        request('/system/overview-board'),
        request('/system/operation-logs', { params: { page: 1, page_size: 8 } })
      ])
      const moduleStates = Object.values(board.moduleHealth || {})
      const availableModules = moduleStates.filter((item) => item.entitled && item.enabled).length
      const summary = board.goLive?.summary || {}
      const routeFor = (code = '') => {
        if (code === 'org') return '/admin/system/org'
        if (code === 'accounts') return '/admin/system/identity-import/students'
        if (code === 'roles' || code === 'permissions') return '/admin/system/roles'
        if (code === 'data_scope') return '/admin/system/scopes'
        if (code === 'integrations') return '/admin/system/integrations'
        if (code === 'sync') return '/admin/system/sync-jobs'
        if (code === 'modules' || code.startsWith('module_')) return '/admin/system/module-entitlements'
        if (code === 'workflow' || code === 'term') return '/admin/workflow/processes'
        return '/admin/system/implementation/acceptance'
      }
      return ok({
        stats: [
          {
            label: '可用业务模块',
            value: `${availableModules}/${moduleStates.length}`,
            trend: '平台授权与学校开关共同生效',
            trendQuality: availableModules === moduleStates.length ? 'good' : 'neutral'
          },
          {
            label: '上线阻断',
            value: String(summary.blocker || 0),
            trend: summary.blocker ? '需完成阻断项后验收' : '当前无阻断项',
            trendQuality: summary.blocker ? 'bad' : 'good'
          },
          {
            label: '同步失败',
            value: String((board.syncFailures || []).length),
            trend: '失败任务进入同步失败中心',
            trendQuality: (board.syncFailures || []).length ? 'bad' : 'good'
          }
        ],
        todos: (board.pendingItems || []).map((item) => ({
          id: item.code,
          label: item.title,
          count: 1,
          tone: item.status === 'BLOCKER' ? 'danger' : 'warning',
          hint: item.recommendedAction || item.detail,
          route: routeFor(item.code)
        })),
        securityAlerts: (board.securityRisks || []).map((item, index) => ({
          id: `risk-${index}`,
          title: item.text,
          detail: item.text,
          level: item.level || 'MEDIUM',
          time: '实时检查'
        })),
        recentOps: (auditPage.list || []).map((item) => ({
          id: item.id,
          who: item.who,
          action: item.actionLabel || item.action,
          time: item.time
        }))
      })
    } catch (error) {
      return fail(error.message || '系统运行总览加载失败')
    }
  },

  /* ==================== 用户账号 ==================== */

  async getUsers(params = {}) {
    try {
      return ok(await request('/system/users', {
        params: {
          keyword: params.keyword || undefined,
          role: params.role || undefined,
          status: params.status || undefined,
          account_type: params.accountType || undefined,
          college_id: params.collegeId || undefined,
          major_id: params.majorId || undefined,
          class_id: params.classId || undefined,
          grade: params.grade || undefined,
          student_status: params.studentStatus || undefined,
          page: params.page || 1,
          page_size: params.pageSize || 20
        }
      }))
    } catch (error) {
      return fail(error.message || '账号列表加载失败')
    }
  },

  async getUserDetail(id) {
    try {
      return ok(await request(`/system/users/${encodeURIComponent(id)}`))
    } catch (error) {
      return fail(error.message || '账号详情加载失败')
    }
  },

  createUser() {
    return fail('师生账号只能通过统一导入入口创建')
  },

  async updateUser(id, payload) {
    try {
      return ok(await request(`/system/users/${encodeURIComponent(id)}`, {
        method: 'PUT',
        body: payload
      }))
    } catch (error) {
      return fail(error.message || '账号更新失败')
    }
  },

  /** 停用/启用（真实库：更新 t_user.status，写审计。停用原因必填 ≥5 字，后端最终校验） */
  async setUserStatus(id, { action, reason }) {
    try {
      return ok(await request(`/system/users/${encodeURIComponent(id)}/status`, {
        method: 'PUT', body: { action, reason }
      }))
    } catch (error) {
      return fail(error.message || '账号状态更新失败')
    }
  },

  /** 重置密码（真实库：生成一次性临时密码，password_hash 更新 + 强制首登改密。临时密码仅本次随响应返回） */
  async resetUserPassword(id) {
    try {
      return ok(await request(`/system/users/${encodeURIComponent(id)}/reset-password`, {
        method: 'POST'
      }))
    } catch (error) {
      return fail(error.message || '重置密码失败')
    }
  },

  async assignUserRoles(id, roleCodes) {
    try {
      return ok(await request(`/system/users/${encodeURIComponent(id)}/roles`, {
        method: 'PUT', body: { roleCodes }
      }))
    } catch (error) {
      return fail(error.message || '角色分配失败')
    }
  },

  async batchDisableUsers(ids, {
    reason,
    accountType,
    scope = 'SELECTED',
    filters = {},
    confirmSchoolScope = false
  }) {
    if (!reason || reason.trim().length < 5) return fail('批量停用原因必填且不少于 5 个字')
    try {
      return ok(await request('/system/user-batch-status', {
        method: 'PUT',
        body: {
          action: 'DISABLE',
          ids,
          reason,
          accountType,
          scope,
          filters,
          confirmSchoolScope
        }
      }))
    } catch (error) {
      return fail(error.message || '批量停用失败')
    }
  },

  /** 旧 mock 导入入口：禁止写成功，引导到 identityImport APIs */
  importUsers({ confirm = false } = {}) {
    if (!confirm) {
      return fail('请使用统一导入：downloadIdentityImportTemplate / validateIdentityImportFile')
    }
    return fail('请使用 confirmIdentityImportBatch 完成师生账号导入，禁止 mock 写入')
  },

  /** 师生账号唯一导入入口：真实 xlsx 上传，不允许写操作回退 mock。 */
  async downloadIdentityImportTemplate() {
    try {
      const blob = await requestBlob('/system/identity-import/template')
      saveBlob(blob, '师生账号导入模板.xlsx')
      return { code: 0, data: {}, message: '模板已下载' }
    } catch (error) {
      return apiError(error)
    }
  },

  async validateIdentityImportFile(file) {
    try {
      const data = await requestUpload('/system/identity-import/validate-file', file)
      return { code: 0, data, message: 'Excel 解析及预检完成' }
    } catch (error) {
      return apiError(error)
    }
  },

  async confirmIdentityImportBatch(batchNo) {
    try {
      const data = await request('/system/identity-import/confirm-batch', {
        method: 'POST', body: { batchNo }
      })
      const entities = data.entities || {}
      const students = entities.studentAccounts?.created || 0
      const teachers = entities.teachers?.created || 0
      if (data.credentialReceipt) downloadXlsxFromApi(data.credentialReceipt)
      return {
        code: 0,
        data: {
          ...data,
          receipt: `已创建学生账号 ${students} 个、教师账号 ${teachers} 个${data.credentialReceipt ? '，初始凭据回执已下载' : ''}`
        },
        message: '师生账号已整批创建'
      }
    } catch (error) {
      return apiError(error)
    }
  },

  /* ── 学生 / 教师拆分入口（各自独立模板与接口语义，共用批次与回执能力）── */

  async downloadStudentImportTemplate() {
    try {
      const blob = await requestBlob('/system/identity-import/students/template')
      saveBlob(blob, '学生导入模板.xlsx')
      return { code: 0, data: {}, message: '模板已下载' }
    } catch (error) {
      return apiError(error)
    }
  },

  async validateStudentIdentityFile(file) {
    try {
      const data = await requestUpload('/system/identity-import/students/validate-file', file)
      return { code: 0, data, message: '学生名单解析及预检完成' }
    } catch (error) {
      return apiError(error)
    }
  },

  async confirmStudentIdentityBatch(batchNo) {
    try {
      const data = await request('/system/identity-import/students/confirm-batch', {
        method: 'POST', body: { batchNo }
      })
      const e = data.entities || {}
      const sum = data.summary || {}
      if (data.credentialReceipt) downloadXlsxFromApi(data.credentialReceipt)
      // 结果按 §10 分类回显，不只报一个笼统数字
      const parts = [
        `新建主档 ${e.students?.created || 0}`,
        `复用已有主档 ${sum.studentsReused || 0}`,
        `新建账号 ${e.studentAccounts?.created || 0}`,
        `补齐角色 ${sum.rolesFilled || 0}`,
        `已存在跳过 ${sum.accountsSkipped || 0}`
      ]
      const conflicts = (sum.IDENTITY_CONFLICT || 0) + (sum.ORG_CONFLICT || 0)
        + (sum.VOIDED_PROFILE || 0) + (sum.ACCOUNT_OCCUPIED || 0)
      if (conflicts) parts.push(`冲突待处理 ${conflicts}`)
      return {
        code: 0,
        data: { ...data, receipt: parts.join(' / ') + (data.credentialReceipt ? '，初始凭据回执已下载' : '') },
        message: '学生导入与账号开通已完成'
      }
    } catch (error) {
      return apiError(error)
    }
  },

  async downloadTeacherImportTemplate() {
    try {
      const blob = await requestBlob('/system/identity-import/teachers/template')
      saveBlob(blob, '教师导入模板.xlsx')
      return { code: 0, data: {}, message: '模板已下载' }
    } catch (error) {
      return apiError(error)
    }
  },

  async validateTeacherIdentityFile(file) {
    try {
      const data = await requestUpload('/system/identity-import/teachers/validate-file', file)
      return { code: 0, data, message: '教师名单解析及预检完成' }
    } catch (error) {
      return apiError(error)
    }
  },

  async confirmTeacherIdentityBatch(batchNo) {
    try {
      const data = await request('/system/identity-import/teachers/confirm-batch', {
        method: 'POST', body: { batchNo }
      })
      const e = data.entities || {}
      if (data.credentialReceipt) downloadXlsxFromApi(data.credentialReceipt)
      return {
        code: 0,
        data: {
          ...data,
          receipt: `已创建教师账号 ${e.teachers?.created || 0} 个、角色绑定 ${e.roleBindings?.created || 0} 条`
            + `${data.credentialReceipt ? '，初始凭据回执已下载' : ''}`
        },
        message: '教师账号已整批创建'
      }
    } catch (error) {
      return apiError(error)
    }
  },

  async downloadIdentityImportErrors(batchNo) {
    try {
      const blob = await requestBlob(`/system/identity-import/batches/${encodeURIComponent(batchNo)}/errors`)
      saveBlob(blob, `师生账号导入错误_${batchNo}.xlsx`)
      return { code: 0, data: {}, message: '错误回执已下载' }
    } catch (error) {
      return apiError(error)
    }
  },

  /** ── 老系统数据迁移（P1 · 6 域）：真实后端，不允许写操作回退 mock ── */
  async getMigrationOverview() {
    try {
      const data = await request('/system/migration/overview')
      return { code: 0, data }
    } catch (error) {
      return apiError(error)
    }
  },

  async getMigrationBatches(domain) {
    try {
      const data = await request(`/system/migration/batches${domain ? `?domain=${encodeURIComponent(domain)}` : ''}`)
      return { code: 0, data }
    } catch (error) {
      return apiError(error)
    }
  },

  async downloadMigrationTemplate(domain, label) {
    try {
      const blob = await requestBlob(`/system/migration/domains/${encodeURIComponent(domain)}/template`)
      saveBlob(blob, `数据迁移-${label || domain}模板.xlsx`)
      return { code: 0, data: {}, message: '模板已下载' }
    } catch (error) {
      return apiError(error)
    }
  },

  async validateMigrationFile(domain, file) {
    try {
      const data = await requestUpload(`/system/migration/domains/${encodeURIComponent(domain)}/validate-file`, file)
      return { code: 0, data, message: '文件解析并校验完成' }
    } catch (error) {
      return apiError(error)
    }
  },

  async downloadMigrationErrors(domain, rows, errors) {
    try {
      const data = await request(`/system/migration/domains/${encodeURIComponent(domain)}/errors-xlsx`, {
        method: 'POST', body: { rows, errors }
      })
      return { code: 0, data }
    } catch (error) {
      return apiError(error)
    }
  },

  async confirmMigrationBatch(batchNo) {
    try {
      const data = await request('/system/migration/confirm', { method: 'POST', body: { batchNo } })
      return { code: 0, data: { ...data, created: data.insertedRows }, message: '导入完成' }
    } catch (error) {
      return apiError(error)
    }
  },

  /** 导出账号台账（真实 xlsx：后端查真库+水印+导出留痕，浏览器直接下载） */
  async exportUsers({ accountType = '', filters = {} } = {}) {
    try {
      const params = new URLSearchParams()
      if (accountType) params.set('account_type', accountType)
      if (filters.keyword) params.set('keyword', filters.keyword)
      if (filters.role) params.set('role', filters.role)
      if (filters.status) params.set('status', filters.status)
      const query = params.toString()
      const blob = await requestBlob('/system/export/users' + (query ? `?${query}` : ''))
      const prefix = accountType === 'STUDENT' ? '学生账号台账_' : accountType === 'STAFF' ? '教职工账号台账_' : '账号台账_'
      const fileName = prefix + now().slice(0, 10) + '.xlsx'
      saveBlob(blob, fileName)
      return ok({ fileName })
    } catch (error) {
      return apiError(error)
    }
  },

  /* ==================== 角色权限 ==================== */

  async getRoles(params = {}) {
    try {
      const data = await request('/system/roles', {
        params: {
          keyword: params.keyword || undefined,
          type: params.type || undefined,
          status: params.status || undefined,
          page: params.page || 1,
          page_size: params.pageSize || 10
        }
      })
      return ok(data)
    } catch (error) {
      return fail(error.message || '角色列表加载失败')
    }
  },

  async getRoleDetail(id) {
    try {
      const data = await request(`/system/roles/${encodeURIComponent(id)}`)
      const tree = _lastPermissionTree.length ? _lastPermissionTree : []
      const fromBackend = (data.menuKeys || data.buttonKeys)
        ? { menuKeys: data.menuKeys || [], buttonKeys: data.buttonKeys || [] }
        : selectionFromPermissionCodes(data.permissionCodes || [], tree)
      return ok({ ...data, ...fromBackend })
    } catch (error) {
      return fail(error.message || '角色详情加载失败')
    }
  },

  async getPermissionTree() {
    try {
      const data = await request('/system/permissions/tree')
      const tree = data.tree || data || []
      _lastPermissionTree = tree
      _lastPermissionTreeVisibleCodes = Array.isArray(data.visibleCodes) && data.visibleCodes.length
        ? data.visibleCodes
        : flattenPermissionTreeVisibleCodes(tree)
      return ok(tree)
    } catch (error) {
      return fail(error.message || '权限树加载失败')
    }
  },

  async createRole(payload) {
    try {
      const data = await request('/system/roles', { method: 'POST', body: payload })
      return ok(data)
    } catch (error) {
      return fail(error.message || '创建角色失败')
    }
  },

  /** 编辑角色名称（真实库：仅自定义角色，预设角色平台维护。权限/范围走 saveRolePermissions） */
  async updateRole(id, payload) {
    try {
      return ok(await request(`/system/roles/${encodeURIComponent(id)}`, {
        method: 'PUT', body: { name: payload.name }
      }))
    } catch (error) {
      return fail(error.message || '角色更新失败')
    }
  },

  async copyRole(id) {
    try {
      const data = await request(`/system/roles/${encodeURIComponent(id)}/copy`, { method: 'POST' })
      return ok(data)
    } catch (error) {
      return fail(error.message || '复制角色失败')
    }
  },

  /** 停用自定义角色（真实库：预设角色不可停、有成员先改派，后端最终校验） */
  async deprecateRole(id, { reason }) {
    try {
      return ok(await request(`/system/roles/${encodeURIComponent(id)}/status`, {
        method: 'PUT', body: { action: 'DISABLE', reason }
      }))
    } catch (error) {
      return fail(error.message || '角色停用失败')
    }
  },

  async saveRolePermissions(id, { menuKeys, buttonKeys, scopeCode, visiblePermissionCodes } = {}) {
    try {
      const permissionCodes = permissionCodesFromSelection(menuKeys, buttonKeys)
      const visible = visiblePermissionCodes
        || (_lastPermissionTreeVisibleCodes.length
          ? _lastPermissionTreeVisibleCodes
          : permissionCodes)
      const data = await request(`/system/roles/${encodeURIComponent(id)}/permissions`, {
        method: 'PUT',
        body: {
          permissionCodes,
          visiblePermissionCodes: visible,
          scopeCode
        }
      })
      return ok(data)
    } catch (error) {
      return fail(error.message || '保存权限配置失败')
    }
  },

  /** 导出角色权限配置（真实 JSON：后端查真库权限点，不含成员，浏览器直接下载） */
  async exportRoleConfig(id) {
    try {
      const blob = await requestBlob(`/system/export/role-config/${encodeURIComponent(id)}`)
      const fileName = `角色配置_${id}.json`
      saveBlob(blob, fileName)
      return ok({ fileName })
    } catch (error) {
      return apiError(error)
    }
  },

  /* ==================== 菜单权限 ==================== */

  getMenuTree() {
    return fail('菜单配置已并入角色权限页，旧菜单编辑入口已停用')
  },

  saveMenu() {
    return fail('菜单由平台导航派生，学校侧不可改')
  },

  setMenuStatus() {
    return fail('菜单由平台导航派生，学校侧不可改')
  },

  previewRoleMenus(roleCode) {
    return fail(`角色 ${roleCode || ''} 的入口预览请在角色权限页查看`)
  },

  /* ==================== 数据范围 ==================== */

  /** 数据范围规则目录（真实库 t_data_scope_rule；引用角色/影响用户由后端按角色 scopeCode 真实计算） */
  async getScopeRules(params = {}) {
    try {
      return ok(await request('/system/scope-rules', {
        params: { keyword: params.keyword || undefined, status: params.status || undefined }
      }))
    } catch (error) {
      return fail(error.message || '数据范围规则加载失败')
    }
  },

  async saveScopeRule(payload) {
    try {
      return ok(await request('/system/scope-rules', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '规则保存失败')
    }
  },

  async deprecateScopeRule(id, { reason }) {
    try {
      return ok(await request(`/system/scope-rules/${encodeURIComponent(id)}/status`, {
        method: 'PUT', body: { action: 'DISABLE', reason }
      }))
    } catch (error) {
      return fail(error.message || '规则作废失败')
    }
  },

  async getScopeAffectedUsers(id) {
    try {
      const data = await request(`/system/scope-rules/${encodeURIComponent(id)}/users`)
      return ok(Array.isArray(data) ? data : (data.list || []))
    } catch (error) {
      return fail(error.message || '影响用户加载失败')
    }
  },

  /** 导出数据范围规则清单（真实 xlsx：含引用角色/影响人数+水印，浏览器直接下载） */
  async exportScopeRules() {
    try {
      const blob = await requestBlob('/system/export/scope-rules')
      const fileName = '数据范围规则_' + now().slice(0, 10) + '.xlsx'
      saveBlob(blob, fileName)
      return ok({ fileName })
    } catch (error) {
      return apiError(error)
    }
  },

  /* ==================== 组织结构 ==================== */

  async getDepartmentTree() {
    try {
      return ok(await request('/system/org-tree'))
    } catch (error) {
      return fail(error.message || '组织结构加载失败')
    }
  },

  /** 岗位列表：映射教职工归属；失败则返回空列表 */
  async getPositions() {
    try {
      const data = await request('/system/staff-affiliations')
      const list = (data.list || []).map((row) => ({
        id: row.id,
        name: row.roleLabel || '岗位',
        orgName: row.orgName || '',
        memberCount: 1,
        remark: [row.staffName, row.staffKey].filter(Boolean).join(' · ') || '',
        status: (row.status === 'ACTIVE' || !row.status) ? 'ENABLED' : row.status,
        statusLabel: (row.status === 'ACTIVE' || !row.status) ? '启用' : String(row.status)
      }))
      return ok(list, '岗位数据来自教职工归属')
    } catch (error) {
      return fail(error.message || '教职工归属加载失败')
    }
  },

  async saveOrgNode(payload) {
    try {
      const path = payload.id ? `/system/org-nodes/${encodeURIComponent(payload.id)}` : '/system/org-nodes'
      return ok(await request(path, { method: payload.id ? 'PUT' : 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '保存组织节点失败')
    }
  },

  /** 停用组织节点（真实库：班级有在籍学生先转出，后端最终校验） */
  async deprecateOrgNode(id, { type, reason }) {
    try {
      return ok(await request(`/system/org-nodes/${encodeURIComponent(id)}/status`, {
        method: 'PUT', body: { type, action: 'DISABLE', reason }
      }))
    } catch (error) {
      return fail(error.message || '组织节点停用失败')
    }
  },

  importOrg() {
    return fail('组织导入请前往实施中心「数据导入与智能匹配」：/admin/system/implementation/data-mapping')
  },

  /** 导出组织结构（真实 xlsx：院系/专业/班级+在籍人数+水印，浏览器直接下载） */
  async exportOrg() {
    try {
      const blob = await requestBlob('/system/export/org')
      const fileName = '组织结构_' + now().slice(0, 10) + '.xlsx'
      saveBlob(blob, fileName)
      return ok({ fileName })
    } catch (error) {
      return apiError(error)
    }
  },

  /* ==================== 系统 / 品牌配置 ==================== */

  /** 学校侧品牌配置（真实库 t_tenant_brand_config，编辑后经 /tenant/brand 真实生效于顶栏/登录页） */
  async getBrandConfig() {
    try {
      return ok(await request('/system/brand'))
    } catch (error) {
      return fail(error.message || '品牌配置加载失败')
    }
  },

  async saveBrandConfig(payload, { reason } = {}) {
    try {
      return ok(await request('/system/brand', { method: 'PUT', body: { ...payload, reason } }))
    } catch (error) {
      return fail(error.message || '品牌保存失败')
    }
  },

  async resetBrandConfig({ reason } = {}) {
    try {
      return ok(await request('/system/brand/reset', { method: 'POST', body: { reason } }))
    } catch (error) {
      return fail(error.message || '品牌恢复默认失败')
    }
  },

  /** 系统配置列表（真实库 t_sys_config，返回真实生效值） */
  async getSystemConfigs() {
    try {
      const data = await request('/system/configs')
      return ok(data.list)
    } catch (error) {
      return fail(error.message || '系统配置加载失败')
    }
  },

  /** 保存系统配置（真实生效：登录锁定阈值/时长、密码最小长度被强制层真实读取） */
  async saveSystemConfig(key, valueText, { reason } = {}) {
    try {
      return ok(await request(`/system/configs/${encodeURIComponent(key)}`, {
        method: 'PUT', body: { valueText, reason }
      }))
    } catch (error) {
      return fail(error.message || '配置保存失败')
    }
  },

  /** getConfigs / saveConfig 别名，供登录策略页绑定 SEC_* */
  getConfigs() {
    return this.getSystemConfigs()
  },

  saveConfig(key, valueText, opts) {
    return this.saveSystemConfig(key, valueText, opts)
  },

  /** 导出系统与品牌配置快照（真实 JSON：后端查真库,不含密钥,浏览器直接下载） */
  async exportConfigs() {
    try {
      const blob = await requestBlob('/system/export/configs')
      const fileName = '系统配置快照_' + now().slice(0, 10) + '.json'
      saveBlob(blob, fileName)
      return ok({ fileName })
    } catch (error) {
      return apiError(error)
    }
  },

  /* ==================== 日志（只读 + 导出，禁止删除） ==================== */

  /** 登录与安全审计（真实库 t_security_audit_log）。安全敏感：不做 mock 回落。 */
  async getLoginLogs(params = {}) {
    try {
      return ok(await request('/system/login-logs', {
        params: {
          keyword: params.keyword || undefined,
          result: params.result || undefined,
          date_from: params.dateFrom || params.date_from || undefined,
          date_to: params.dateTo || params.date_to || undefined,
          page: params.page || 1,
          page_size: params.pageSize || 20
        }
      }))
    } catch (error) {
      return fail(error.message || '登录日志加载失败')
    }
  },

  /** 操作与权限审计（真实库 t_security_audit_log）。同样不做 mock 回落。 */
  async getOperationLogs(params = {}) {
    try {
      return ok(await request('/system/operation-logs', {
        params: {
          keyword: params.keyword || undefined,
          result: params.result || undefined,
          action: params.action || undefined,
          module: params.module || undefined,
          date_from: params.dateFrom || params.date_from || undefined,
          date_to: params.dateTo || params.date_to || undefined,
          page: params.page || 1,
          page_size: params.pageSize || 20
        }
      }))
    } catch (error) {
      return fail(error.message || '操作日志加载失败')
    }
  },

  getAuditLogs(params = {}) {
    return this.getOperationLogs(params)
  },

  /** 导出登录/操作审计（真实 xlsx：后端查真库 t_security_audit_log+水印，浏览器直接下载） */
  async exportLogs({ tab } = {}) {
    try {
      const t = tab === 'login' ? 'login' : 'operation'
      const blob = await requestBlob(`/system/export/logs?tab=${t}`)
      const fileName = (t === 'login' ? '登录审计_' : '操作审计_') + now().slice(0, 10) + '.xlsx'
      saveBlob(blob, fileName)
      return ok({ fileName })
    } catch (error) {
      return apiError(error)
    }
  },

  /* ==================== 治理扩展 P0–P3 ==================== */

  async listAccountExceptions(params = {}) {
    try {
      return ok(await request('/system/users-exceptions', {
        params: {
          account_type: params.accountType || undefined,
          page: params.page || 1,
          page_size: params.pageSize || 50
        }
      }))
    } catch (error) {
      return fail(error.message || '账号异常列表加载失败')
    }
  },

  async listStaffAffiliations() {
    try {
      return ok(await request('/system/staff-affiliations'))
    } catch (error) {
      return fail(error.message || '教职工归属加载失败')
    }
  },

  async listDelegations() {
    try {
      return ok(await request('/system/delegations'))
    } catch (error) {
      return fail(error.message || '临时授权列表加载失败')
    }
  },

  async createDelegation(payload) {
    try {
      return ok(await request('/system/delegations', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '创建临时授权失败')
    }
  },

  async revokeDelegation(id, { reason } = {}) {
    try {
      return ok(await request(`/system/delegations/${encodeURIComponent(id)}/revoke`, {
        method: 'POST', body: { reason }
      }))
    } catch (error) {
      return fail(error.message || '回收临时授权失败')
    }
  },

  async listIntegrations() {
    try {
      return ok(await request('/system/integrations'))
    } catch (error) {
      return fail(error.message || '接口连接列表加载失败')
    }
  },

  async saveIntegration(payload) {
    try {
      return ok(await request('/system/integrations', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '保存接口连接失败')
    }
  },

  async rotateIntegration(id, { credential } = {}) {
    try {
      return ok(await request(`/system/integrations/${encodeURIComponent(id)}/rotate`, {
        method: 'POST', body: { credential }
      }))
    } catch (error) {
      return fail(error.message || '轮换凭证失败')
    }
  },

  async listSyncJobs() {
    try {
      return ok(await request('/system/sync-jobs'))
    } catch (error) {
      return fail(error.message || '同步任务列表加载失败')
    }
  },

  async enqueueSyncJob(payload) {
    try {
      return ok(await request('/system/sync-jobs', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '登记同步任务失败')
    }
  },

  async retrySyncJob(id) {
    try {
      return ok(await request(`/system/sync-jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' }))
    } catch (error) {
      return fail(error.message || '重试同步任务失败')
    }
  },

  async cancelSyncJob(id, { reason } = {}) {
    try {
      return ok(await request(`/system/sync-jobs/${encodeURIComponent(id)}/cancel`, {
        method: 'POST', body: { reason }
      }))
    } catch (error) {
      return fail(error.message || '取消同步任务失败')
    }
  },

  async getModuleFeatures() {
    try {
      return ok(await request('/system/module-features'))
    } catch (error) {
      return fail(error.message || '模块开关加载失败')
    }
  },

  async saveModuleFeatures(features, { reason, expectedVersion } = {}) {
    try {
      return ok(await request('/system/module-features', {
        method: 'PUT', body: { features, reason, expectedVersion }
      }))
    } catch (error) {
      return fail(error.message || '业务开关保存失败')
    }
  },

  // SYS-13：能力四态与单键启停（整份 module-features 覆盖已退役为兼容入口）
  async listCapabilitySettings() {
    try {
      return ok(await request('/system/capability-settings'))
    } catch (error) {
      return fail(error.message || '模块授权加载失败')
    }
  },

  async getCapabilityImpact(key) {
    try {
      return ok(await request(`/system/capability-settings/${encodeURIComponent(key)}/impact`))
    } catch (error) {
      return fail(error.message || '影响预览加载失败')
    }
  },

  async setCapabilitySetting(key, { enabled, reason, expectedVersion } = {}) {
    try {
      return ok(await request(`/system/capability-settings/${encodeURIComponent(key)}`, {
        method: 'PUT', body: { enabled, reason, expectedVersion }
      }))
    } catch (error) {
      // 保留 bizCode：页面据此区分"版本冲突需刷新"与普通失败
      return { ...apiError(error), bizCode: error?.bizCode || '' }
    }
  },

  async listSensitiveLogs(params = {}) {
    try {
      return ok(await request('/system/sensitive-logs', {
        params: {
          keyword: params.keyword || undefined,
          result: params.result || undefined,
          date_from: params.dateFrom || params.date_from || undefined,
          date_to: params.dateTo || params.date_to || undefined,
          page: params.page || 1,
          page_size: params.pageSize || 20
        }
      }))
    } catch (error) {
      return fail(error.message || '敏感审计加载失败')
    }
  },

  // ── SYS-12 学年学期、业务日历与统一切换 ──────────────────────────────
  // 学期主数据仍由教务维护；本组接口只做全校统一切换治理与唯一读取入口。

  /** 学期治理列表：含未纳入治理的学期、一致性问题和受影响模块 */
  async getAcademicCalendars() {
    try {
      return ok(await request('/system/academic-calendars'))
    } catch (error) {
      return fail(error.message || '学年学期加载失败')
    }
  },

  /** 当前生效学期（全系统唯一读取入口，前端不得自行按日期推断） */
  async getCurrentAcademicCalendar(moduleCode) {
    try {
      const query = moduleCode ? `?module=${encodeURIComponent(moduleCode)}` : ''
      return ok(await request(`/system/academic-calendars/current${query}`))
    } catch (error) {
      return fail(error.message || '当前学期加载失败')
    }
  },

  /** 学期详情：阻断项、业务窗口与切换历史 */
  async getAcademicCalendarDetail(termId) {
    try {
      return ok(await request(`/system/academic-calendars/${encodeURIComponent(termId)}`))
    } catch (error) {
      return fail(error.message || '学期详情加载失败')
    }
  },

  /** 把教务已建学期纳入全校治理（幂等） */
  async enrollAcademicCalendar(termId, { timezone } = {}) {
    try {
      return ok(await request(`/system/academic-calendars/${encodeURIComponent(termId)}/enroll`, {
        method: 'POST', body: { timezone }
      }))
    } catch (error) {
      return fail(error.message || '纳入治理失败')
    }
  },

  /**
   * 学期状态切换。expectedVersion 必传，后端据此做乐观锁；
   * 结期被阻断时后端返回 409 + blockers，页面必须展示而不是吞掉。
   */
  async transitionAcademicCalendar(termId, { targetStatus, reason, expectedVersion, scheduledAt, force } = {}) {
    try {
      return ok(await request(`/system/academic-calendars/${encodeURIComponent(termId)}/transition`, {
        method: 'POST',
        body: { targetStatus, reason, expectedVersion, scheduledAt, force: !!force }
      }))
    } catch (error) {
      return fail(error.message || '学期状态变更失败')
    }
  },

  /** 结期阻断项（只读；系统管理不代业务模块确认业务事实） */
  async getAcademicCalendarBlockers(termId) {
    try {
      return ok(await request(`/system/academic-calendars/${encodeURIComponent(termId)}/closing-blockers`))
    } catch (error) {
      return fail(error.message || '阻断项加载失败')
    }
  },

  /** 维护考试/迎新/实习/毕设等业务窗口 */
  async saveAcademicCalendarWindow(termId, payload = {}) {
    try {
      return ok(await request(`/system/academic-calendars/${encodeURIComponent(termId)}/windows`, {
        method: 'PUT', body: payload
      }))
    } catch (error) {
      return fail(error.message || '业务窗口保存失败')
    }
  },

  // ── SYS-04 组织变更版本与教职工任职 ──────────────────────────────────
  // 组织仍是学院/专业/班级三张实体表；这里是"未来生效的变更集"和"带有效期的任职"。

  /** 组织变更版本列表 */
  async getOrgVersions() {
    try {
      return ok(await request('/system/org-versions'))
    } catch (error) {
      return fail(error.message || '组织变更版本加载失败')
    }
  },

  /** 新建组织变更版本（草稿不影响当前组织） */
  async createOrgVersion({ versionName, reason } = {}) {
    try {
      return ok(await request('/system/org-versions', { method: 'POST', body: { versionName, reason } }))
    } catch (error) {
      return fail(error.message || '创建组织变更版本失败')
    }
  },

  /** 版本详情与变更项 */
  async getOrgVersionDetail(versionId) {
    try {
      return ok(await request(`/system/org-versions/${encodeURIComponent(versionId)}`))
    } catch (error) {
      return fail(error.message || '版本详情加载失败')
    }
  },

  /** 向草稿版本添加一条变更 */
  async addOrgVersionChange(versionId, payload = {}) {
    try {
      return ok(await request(`/system/org-versions/${encodeURIComponent(versionId)}/changes`, {
        method: 'POST', body: payload
      }))
    } catch (error) {
      return fail(error.message || '添加变更项失败')
    }
  },

  /** 校验 / 排期 / 激活 / 回滚组织变更版本 */
  async transitionOrgVersion(versionId, { targetStatus, reason, expectedVersion, effectiveAt } = {}) {
    try {
      return ok(await request(`/system/org-versions/${encodeURIComponent(versionId)}/transition`, {
        method: 'POST', body: { targetStatus, reason, expectedVersion, effectiveAt }
      }))
    } catch (error) {
      return fail(error.message || '组织版本状态变更失败')
    }
  },

  /** 移动或停用某节点会影响多少下级与学生 */
  async getOrgNodeImpact(orgType, nodeId) {
    try {
      return ok(await request(
        `/system/org-nodes/${encodeURIComponent(orgType)}/${encodeURIComponent(nodeId)}/impact`
      ))
    } catch (error) {
      return fail(error.message || '影响面计算失败')
    }
  },

  /** 教职工任职（默认只返回此刻真实生效的） */
  async listStaffAssignments({ userId, orgType, orgNodeId, includeExpired } = {}) {
    try {
      const qs = new URLSearchParams()
      if (userId) qs.set('userId', userId)
      if (orgType) qs.set('orgType', orgType)
      if (orgNodeId) qs.set('orgNodeId', orgNodeId)
      if (includeExpired) qs.set('includeExpired', 'true')
      const suffix = qs.toString() ? `?${qs.toString()}` : ''
      return ok(await request(`/system/staff-assignments${suffix}`))
    } catch (error) {
      return fail(error.message || '任职记录加载失败')
    }
  },

  /** 任命岗位（可指定起止时间；到期后自动失效） */
  async createStaffAssignment(payload = {}) {
    try {
      return ok(await request('/system/staff-assignments', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '任职创建失败')
    }
  },

  /** 撤销任职 */
  async revokeStaffAssignment(assignmentId, { reason, expectedVersion } = {}) {
    try {
      return ok(await request(`/system/staff-assignments/${encodeURIComponent(assignmentId)}/revoke`, {
        method: 'POST', body: { reason, expectedVersion }
      }))
    } catch (error) {
      return fail(error.message || '任职撤销失败')
    }
  },

  // ── SYS-11 有效配置：来源链与分层覆盖 ────────────────────────────────
  // 最终值由后端一个 Resolver 算出，前端只展示，不自行推断来源。

  /** 配置最终值与完整来源链（不传 configKey 返回全部） */
  async getEffectiveConfig({ configKey, domain, orgUnitId, termId } = {}) {
    try {
      const qs = new URLSearchParams()
      if (configKey) qs.set('configKey', configKey)
      if (domain) qs.set('domain', domain)
      if (orgUnitId) qs.set('orgUnitId', orgUnitId)
      if (termId) qs.set('termId', termId)
      const suffix = qs.toString() ? `?${qs.toString()}` : ''
      return ok(await request(`/system/effective-config${suffix}`))
    } catch (error) {
      return fail(error.message || '有效配置加载失败')
    }
  },

  /** 设置学校/组织/学期级配置覆盖；越过平台底线后端会拒绝 */
  async setConfigOverride(payload = {}) {
    try {
      return ok(await request('/system/config-overrides', { method: 'PUT', body: payload }))
    } catch (error) {
      return fail(error.message || '配置保存失败')
    }
  },

  /** 撤销一层配置覆盖 */
  async revokeConfigOverride(overrideId, { reason, expectedVersion } = {}) {
    try {
      return ok(await request(`/system/config-overrides/${encodeURIComponent(overrideId)}/revoke`, {
        method: 'POST', body: { reason, expectedVersion }
      }))
    } catch (error) {
      return fail(error.message || '配置撤销失败')
    }
  },

  /** 某个配置的变更历史 */
  async getConfigHistory(configKey) {
    try {
      return ok(await request(`/system/config-history/${encodeURIComponent(configKey)}`))
    } catch (error) {
      return fail(error.message || '配置历史加载失败')
    }
  },

  // ── SYS-06 权限包、交付模板与通配退役 ────────────────────────────────
  // 治理层：保存自定义角色只写治理表，不改变任何人当前的实际权限。

  /** 从当前代码固化交付模板与权限包（幂等） */
  async bootstrapPermissionGovernance() {
    try {
      return ok(await request('/system/permission-governance/bootstrap', { method: 'POST' }))
    } catch (error) {
      return fail(error.message || '权限治理初始化失败')
    }
  },

  /** 交付角色模板（DELIVERED，学校只读） */
  async getRoleTemplates() {
    try {
      return ok(await request('/system/role-templates'))
    } catch (error) {
      return fail(error.message || '交付角色模板加载失败')
    }
  },

  /** 模板权限上限与其持有的通配 */
  async getRoleTemplateDetail(templateCode) {
    try {
      return ok(await request(`/system/role-templates/${encodeURIComponent(templateCode)}`))
    } catch (error) {
      return fail(error.message || '模板详情加载失败')
    }
  },

  /** 权限包目录 */
  async getPermissionBundles() {
    try {
      return ok(await request('/system/permission-bundles'))
    } catch (error) {
      return fail(error.message || '权限包加载失败')
    }
  },

  /** 通配权限退役队列（展开数为下界，见后端 disclaimer） */
  async getWildcardRetirement() {
    try {
      return ok(await request('/system/wildcard-retirement'))
    } catch (error) {
      return fail(error.message || '通配退役队列加载失败')
    }
  },

  /** 学校自定义角色（含来源模板） */
  async getCustomRoles() {
    try {
      return ok(await request('/system/custom-roles'))
    } catch (error) {
      return fail(error.message || '自定义角色加载失败')
    }
  },

  /** 从交付模板复制出学校自定义角色；超模板上限后端会 403 */
  async cloneRoleTemplate({ templateCode, roleCode, permissionCodes } = {}) {
    try {
      return ok(await request('/system/custom-roles/clone', {
        method: 'POST', body: { templateCode, roleCode, permissionCodes }
      }))
    } catch (error) {
      return fail(error.message || '自定义角色创建失败')
    }
  },

  // ── SYS-08 组织安全树：显式 DENY 与判定解释 ──────────────────────────
  // DENY 优先于一切 ALLOW（含继承）；判定链由后端返回，前端只展示不重算。

  /** 范围策略列表（ALLOW / DENY） */
  async getScopePolicies(roleCode) {
    try {
      const suffix = roleCode ? `?roleCode=${encodeURIComponent(roleCode)}` : ''
      return ok(await request(`/system/scope-policies${suffix}`))
    } catch (error) {
      return fail(error.message || '范围策略加载失败')
    }
  },

  /** 设置角色对某组织节点的 ALLOW 或 DENY */
  async setScopePolicy(payload = {}) {
    try {
      return ok(await request('/system/scope-policies', { method: 'PUT', body: payload }))
    } catch (error) {
      return fail(error.message || '范围策略保存失败')
    }
  },

  /** 撤销一条范围策略 */
  async revokeScopePolicy(policyId, { reason, expectedVersion } = {}) {
    try {
      return ok(await request(`/system/scope-policies/${encodeURIComponent(policyId)}/revoke`, {
        method: 'POST', body: { reason, expectedVersion }
      }))
    } catch (error) {
      return fail(error.message || '范围策略撤销失败')
    }
  },

  /** 模拟判定：返回完整判定链与原因码（与真实判定同一核心） */
  async simulateScopePolicy({ roleCode, targetType, targetId, businessRelationAllows } = {}) {
    try {
      return ok(await request('/system/scope-policies/simulate', {
        method: 'POST', body: { roleCode, targetType, targetId, businessRelationAllows }
      }))
    } catch (error) {
      return fail(error.message || '范围模拟失败')
    }
  },

  // ── SYS-09 安全变更：草稿、审核、排期、激活与回滚 ────────────────────
  // 草稿/审核/排期期间不写任何权限表；只有激活才生效并产生新的安全版本号。

  /** 当前安全版本号 */
  async getSecurityRevision() {
    try {
      return ok(await request('/system/security-revision'))
    } catch (error) {
      return fail(error.message || '安全版本号加载失败')
    }
  },

  /** 安全变更列表 */
  async getSecurityChanges() {
    try {
      return ok(await request('/system/security-changes'))
    } catch (error) {
      return fail(error.message || '安全变更加载失败')
    }
  },

  /** 创建安全变更草稿 */
  async createSecurityChange({ title, reason, riskLevel } = {}) {
    try {
      return ok(await request('/system/security-changes', {
        method: 'POST', body: { title, reason, riskLevel }
      }))
    } catch (error) {
      return fail(error.message || '安全变更创建失败')
    }
  },

  /** 变更详情与变更项 */
  async getSecurityChangeDetail(changeSetId) {
    try {
      return ok(await request(`/system/security-changes/${encodeURIComponent(changeSetId)}`))
    } catch (error) {
      return fail(error.message || '变更详情加载失败')
    }
  },

  /** 向草稿追加一条改动 */
  async addSecurityChangeItem(changeSetId, { targetType, targetId, after } = {}) {
    try {
      return ok(await request(`/system/security-changes/${encodeURIComponent(changeSetId)}/items`, {
        method: 'POST', body: { targetType, targetId, after }
      }))
    } catch (error) {
      return fail(error.message || '变更项添加失败')
    }
  },

  /** 提交 / 审核 / 排期 / 激活 / 回滚 */
  async transitionSecurityChange(changeSetId, { targetStatus, reason, expectedVersion, scheduledAt, selfReviewAck } = {}) {
    try {
      return ok(await request(`/system/security-changes/${encodeURIComponent(changeSetId)}/transition`, {
        method: 'POST',
        body: { targetStatus, reason, expectedVersion, scheduledAt, selfReviewAck }
      }))
    } catch (error) {
      return fail(error.message || '安全变更状态变更失败')
    }
  },

  /** 激活历史（版本号只进不退） */
  async getSecurityActivations() {
    try {
      return ok(await request('/system/security-activations'))
    } catch (error) {
      return fail(error.message || '激活历史加载失败')
    }
  },

  // ── SYS-10 访问解释、职责分离、紧急访问与权限复核 ────────────────────
  // 解释结论由后端真实鉴权核心给出，前端只展示判定链，不自行推断。

  /** 解释某人对某动作的判定，逐层给出 PASS/FAIL */
  async explainAccess({ actionCode, resourceType, resourceId, scopeTargetType, scopeTargetId } = {}) {
    try {
      return ok(await request('/system/access-explanations', {
        method: 'POST',
        body: { actionCode, resourceType, resourceId, scopeTargetType, scopeTargetId }
      }))
    } catch (error) {
      return fail(error.message || '访问解释失败')
    }
  },

  /** 按 traceId 复现当时的判定链 */
  async getAccessTrace(traceId) {
    try {
      return ok(await request(`/system/access-explanations/${encodeURIComponent(traceId)}`))
    } catch (error) {
      return fail(error.message || '判定记录加载失败')
    }
  },

  /** 最近的拒绝记录 */
  async getAccessDenials() {
    try {
      return ok(await request('/system/access-denials'))
    } catch (error) {
      return fail(error.message || '拒绝记录加载失败')
    }
  },

  /** 职责分离规则与已检出冲突 */
  async getSodRules() {
    try {
      return ok(await request('/system/sod'))
    } catch (error) {
      return fail(error.message || '职责分离规则加载失败')
    }
  },

  /** 新增职责分离规则 */
  async createSodRule(payload = {}) {
    try {
      return ok(await request('/system/sod/rules', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '规则创建失败')
    }
  },

  /** 紧急访问会话列表 */
  async getEmergencySessions() {
    try {
      return ok(await request('/system/emergency-sessions'))
    } catch (error) {
      return fail(error.message || '紧急访问加载失败')
    }
  },

  /** 开通紧急访问（必须有工单号，最长 8 小时） */
  async grantEmergencySession(payload = {}) {
    try {
      return ok(await request('/system/emergency-sessions', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '紧急访问开通失败')
    }
  },

  /** 提前收回紧急访问 */
  async revokeEmergencySession(sessionCode, { reason } = {}) {
    try {
      return ok(await request(`/system/emergency-sessions/${encodeURIComponent(sessionCode)}/revoke`, {
        method: 'POST', body: { reason }
      }))
    } catch (error) {
      return fail(error.message || '紧急访问收回失败')
    }
  },

  /** 权限复核活动列表 */
  async getAccessReviews() {
    try {
      return ok(await request('/system/access-reviews'))
    } catch (error) {
      return fail(error.message || '复核活动加载失败')
    }
  },

  /** 复核活动详情 */
  async getAccessReviewDetail(campaignId) {
    try {
      return ok(await request(`/system/access-reviews/${encodeURIComponent(campaignId)}`))
    } catch (error) {
      return fail(error.message || '复核详情加载失败')
    }
  },

  /** 发起一轮权限复核 */
  async createAccessReview(payload = {}) {
    try {
      return ok(await request('/system/access-reviews', { method: 'POST', body: payload }))
    } catch (error) {
      return fail(error.message || '复核活动创建失败')
    }
  },

  /** 给出复核结论；调整或回收必须关联安全变更 */
  async decideAccessReviewItem(itemId, payload = {}) {
    try {
      return ok(await request(`/system/access-reviews/items/${encodeURIComponent(itemId)}/decide`, {
        method: 'POST', body: payload
      }))
    } catch (error) {
      return fail(error.message || '复核结论提交失败')
    }
  }
}

export default systemApi
