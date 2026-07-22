/**
 * 系统管理中心 API（mock 实现）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 真实后端阶段仅替换实现，方法签名冻结不变（与 internship/dashboard 模块同约定）。
 * 页面禁止直接 import mocks，必须经本文件获取数据。
 * 留痕规则：所有写操作（含导入导出）均追加 operationLogList / auditLogs，不提供删除审计日志的方法。
 */
/* P2 · 真实后端桥 */
import { request, requestBlob, requestUpload, withFallback } from '@/services/http/client'
import * as realApi from '@/services/http/adapters'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { SYSTEM_ACTION_PERMISSION_BY_KEY, SYSTEM_MENU_PERMISSION_BY_KEY } from '@/modules/system/systemManagementCatalog'
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
  userDetailMap,
  roleList,
  roleDetailMap,
  permissionTree,
  menuTree,
  roleMenuPreview,
  dataScopeRules,
  scopeAffectedUsersMap,
  departmentTree,
  positionList,
  loginLogList,
  operationLogList,
  systemConfigList,
  brandConfig,
  auditLogs
} from '@/mocks/system/system.mock'

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

const menuKeyByPermission = Object.fromEntries(Object.entries(SYSTEM_MENU_PERMISSION_BY_KEY).map(([key, code]) => [code, key]))
const actionKeyByPermission = Object.fromEntries(Object.entries(SYSTEM_ACTION_PERMISSION_BY_KEY).map(([key, code]) => [code, key]))

function permissionCodesFromSelection(menuKeys = [], buttonKeys = []) {
  return [...new Set([
    ...menuKeys.map((key) => SYSTEM_MENU_PERMISSION_BY_KEY[key]).filter(Boolean),
    ...buttonKeys.map((key) => SYSTEM_ACTION_PERMISSION_BY_KEY[key]).filter(Boolean)
  ])]
}

function selectionFromPermissionCodes(permissionCodes = []) {
  return {
    menuKeys: permissionCodes.map((code) => menuKeyByPermission[code]).filter(Boolean),
    buttonKeys: permissionCodes.map((code) => actionKeyByPermission[code]).filter(Boolean)
  }
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

let seed = 100

/** 写审计：同时进入操作日志与通用留痕区（审计日志只增不删） */
function audit({ module = 'SYSTEM', action, actionLabel, target, summary, before = '', after = '', reason = '', result = 'SUCCESS' }) {
  const entry = {
    id: 'ol-x' + ++seed,
    time: now(),
    who: currentRole.userName,
    roleName: currentRole.roleName,
    module,
    moduleLabel: module === 'EXPORT' ? '导入导出' : '系统管理',
    action,
    actionLabel,
    target,
    result,
    resultLabel: result === 'SUCCESS' ? '成功' : '失败',
    ip: '10.12.*.*',
    detail: { summary, before, after, reason }
  }
  operationLogList.unshift(entry)
  auditLogs.unshift({
    id: 'au-x' + seed,
    who: `${currentRole.userName} · ${currentRole.roleName}`,
    time: entry.time,
    action: `${actionLabel}：${target}`,
    affected: summary
  })
  return entry
}

export const systemApi = {
  /** 品牌 / 角色 / 数据范围 / 权限动作 / 字典 / 列配置（页面初始化统一获取） */
  getContext() {
    return ok({
      tenantBrandConfig: clone(tenantBrandConfig),
      currentRole: clone(currentRole),
      dataScope: clone(dataScope),
      permissionActions: clone(permissionActions),
      statusOptions: clone(statusOptions),
      filterOptions: clone(filterOptions),
      fieldColumns: clone(fieldColumns),
      batchActions: clone(batchActions),
      importTemplates: clone(importTemplates),
      exportOptions: clone(exportOptions)
    })
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
      params: { keyword: params.keyword || undefined, role: params.role || undefined,
        status: params.status || undefined, page: params.page || 1, page_size: params.pageSize || 20 }
    })), mockUsers)
  },

  getUserDetail(id) {
    const preset = userDetailMap[id]
    if (preset) return ok(clone(preset))
    const row = userList.find((u) => u.id === id)
    if (!row) return fail('账号不存在或不在当前数据范围内')
    return ok({
      ...clone(row),
      roles: row.roles.map((code, i) => ({ code, name: row.roleNames[i] || code, scopeName: '按角色默认范围' })),
      contexts: row.roleNames,
      loginHistory: [],
      auditTrail: [{ who: '系统', time: row.createdAt, action: '账号创建', affected: '来源：' + row.source }]
    })
  },

  createUser(payload) {
    if (!payload.name || !payload.userNo) return fail('姓名与工号/账号为必填项')
    if (userList.some((u) => u.userNo === payload.userNo)) return fail('工号/账号已存在：' + payload.userNo)
    const roleNames = (payload.roles || []).map((c) => (filterOptions.roles.find((r) => r.value === c) || { label: c }).label)
    const row = {
      id: 'sys-u-n' + ++seed,
      userNo: payload.userNo,
      name: payload.name,
      orgId: payload.orgId || '',
      orgName: (filterOptions.colleges.find((c) => c.value === payload.orgId) || { label: payload.orgName || '未设置' }).label,
      roles: payload.roles || [],
      roleNames,
      phone: payload.phone || '',
      email: payload.email || '',
      status: 'PENDING',
      statusLabel: '待激活',
      source: '手工创建',
      lastLoginAt: '',
      createdAt: now().slice(0, 10)
    }
    userList.unshift(row)
    audit({ action: 'CREATE', actionLabel: '新增', target: `账号 ${row.userNo}（${row.name}）`, summary: '创建账号，初始状态待激活，首登强制改密' })
    return ok(clone(row))
  },

  updateUser(id, payload) {
    const row = userList.find((u) => u.id === id)
    if (!row) return fail('账号不存在')
    const before = `${row.orgName} · ${row.roleNames.join('/')}`
    Object.assign(row, {
      name: payload.name ?? row.name,
      orgId: payload.orgId ?? row.orgId,
      orgName: payload.orgId ? (filterOptions.colleges.find((c) => c.value === payload.orgId) || { label: row.orgName }).label : row.orgName,
      phone: payload.phone ?? row.phone,
      email: payload.email ?? row.email
    })
    audit({ action: 'UPDATE', actionLabel: '编辑', target: `账号 ${row.userNo}（${row.name}）`, summary: '编辑基础信息', before, after: `${row.orgName} · ${row.roleNames.join('/')}` })
    return ok(clone(row))
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

  batchDisableUsers(ids, { reason }) {
    if (!reason || reason.trim().length < 5) return fail('批量停用原因必填且不少于 5 个字')
    let count = 0
    ids.forEach((id) => {
      const row = userList.find((u) => u.id === id)
      if (row && row.status !== 'DISABLED') {
        row.status = 'DISABLED'
        row.statusLabel = '已停用'
        count++
      }
    })
    audit({ action: 'DISABLE', actionLabel: '停用/作废', target: `批量停用 ${count} 个账号`, summary: '批量停用（逻辑删除，可恢复）', reason })
    return ok({ count })
  },

  /** 导入：返回校验预览（dry-run），confirm=true 时写入并生成回执 */
  importUsers({ fileName, confirm = false }) {
    const preview = {
      batchNo: 'IMP-' + now().slice(0, 10).replaceAll('-', '') + '-02',
      fileName: fileName || '用户账号导入_0704.xlsx',
      total: 14,
      valid: 12,
      invalid: 2,
      errors: [
        { row: 6, field: '工号/账号', message: '与现有账号 T2019035 重复' },
        { row: 11, field: '角色编码', message: '角色 OLD_EXPORTER 已作废，不允许分配' }
      ]
    }
    if (!confirm) return ok(preview)
    audit({ module: 'EXPORT', action: 'IMPORT', actionLabel: '导入', target: `用户账号（批次 ${preview.batchNo}）`, summary: `导入 ${preview.total} 行：成功 ${preview.valid} · 失败 ${preview.invalid}，错误清单已留存` })
    return ok({ ...preview, receipt: `已导入 ${preview.valid} 行，失败 ${preview.invalid} 行（可下载错误清单修正后重新导入）` })
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

  /** 导出：受数据范围限制，敏感字段按选择脱敏，文件带水印，动作留痕 */
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
      return ok({ ...data, ...selectionFromPermissionCodes(data.permissionCodes || []) })
    }, mockDetail)
  },

  getPermissionTree() {
    return ok(clone(permissionTree))
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

  /** 作废角色（逻辑删除）：内置角色禁止作废；有成员需先移除；原因必填留痕 */
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

  async saveRolePermissions(id, { menuKeys, buttonKeys, scopeCode }) {
    try {
      const data = await request(`/system/roles/${encodeURIComponent(id)}/permissions`, {
        method: 'PUT', body: { permissionCodes: permissionCodesFromSelection(menuKeys, buttonKeys), scopeCode }
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

  saveMenu(payload) {
    audit({ action: 'CONFIG', actionLabel: '配置变更', target: `菜单「${payload.name || payload.code}」`, summary: payload.id ? '编辑菜单' : '新增菜单', reason: payload.reason || '' })
    return ok({ ...payload, id: payload.id || 'menu-n' + ++seed })
  },

  setMenuStatus(id, { action, reason }) {
    if (action === 'DISABLE' && (!reason || reason.trim().length < 5)) return fail('停用原因必填且不少于 5 个字')
    function walk(nodes) {
      for (const n of nodes) {
        if (n.id === id) return n
        const hit = n.children && walk(n.children)
        if (hit) return hit
      }
      return null
    }
    const node = walk(menuTree)
    if (!node) return fail('菜单不存在')
    node.status = action === 'DISABLE' ? 'DISABLED' : 'ENABLED'
    node.statusLabel = action === 'DISABLE' ? '停用' : '启用'
    audit({ action: 'DISABLE', actionLabel: action === 'DISABLE' ? '停用/作废' : '启用', target: `菜单「${node.name}」`, summary: action === 'DISABLE' ? '停用菜单（各角色即时不可见，配置保留）' : '恢复启用', reason: reason || '' })
    return ok({ id, status: node.status })
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

  getScopeAffectedUsers(id) {
    return ok(clone(scopeAffectedUsersMap[id] || []))
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

  getPositions() {
    return ok(clone(positionList))
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

  importOrg({ confirm = false } = {}) {
    const preview = { batchNo: 'IMP-ORG-' + now().slice(0, 10).replaceAll('-', ''), total: 8, valid: 8, invalid: 0, errors: [] }
    if (!confirm) return ok(preview)
    audit({ module: 'EXPORT', action: 'IMPORT', actionLabel: '导入', target: `组织结构（批次 ${preview.batchNo}）`, summary: '导入 8 行全部成功' })
    return ok({ ...preview, receipt: '已导入 8 行组织节点' })
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

  /** 登录与安全审计（真实库 t_security_audit_log）。安全敏感：不做 mock 回落，后端失败即报错，绝不展示编造日志。 */
  async getLoginLogs(params = {}) {
    try {
      return ok(await request('/system/login-logs', {
        params: { keyword: params.keyword || undefined, result: params.result || undefined,
          page: params.page || 1, page_size: params.pageSize || 20 }
      }))
    } catch (error) {
      return fail(error.message || '登录日志加载失败')
    }
  },

  /** 操作与权限审计（真实库 t_security_audit_log）。同样不做 mock 回落。 */
  async getOperationLogs(params = {}) {
    try {
      return ok(await request('/system/operation-logs', {
        params: { keyword: params.keyword || undefined, result: params.result || undefined,
          action: params.action || undefined, module: params.module || undefined,
          page: params.page || 1, page_size: params.pageSize || 20 }
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
  }
}

function maskPhone(v) {
  return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
}

export default systemApi
