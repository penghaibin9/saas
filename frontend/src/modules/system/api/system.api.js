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
    return ok(clone(dashboardSummary))
  },

  /* ==================== 用户账号 ==================== */

  getUsers(params = {}) {
    let list = [...userList]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((u) => u.name.includes(kw) || u.userNo.includes(kw) || (u.orgName || '').includes(kw))
    }
    if (params.orgId) list = list.filter((u) => u.orgId === params.orgId)
    if (params.role) list = list.filter((u) => u.roles.includes(params.role))
    if (params.status) list = list.filter((u) => u.status === params.status)
    return ok(paginate(list, params))
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

  /** 停用/启用（逻辑操作，不物理删除；停用原因必填 ≥5 字） */
  setUserStatus(id, { action, reason }) {
    const row = userList.find((u) => u.id === id)
    if (!row) return fail('账号不存在')
    if (action === 'DISABLE' && (!reason || reason.trim().length < 5)) return fail('停用原因必填且不少于 5 个字')
    const map = { DISABLE: ['DISABLED', '已停用'], ENABLE: ['ACTIVE', '启用中'], UNLOCK: ['ACTIVE', '启用中'] }
    if (!map[action]) return fail('非法操作')
    const before = row.statusLabel
    row.status = map[action][0]
    row.statusLabel = map[action][1]
    audit({
      action: 'DISABLE', actionLabel: action === 'DISABLE' ? '停用/作废' : '启用',
      target: `账号 ${row.userNo}（${row.name}）`,
      summary: action === 'DISABLE' ? '停用账号（逻辑删除，可恢复，历史留痕保留）' : action === 'UNLOCK' ? '解锁账号' : '启用账号',
      before, after: row.statusLabel, reason: reason || ''
    })
    return ok({ id, status: row.status, statusLabel: row.statusLabel })
  },

  resetUserPassword(id) {
    const row = userList.find((u) => u.id === id)
    if (!row) return fail('账号不存在')
    audit({ action: 'UPDATE', actionLabel: '重置密码', target: `账号 ${row.userNo}（${row.name}）`, summary: '临时密码已通过短信下发（页面不展示明文），首登强制改密' })
    return ok({ id, notice: '临时密码已发送至账号绑定手机号（' + maskPhone(row.phone) + '），本页不展示明文' })
  },

  assignUserRoles(id, roleCodes) {
    const row = userList.find((u) => u.id === id)
    if (!row) return fail('账号不存在')
    const before = row.roleNames.join('、') || '无'
    row.roles = [...roleCodes]
    row.roleNames = roleCodes.map((c) => (filterOptions.roles.find((r) => r.value === c) || { label: c }).label)
    audit({ action: 'GRANT', actionLabel: '授权变更', target: `账号 ${row.userNo}（${row.name}）`, summary: '调整角色分配', before, after: row.roleNames.join('、') || '无' })
    return ok(clone(row))
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

  /** 导出：受数据范围限制，敏感字段按选择脱敏，文件带水印，动作留痕 */
  exportUsers({ scope, fields, count }) {
    const sensitive = (fields || []).filter((f) => f.sensitive)
    audit({
      module: 'EXPORT', action: 'EXPORT', actionLabel: '导出',
      target: `用户账号（${scope === 'SELECTED' ? '所选 ' + count + ' 条' : scope === 'ALL' ? '数据范围内全部' : '当前筛选结果'}）`,
      summary: `导出字段 ${(fields || []).length} 个（敏感字段 ${sensitive.length} 个已脱敏）· 文件含水印`
    })
    return ok({ fileName: '用户账号导出_' + now().slice(0, 10) + '.xlsx', watermark: `${tenantBrandConfig.watermarkText} · ${currentRole.userName} · ${now()}` })
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
    /* mock fallback 仅用于未启用真实后端的本地演示 */
    /* c8 ignore next */
    if (!payload.name) return fail('角色名称为必填项')
    const row = {
      id: 'role-n' + ++seed,
      code: payload.code || 'CUSTOM_' + seed,
      name: payload.name,
      type: 'CUSTOM',
      typeLabel: '自定义角色',
      memberCount: 0,
      scopeCode: payload.scopeCode || 'COLLEGE',
      scopeName: (statusOptions.scopeTypes.find((s) => s.value === (payload.scopeCode || 'COLLEGE')) || {}).label || '本学院',
      status: 'ENABLED',
      statusLabel: '启用中',
      description: payload.description || '',
      updatedAt: now().slice(0, 10)
    }
    roleList.push(row)
    audit({ action: 'CREATE', actionLabel: '新增', target: `角色「${row.name}」`, summary: '创建自定义角色，默认无菜单权限，需单独配置' })
    return ok(clone(row))
  },

  updateRole(id, payload) {
    const row = roleList.find((r) => r.id === id)
    if (!row) return fail('角色不存在')
    const before = `${row.name} · ${row.description}`
    Object.assign(row, { name: payload.name ?? row.name, description: payload.description ?? row.description, updatedAt: now().slice(0, 10) })
    audit({ action: 'UPDATE', actionLabel: '编辑', target: `角色「${row.name}」`, summary: '编辑角色基础信息', before, after: `${row.name} · ${row.description}` })
    return ok(clone(row))
  },

  async copyRole(id) {
    try {
      const data = await request(`/system/roles/${encodeURIComponent(id)}/copy`, { method: 'POST' })
      return ok(data)
    } catch (error) {
      return fail(error.message || '复制角色失败')
    }
    /* c8 ignore next */
    const src = roleList.find((r) => r.id === id)
    if (!src) return fail('角色不存在')
    const row = { ...clone(src), id: 'role-n' + ++seed, code: src.code + '_COPY', name: src.name + '（副本）', type: 'CUSTOM', typeLabel: '自定义角色', memberCount: 0, updatedAt: now().slice(0, 10) }
    roleList.push(row)
    audit({ action: 'CREATE', actionLabel: '复制角色', target: `角色「${row.name}」`, summary: `由「${src.name}」复制，权限与数据范围一并复制，成员不复制` })
    return ok(clone(row))
  },

  /** 作废角色（逻辑删除）：内置角色禁止作废；有成员需先移除；原因必填留痕 */
  deprecateRole(id, { reason }) {
    const row = roleList.find((r) => r.id === id)
    if (!row) return fail('角色不存在')
    if (row.type === 'BUILTIN') return fail('内置角色不允许作废（平台冻结规则）')
    if (row.memberCount > 0) return fail(`该角色仍有 ${row.memberCount} 个成员，请先移除成员再作废`)
    if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 个字')
    row.status = 'DEPRECATED'
    row.statusLabel = '已作废'
    row.updatedAt = now().slice(0, 10)
    audit({ action: 'DISABLE', actionLabel: '停用/作废', target: `角色「${row.name}」`, summary: '作废角色（逻辑删除，历史授权记录保留）', reason })
    return ok({ id, status: row.status })
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
    /* c8 ignore next */
    const row = roleList.find((r) => r.id === id)
    if (!row) return fail('角色不存在')
    const detail = roleDetailMap[id]
    const before = `菜单 ${(detail?.menuKeys || []).length} · 按钮 ${(detail?.buttonKeys || []).length} · 范围 ${row.scopeName}`
    const nextDetail = detail || { id: row.id, code: row.code, name: row.name, type: row.type, typeLabel: row.typeLabel, status: row.status, statusLabel: row.statusLabel, description: row.description, members: [], auditTrail: [] }
    nextDetail.menuKeys = [...menuKeys]
    nextDetail.buttonKeys = [...buttonKeys]
    nextDetail.scopeCode = scopeCode
    nextDetail.scopeName = (statusOptions.scopeTypes.find((s) => s.value === scopeCode) || {}).label || scopeCode
    if (!detail) roleDetailMap[id] = nextDetail
    row.scopeCode = scopeCode
    row.scopeName = (statusOptions.scopeTypes.find((s) => s.value === scopeCode) || {}).label || scopeCode
    row.updatedAt = now().slice(0, 10)
    audit({ action: 'GRANT', actionLabel: '授权变更', target: `角色「${row.name}」`, summary: '配置菜单/按钮权限与数据范围', before, after: `菜单 ${menuKeys.length} · 按钮 ${buttonKeys.length} · 范围 ${row.scopeName}` })
    return ok({ id })
  },

  exportRoleConfig(id) {
    const row = roleList.find((r) => r.id === id)
    if (!row) return fail('角色不存在')
    audit({ module: 'EXPORT', action: 'EXPORT', actionLabel: '导出', target: `角色配置「${row.name}」`, summary: '导出角色权限配置（JSON，不含成员个人信息），文件含水印' })
    return ok({ fileName: `角色配置_${row.code}.json` })
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

  getScopeRules(params = {}) {
    let list = [...dataScopeRules]
    if (params.status) list = list.filter((r) => r.status === params.status)
    if (params.keyword) list = list.filter((r) => r.name.includes(params.keyword.trim()))
    return ok(paginate(list, { page: 1, pageSize: 50, ...params }))
  },

  saveScopeRule(payload) {
    if (payload.id) {
      const row = dataScopeRules.find((r) => r.id === payload.id)
      if (!row) return fail('规则不存在')
      const before = row.remark
      Object.assign(row, { name: payload.name ?? row.name, remark: payload.remark ?? row.remark, updatedAt: now().slice(0, 10) })
      audit({ action: 'CONFIG', actionLabel: '配置变更', target: `数据范围规则「${row.name}」`, summary: '编辑规则', before, after: row.remark })
      return ok(clone(row))
    }
    const row = {
      id: 'scope-n' + ++seed,
      name: payload.name,
      scopeCode: payload.scopeCode || 'CUSTOM',
      scopeLabel: (statusOptions.scopeTypes.find((s) => s.value === payload.scopeCode) || { label: '自定义' }).label,
      appliedRoles: payload.appliedRoles || [],
      affectedUsers: 0,
      remark: payload.remark || '',
      status: 'ENABLED',
      statusLabel: '启用中',
      updatedAt: now().slice(0, 10)
    }
    dataScopeRules.push(row)
    audit({ action: 'CREATE', actionLabel: '新增', target: `数据范围规则「${row.name}」`, summary: '创建规则，生效前需在角色配置中引用' })
    return ok(clone(row))
  },

  deprecateScopeRule(id, { reason }) {
    const row = dataScopeRules.find((r) => r.id === id)
    if (!row) return fail('规则不存在')
    if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 个字')
    if (row.affectedUsers > 0) return fail(`该规则仍影响 ${row.affectedUsers} 个用户，请先在角色配置中解除引用`)
    row.status = 'DEPRECATED'
    row.statusLabel = '已作废'
    row.updatedAt = now().slice(0, 10)
    audit({ action: 'DISABLE', actionLabel: '停用/作废', target: `数据范围规则「${row.name}」`, summary: '作废规则（逻辑删除，历史引用记录保留）', reason })
    return ok({ id })
  },

  getScopeAffectedUsers(id) {
    return ok(clone(scopeAffectedUsersMap[id] || []))
  },

  exportScopeRules() {
    audit({ module: 'EXPORT', action: 'EXPORT', actionLabel: '导出', target: '数据范围规则清单', summary: '导出规则清单（含引用角色与影响人数），文件含水印' })
    return ok({ fileName: '数据范围规则_' + now().slice(0, 10) + '.xlsx' })
  },

  /* ==================== 组织结构 ==================== */

  getDepartmentTree() {
    return ok(clone(departmentTree))
  },

  getPositions() {
    return ok(clone(positionList))
  },

  saveOrgNode(payload) {
    audit({ action: payload.id ? 'UPDATE' : 'CREATE', actionLabel: payload.id ? '编辑' : '新增', target: `组织「${payload.name}」`, summary: (payload.id ? '编辑' : '新增') + '组织节点（' + (payload.typeLabel || payload.type) + '）' })
    return ok({ ...payload, id: payload.id || 'org-n' + ++seed })
  },

  deprecateOrgNode(id, { name, reason }) {
    if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 个字')
    audit({ action: 'DISABLE', actionLabel: '停用/作废', target: `组织「${name}」`, summary: '作废组织节点（逻辑删除，历史归属关系保留；如有在册成员需先转移）', reason })
    return ok({ id })
  },

  importOrg({ confirm = false } = {}) {
    const preview = { batchNo: 'IMP-ORG-' + now().slice(0, 10).replaceAll('-', ''), total: 8, valid: 8, invalid: 0, errors: [] }
    if (!confirm) return ok(preview)
    audit({ module: 'EXPORT', action: 'IMPORT', actionLabel: '导入', target: `组织结构（批次 ${preview.batchNo}）`, summary: '导入 8 行全部成功' })
    return ok({ ...preview, receipt: '已导入 8 行组织节点' })
  },

  exportOrg() {
    audit({ module: 'EXPORT', action: 'EXPORT', actionLabel: '导出', target: '组织结构', summary: '导出院系/专业/班级结构（不含成员个人信息），文件含水印' })
    return ok({ fileName: '组织结构_' + now().slice(0, 10) + '.xlsx' })
  },

  /* ==================== 系统 / 品牌配置 ==================== */

  getBrandConfig() {
    return ok(clone(brandConfig))
  },

  saveBrandConfig(payload, { reason } = {}) {
    const editable = ['schoolShortName', 'brandColor', 'loginSlogan', 'watermarkText', 'watermarkDensity', 'footerText']
    const changed = []
    editable.forEach((k) => {
      if (payload[k] !== undefined && payload[k] !== brandConfig[k]) {
        changed.push(`${k}: ${brandConfig[k] || '（空）'} → ${payload[k]}`)
        brandConfig[k] = payload[k]
      }
    })
    if (!changed.length) return fail('没有可保存的变更（学校名称/校徽为平台核定项，学校侧不可修改）')
    tenantBrandConfig.brandColor = brandConfig.brandColor
    tenantBrandConfig.watermarkText = brandConfig.watermarkText
    audit({ action: 'CONFIG', actionLabel: '配置变更', target: '租户品牌配置', summary: `变更 ${changed.length} 项`, before: '', after: changed.join('；'), reason: reason || '' })
    return ok(clone(brandConfig))
  },

  getSystemConfigs() {
    return ok(clone(systemConfigList))
  },

  saveSystemConfig(key, valueText, { reason } = {}) {
    const row = systemConfigList.find((c) => c.key === key)
    if (!row) return fail('配置项不存在')
    if (!reason || reason.trim().length < 5) return fail('配置变更原因必填且不少于 5 个字（写入审计）')
    const before = row.valueText
    row.valueText = valueText
    row.updatedAt = now().slice(0, 10)
    row.updatedBy = currentRole.userName
    audit({ action: 'CONFIG', actionLabel: '配置变更', target: `系统配置「${row.name}」`, summary: '修改配置值', before, after: valueText, reason })
    return ok(clone(row))
  },

  exportConfigs() {
    audit({ module: 'EXPORT', action: 'EXPORT', actionLabel: '导出', target: '系统与品牌配置', summary: '导出配置快照（敏感项仅导出策略描述，不含密钥），文件含水印' })
    return ok({ fileName: '系统配置快照_' + now().slice(0, 10) + '.json' })
  },

  /* ==================== 日志（只读 + 导出，禁止删除） ==================== */

  getLoginLogs(params = {}) {
    let list = [...loginLogList]
    if (params.keyword) list = list.filter((l) => l.userName.includes(params.keyword.trim()) || l.userNo.includes(params.keyword.trim()))
    if (params.result) list = list.filter((l) => l.result === params.result)
    return ok(paginate(list, params))
  },

  getOperationLogs(params = {}) {
    let list = [...operationLogList]
    if (params.keyword) list = list.filter((l) => l.who.includes(params.keyword.trim()) || l.target.includes(params.keyword.trim()))
    if (params.module) list = list.filter((l) => l.module === params.module)
    if (params.action) list = list.filter((l) => l.action === params.action)
    if (params.result) list = list.filter((l) => l.result === params.result)
    return ok(paginate(list, params))
  },

  getAuditLogs() {
    return withFallback('audit.logs', () => realApi.getAuditLogs(), () => ok(clone(auditLogs)))
  },

  exportLogs({ tab, scope, fields }) {
    audit({
      module: 'EXPORT', action: 'EXPORT', actionLabel: '导出',
      target: tab === 'login' ? '登录日志' : '操作日志',
      summary: `导出（${scope === 'RANGE_30D' ? '近 30 天' : '当前筛选结果'} · ${(fields || []).length} 个字段），IP/账号固定脱敏，文件含水印`
    })
    return ok({ fileName: (tab === 'login' ? '登录日志_' : '操作日志_') + now().slice(0, 10) + '.xlsx' })
  }
}

function maskPhone(v) {
  return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
}

export default systemApi
