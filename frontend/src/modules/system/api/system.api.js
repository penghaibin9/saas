/**
 * 系统管理中心 API（半真实：读可合并 UI 脚手架；写操作禁止 mock 成功）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 页面禁止直接 import mocks，必须经本文件获取数据。
 * 留痕规则：所有写操作（含导入导出）均由后端审计；前端不伪造写成功。
 */
/* P2 · 真实后端桥 */
import { request, requestBlob, requestUpload, withFallback } from '@/services/http/client'
import * as realApi from '@/services/http/adapters'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import {
  tenantBrandConfig,
  currentRole,
  dataScope,
  permissionActions,
  statusOptions,
  filterOptions,
  fieldColumns,
  batchActions,
  importTemplates,
  exportOptions,
  dashboardSummary,
  userList,
  roleList,
  roleDetailMap,
  permissionTree,
  menuTree,
  roleMenuPreview,
  departmentTree,
  auditLogs
} from '@/mocks/system/system.mock'

import { MOCK_DELAY_MS } from '@/utils/mockDelay'

const DELAY = MOCK_DELAY_MS

/** 最近一次权限树展开得到的全部可见 permissionCode（保存角色权限时提交） */
let _lastPermissionTreeVisibleCodes = []
/** 最近一次权限树原始结构（角色详情拆分 menuKeys/buttonKeys 用） */
let _lastPermissionTree = []

function ok(data, message = 'ok') {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ code: 0, data, message }), DELAY)
  })
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

function paginate(list, { page = 1, pageSize = 10 } = {}) {
  const total = list.length
  const start = (page - 1) * pageSize
  return { list: list.slice(start, start + pageSize), total, page, pageSize }
}

function now() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

function mergeContextUiScaffold(data) {
  const mockStatus = clone(statusOptions)
  const mockFilter = clone(filterOptions)
  return {
    tenantBrandConfig: data.tenantBrandConfig || clone(tenantBrandConfig),
    currentRole: data.currentRole || clone(currentRole),
    dataScope: data.dataScope || clone(dataScope),
    /* 后端动作覆盖脚手架；失败路径不得走到这里（见 getContext fail） */
    permissionActions: {
      ...clone(permissionActions),
      ...(data.permissionActions || {})
    },
    permissionPatterns: data.permissionPatterns || [],
    statusOptions: { ...mockStatus, ...(data.statusOptions || {}) },
    filterOptions: {
      roles: (data.filterOptions?.roles?.length ? data.filterOptions.roles : mockFilter.roles),
      colleges: (data.filterOptions?.colleges?.length ? data.filterOptions.colleges : mockFilter.colleges),
      logModules: data.filterOptions?.logModules || mockFilter.logModules,
      logActions: data.filterOptions?.logActions || mockFilter.logActions
    },
    fieldColumns: (data.fieldColumns && Object.keys(data.fieldColumns).length)
      ? data.fieldColumns
      : clone(fieldColumns),
    batchActions: (data.batchActions && data.batchActions.length) ? data.batchActions : clone(batchActions),
    importTemplates: (data.importTemplates && Object.keys(data.importTemplates).length)
      ? data.importTemplates
      : clone(importTemplates),
    exportOptions: (data.exportOptions && Object.keys(data.exportOptions).length)
      ? data.exportOptions
      : clone(exportOptions)
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

  getDashboardSummary() {
    return withFallback('system.readiness', async () => {
      const data = await request('/system/readiness')
      const c = data.counts || {}
      return ok({
        stats: [
          { label: '在册账号', value: String(c.accounts || 0), trend: '仅统一导入入口可创建', trendQuality: 'neutral' },
          { label: '预设角色', value: String(c.roles || 0), trend: '标准模板自动初始化', trendQuality: c.roles >= 26 ? 'good' : 'bad' },
          { label: '学院', value: String(c.colleges || 0), trend: `专业 ${c.majors || 0} · 班级 ${c.classes || 0}`, trendQuality: 'neutral' }
        ],
        todos: (data.checks || []).filter((item) => !item.passed).map((item) => ({
          id: item.key, label: item.label, count: 1, tone: 'warning', hint: item.message, route: '/admin/system/org'
        })),
        securityAlerts: [], recentOps: []
      })
    }, () => ok(clone(dashboardSummary)))
  },

  /* ==================== 用户账号 ==================== */

  getUsers(params = {}) {
    const mockUsers = () => {
      let list = [...userList]
      if (params.keyword) {
        const kw = params.keyword.trim()
        list = list.filter((u) => u.name.includes(kw) || u.userNo.includes(kw) || (u.orgName || '').includes(kw))
      }
      if (params.orgId) list = list.filter((u) => u.orgId === params.orgId)
      if (params.role) list = list.filter((u) => u.roles.includes(params.role))
      if (params.status) list = list.filter((u) => u.status === params.status)
      return ok(paginate(list, params))
    }
    return withFallback('system.users', async () => ok(await request('/system/users', {
      params: {
        keyword: params.keyword || undefined,
        role: params.role || undefined,
        status: params.status || undefined,
        page: params.page || 1,
        page_size: params.pageSize || 20
      }
    })), mockUsers)
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

  async batchDisableUsers(ids, { reason }) {
    if (!reason || reason.trim().length < 5) return fail('批量停用原因必填且不少于 5 个字')
    try {
      return ok(await request('/system/user-batch-status', {
        method: 'PUT',
        body: { action: 'DISABLE', ids, reason }
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
  async exportUsers() {
    try {
      const blob = await requestBlob('/system/export/users')
      const fileName = '账号台账_' + now().slice(0, 10) + '.xlsx'
      saveBlob(blob, fileName)
      return ok({ fileName })
    } catch (error) {
      return apiError(error)
    }
  },

  /* ==================== 角色权限 ==================== */

  getRoles(params = {}) {
    const mockRoles = () => {
      let list = [...roleList]
      if (params.keyword) list = list.filter((r) => r.name.includes(params.keyword.trim()) || r.code.includes(params.keyword.trim().toUpperCase()))
      if (params.status) list = list.filter((r) => r.status === params.status)
      if (params.type) list = list.filter((r) => r.type === params.type)
      return ok(paginate(list, params))
    }
    return withFallback('system.roles', async () => {
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
    }, mockRoles)
  },

  getRoleDetail(id) {
    const mockDetail = () => {
      const preset = roleDetailMap[id]
      if (preset) return ok(clone(preset))
      const row = roleList.find((r) => r.id === id)
      if (!row) return fail('角色不存在')
      const menuKeys = [...(roleMenuPreview[row.code] || [])]
      const systemNode = permissionTree.find((node) => node.key === 'mod-system')
      const buttonKeys = (systemNode?.children || [])
        .filter((menu) => menuKeys.includes(menu.key))
        .flatMap((menu) => (menu.children || []).map((button) => button.key))
      return ok({ ...clone(row), menuKeys, buttonKeys, members: [], auditTrail: [{ who: '系统', time: row.updatedAt, action: '最近更新', affected: row.description }] })
    }
    return withFallback('system.role.detail', async () => {
      const data = await request(`/system/roles/${encodeURIComponent(id)}`)
      const tree = _lastPermissionTree.length ? _lastPermissionTree : []
      const fromBackend = (data.menuKeys || data.buttonKeys)
        ? { menuKeys: data.menuKeys || [], buttonKeys: data.buttonKeys || [] }
        : selectionFromPermissionCodes(data.permissionCodes || [], tree)
      return ok({ ...data, ...fromBackend })
    }, mockDetail)
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
    return ok(clone(menuTree))
  },

  saveMenu() {
    return fail('菜单由平台导航派生，学校侧不可改')
  },

  setMenuStatus() {
    return fail('菜单由平台导航派生，学校侧不可改')
  },

  previewRoleMenus(roleCode) {
    return ok({ roleCode, menuCodes: clone(roleMenuPreview[roleCode] || []) })
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

  getDepartmentTree() {
    return withFallback('system.org-tree', async () => ok(await request('/system/org-tree')),
      () => ok(clone(departmentTree)))
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
      return ok([], error.message || '暂无岗位归属数据')
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

  getAuditLogs() {
    return withFallback('audit.logs', () => realApi.getAuditLogs(), () => ok(clone(auditLogs)))
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
        params: { page: params.page || 1, page_size: params.pageSize || 50 }
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

  async saveModuleFeatures(features, { reason } = {}) {
    try {
      return ok(await request('/system/module-features', {
        method: 'PUT', body: { features, reason }
      }))
    } catch (error) {
      return fail(error.message || '业务开关保存失败')
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
  }
}

export default systemApi
