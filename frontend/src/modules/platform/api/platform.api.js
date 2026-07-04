/**
 * 平台运营中心 / 集成开放中心 API（mock 实现）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功。
 * 真实后端阶段仅替换实现，方法签名冻结不变。页面禁止直接 import mocks。
 * 安全底线：不返回任何明文密钥；重置密钥仅返回一次性下发提示；审计日志只增不删。
 */
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
  moduleLicenseList,
  packageList,
  packageDetailMap,
  tenantList,
  tenantDetailMap,
  orderList,
  orderDetailMap,
  authorizationList,
  integrationList,
  integrationDetailMap,
  apiAccessList,
  apiCallLogs,
  webhookList,
  syncTaskList,
  syncTaskDetailMap,
  platformOperationLogs,
  dashboardSummary,
  auditLogs
} from '@/mocks/platform/platform.mock'

const DELAY = 120

function ok(data) {
  return new Promise((resolve) => {
    setTimeout(() => resolve({ code: 0, data, message: 'ok' }), DELAY)
  })
}

function fail(message) {
  return Promise.resolve({ code: 1, data: null, message })
}

function clone(v) {
  return JSON.parse(JSON.stringify(v))
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

let seed = 500

function audit({ module = 'TENANT', moduleLabel = '租户授权', action, actionLabel, target, summary, before = '', after = '', reason = '', result = 'SUCCESS' }) {
  const entry = {
    id: 'pol-x' + ++seed,
    time: now(),
    who: currentRole.userName,
    roleName: currentRole.roleName,
    module,
    moduleLabel,
    action,
    actionLabel,
    target,
    result,
    resultLabel: result === 'SUCCESS' ? '成功' : '失败',
    ip: '172.16.*.*',
    detail: { summary, before, after, reason }
  }
  platformOperationLogs.unshift(entry)
  auditLogs.unshift({
    id: 'pau-x' + seed,
    who: `${currentRole.userName} · ${currentRole.roleName}`,
    time: entry.time,
    action: `${actionLabel}：${target}`,
    affected: summary
  })
  return entry
}

export const platformApi = {
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
      exportOptions: clone(exportOptions),
      moduleLicenseList: clone(moduleLicenseList)
    })
  },

  getDashboardSummary() {
    return ok(clone(dashboardSummary))
  },

  /* ==================== 租户 / 学校 ==================== */

  getTenants(params = {}) {
    let list = [...tenantList]
    if (params.keyword) {
      const kw = params.keyword.trim()
      list = list.filter((t) => t.name.includes(kw) || t.code.toLowerCase().includes(kw.toLowerCase()))
    }
    if (params.region) list = list.filter((t) => t.region === params.region)
    if (params.packageId) list = list.filter((t) => t.packageId === params.packageId)
    if (params.status) list = list.filter((t) => t.status === params.status)
    if (params.csOwner) list = list.filter((t) => t.csOwner === params.csOwner)
    return ok(paginate(list, params))
  },

  /** 租户下拉选项（订单/集成等页面选择用，禁止页面写死租户名） */
  getTenantOptions() {
    return ok(tenantList.filter((t) => t.status !== 'SUSPENDED').map((t) => ({ value: t.id, label: t.name })))
  },

  getTenantDetail(id) {
    const preset = tenantDetailMap[id]
    if (preset) return ok(clone(preset))
    const row = tenantList.find((t) => t.id === id)
    if (!row) return fail('租户不存在或不在当前数据范围内')
    const pkg = packageList.find((p) => p.id === row.packageId)
    return ok({
      ...clone(row),
      remainDays: null,
      implOwnerName: '—',
      usage: {
        students: `${row.studentCount.toLocaleString()} / ${row.studentLimit.toLocaleString()}`,
        teachers: `${row.teacherCount}`,
        storage: '—',
        apiToday: '—'
      },
      brand: {
        schoolName: row.name,
        schoolShortName: row.name.slice(0, 4),
        brandColor: '#2563eb',
        loginSlogan: '',
        watermarkText: row.name + ' · 内部数据',
        footerText: '技术支持：{{platformDisplayName}}'
      },
      moduleLicenses: moduleLicenseList.map((m) => ({
        code: m.code,
        name: m.name,
        enabled: (pkg ? pkg.modules : []).includes(m.code),
        locked: m.required,
        expireAt: row.expireAt
      })).filter((m) => m.enabled || !m.locked),
      orders: orderList.filter((o) => o.tenantId === id).map((o) => ({ orderNo: o.orderNo, typeLabel: o.typeLabel, packageName: o.packageName, period: o.period, statusLabel: o.statusLabel })),
      auditTrail: [{ who: '系统', time: row.createdAt, action: '租户开通', affected: '套餐：' + row.packageName }]
    })
  },

  createTenant(payload) {
    if (!payload.name || !payload.code) return fail('学校名称与租户编码为必填项')
    if (tenantList.some((t) => t.code === payload.code)) return fail('租户编码已存在：' + payload.code)
    const pkg = packageList.find((p) => p.id === payload.packageId)
    const row = {
      id: 'tenant-n' + ++seed,
      code: payload.code,
      name: payload.name,
      region: payload.region || 'EAST',
      regionLabel: (filterOptions.regions.find((r) => r.value === payload.region) || { label: '华东' }).label,
      packageId: payload.packageId || '',
      packageName: pkg ? pkg.name : '未选择',
      moduleCount: pkg ? pkg.modules.length : 0,
      studentCount: 0,
      studentLimit: pkg ? pkg.limits.students : 0,
      teacherCount: 0,
      expireAt: payload.expireAt || '—',
      status: 'TRIAL',
      statusLabel: '试用中',
      csOwner: payload.csOwner || '',
      csOwnerName: (filterOptions.csOwners.find((c) => c.value === payload.csOwner) || { label: '未分配' }).label,
      contactName: payload.contactName || '',
      contactPhone: payload.contactPhone || '',
      createdAt: now().slice(0, 10)
    }
    tenantList.unshift(row)
    audit({ action: 'CREATE', actionLabel: '新增', target: `租户「${row.name}」`, summary: '创建租户（试用中），正式开通需订单授权确认' })
    return ok(clone(row))
  },

  updateTenant(id, payload) {
    const row = tenantList.find((t) => t.id === id)
    if (!row) return fail('租户不存在')
    const before = `${row.regionLabel} · ${row.csOwnerName}`
    if (payload.region) {
      row.region = payload.region
      row.regionLabel = (filterOptions.regions.find((r) => r.value === payload.region) || { label: row.regionLabel }).label
    }
    if (payload.csOwner) {
      row.csOwner = payload.csOwner
      row.csOwnerName = (filterOptions.csOwners.find((c) => c.value === payload.csOwner) || { label: row.csOwnerName }).label
    }
    if (payload.contactName !== undefined) row.contactName = payload.contactName
    if (payload.contactPhone !== undefined) row.contactPhone = payload.contactPhone
    audit({ action: 'UPDATE', actionLabel: '编辑', target: `租户「${row.name}」`, summary: '编辑租户基础信息', before, after: `${row.regionLabel} · ${row.csOwnerName}` })
    return ok(clone(row))
  },

  /** 停用/恢复租户（逻辑操作；到期锁写由系统自动执行） */
  setTenantStatus(id, { action, reason }) {
    const row = tenantList.find((t) => t.id === id)
    if (!row) return fail('租户不存在')
    if (action === 'SUSPEND' && (!reason || reason.trim().length < 5)) return fail('停用原因必填且不少于 5 个字')
    const before = row.statusLabel
    if (action === 'SUSPEND') {
      row.status = 'SUSPENDED'
      row.statusLabel = '已停用'
    } else {
      row.status = 'ACTIVE'
      row.statusLabel = '正式有效'
    }
    audit({
      action: 'DISABLE', actionLabel: action === 'SUSPEND' ? '停用/作废' : '恢复启用',
      target: `租户「${row.name}」`,
      summary: action === 'SUSPEND' ? '停用租户：普通用户不可进入，管理员可导出，数据完整保留' : '恢复租户',
      before, after: row.statusLabel, reason: reason || ''
    })
    return ok({ id, status: row.status, statusLabel: row.statusLabel })
  },

  saveTenantBrand(id, brand, { reason } = {}) {
    const detail = tenantDetailMap[id]
    const row = tenantList.find((t) => t.id === id)
    if (!row) return fail('租户不存在')
    if (detail) detail.brand = { ...detail.brand, ...brand }
    audit({ action: 'CONFIG', actionLabel: '配置变更', target: `租户「${row.name}」品牌配置`, summary: '更新品牌项（简称/主色/口号/水印）', reason: reason || '' })
    return ok({ id })
  },

  /** 模块授权开关（底座模块 locked 不可关；变更留痕） */
  toggleTenantModule(id, { code, name, enabled, reason }) {
    const row = tenantList.find((t) => t.id === id)
    if (!row) return fail('租户不存在')
    const detail = tenantDetailMap[id]
    if (detail) {
      const m = detail.moduleLicenses.find((x) => x.code === code)
      if (m && m.locked) return fail('底座模块（' + name + '）随套餐必含，不可单独关闭')
      if (m) m.enabled = enabled
    }
    if (!enabled && (!reason || reason.trim().length < 5)) return fail('关闭模块需填写原因（≥5 字）并留痕')
    audit({
      action: 'GRANT', actionLabel: '授权变更', target: `租户「${row.name}」· ${name}`,
      summary: enabled ? '开通模块（即时生效）' : '关闭模块（菜单灰显 / 新增拦截 / 历史可读）',
      before: enabled ? '未开通' : '已开通', after: enabled ? '已开通' : '已关闭', reason: reason || ''
    })
    return ok({ id, code, enabled })
  },

  importTenants({ fileName, confirm = false }) {
    const preview = {
      batchNo: 'IMP-TEN-' + now().slice(0, 10).replaceAll('-', ''),
      fileName: fileName || '租户开通导入_0704.xlsx',
      total: 3,
      valid: 2,
      invalid: 1,
      errors: [{ row: 3, field: '套餐编码', message: '套餐 pkg-99 不存在或未上架' }]
    }
    if (!confirm) return ok(preview)
    audit({ module: 'EXPORT', moduleLabel: '导入导出', action: 'IMPORT', actionLabel: '导入', target: `租户（批次 ${preview.batchNo}）`, summary: `导入 ${preview.total} 行：成功 ${preview.valid} · 失败 ${preview.invalid}，新租户为「待开通」状态` })
    return ok({ ...preview, receipt: `已导入 ${preview.valid} 行（待开通），失败 ${preview.invalid} 行可下载错误清单` })
  },

  exportTenants({ scope, fields, count }) {
    const sensitive = (fields || []).filter((f) => f.sensitive)
    audit({
      module: 'EXPORT', moduleLabel: '导入导出', action: 'EXPORT', actionLabel: '导出',
      target: `租户清单（${scope === 'SELECTED' ? '所选 ' + count + ' 条' : scope === 'ALL' ? '数据范围内全部' : '当前筛选结果'}）`,
      summary: `导出字段 ${(fields || []).length} 个（敏感 ${sensitive.length} 个已脱敏）· 文件含水印`
    })
    return ok({ fileName: '租户清单_' + now().slice(0, 10) + '.xlsx' })
  },

  batchRemindRenew(ids) {
    audit({ action: 'UPDATE', actionLabel: '续费提醒', target: `批量提醒 ${ids.length} 个租户`, summary: '站内信 + 短信触达租户管理员与客户成功负责人' })
    return ok({ count: ids.length })
  },

  /* ==================== 套餐 ==================== */

  getPackages(params = {}) {
    let list = [...packageList]
    if (params.keyword) list = list.filter((p) => p.name.includes(params.keyword.trim()))
    return ok(paginate(list, { page: 1, pageSize: 20, ...params }))
  },

  getPackageDetail(id) {
    const row = packageList.find((p) => p.id === id)
    if (!row) return fail('套餐不存在')
    const extra = packageDetailMap[id] || { auditTrail: [] }
    return ok({ ...clone(row), ...clone(extra) })
  },

  savePackage(payload) {
    if (payload.id) {
      const row = packageList.find((p) => p.id === payload.id)
      if (!row) return fail('套餐不存在')
      const before = `${row.modules.length} 模块 · 学生上限 ${row.limits.students}`
      Object.assign(row, {
        name: payload.name ?? row.name,
        positioning: payload.positioning ?? row.positioning,
        modules: payload.modules ?? row.modules,
        limits: { ...row.limits, ...(payload.limits || {}) },
        updatedAt: now().slice(0, 10)
      })
      audit({ module: 'PACKAGE', moduleLabel: '套餐管理', action: 'UPDATE', actionLabel: '编辑', target: `套餐「${row.name}」`, summary: '编辑套餐定义', before, after: `${row.modules.length} 模块 · 学生上限 ${row.limits.students}` })
      return ok(clone(row))
    }
    const row = {
      id: 'pkg-n' + ++seed,
      name: payload.name,
      positioning: payload.positioning || '',
      modules: payload.modules || [],
      limits: { students: 3000, teachers: 300, storageGB: 100, apiQpd: 50000, ...(payload.limits || {}) },
      priceNote: payload.priceNote || '按年订阅（演示口径）',
      status: 'ENABLED',
      statusLabel: '上架中',
      tenantCount: 0,
      updatedAt: now().slice(0, 10)
    }
    packageList.push(row)
    audit({ module: 'PACKAGE', moduleLabel: '套餐管理', action: 'CREATE', actionLabel: '新增', target: `套餐「${row.name}」`, summary: '创建套餐（上架中）' })
    return ok(clone(row))
  },

  disablePackage(id, { reason }) {
    const row = packageList.find((p) => p.id === id)
    if (!row) return fail('套餐不存在')
    if (row.tenantCount > 0) return fail(`该套餐仍有 ${row.tenantCount} 个在用租户，停用后仅停止新售，存量授权不受影响；请确认后再操作`)
    if (!reason || reason.trim().length < 5) return fail('停用原因必填且不少于 5 个字')
    row.status = 'DISABLED'
    row.statusLabel = '已停售'
    audit({ module: 'PACKAGE', moduleLabel: '套餐管理', action: 'DISABLE', actionLabel: '停用/作废', target: `套餐「${row.name}」`, summary: '停售套餐（逻辑操作，存量租户不受影响）', reason })
    return ok({ id })
  },

  exportPackageConfig(id) {
    const row = packageList.find((p) => p.id === id)
    if (!row) return fail('套餐不存在')
    audit({ module: 'EXPORT', moduleLabel: '导入导出', action: 'EXPORT', actionLabel: '导出', target: `套餐配置「${row.name}」`, summary: '导出套餐模块与限制配置（JSON），文件含水印' })
    return ok({ fileName: `套餐配置_${row.id}.json` })
  },

  /* ==================== 订单 / 授权 ==================== */

  getOrders(params = {}) {
    let list = [...orderList]
    if (params.keyword) list = list.filter((o) => o.orderNo.includes(params.keyword.trim()) || o.tenantName.includes(params.keyword.trim()))
    if (params.type) list = list.filter((o) => o.type === params.type)
    if (params.status) list = list.filter((o) => o.status === params.status)
    return ok(paginate(list, params))
  },

  getOrderDetail(id) {
    const row = orderList.find((o) => o.id === id)
    if (!row) return fail('订单不存在')
    const extra = orderDetailMap[id] || { auditTrail: [{ who: row.createdBy, time: row.createdAt, action: '创建订单', affected: row.remark || '—' }] }
    return ok({ ...clone(row), ...clone(extra) })
  },

  createOrder(payload) {
    if (!payload.tenantId || !payload.type) return fail('租户与订单类型为必填项')
    const tenant = tenantList.find((t) => t.id === payload.tenantId)
    if (!tenant) return fail('租户不存在')
    const row = {
      id: 'ord-n' + ++seed,
      orderNo: 'ORD-' + now().slice(0, 10).replaceAll('-', '') + '-0' + (seed % 90),
      tenantId: tenant.id,
      tenantName: tenant.name,
      type: payload.type,
      typeLabel: (statusOptions.orderTypes.find((t) => t.value === payload.type) || {}).label || payload.type,
      packageName: payload.packageName || tenant.packageName,
      amountMasked: '¥ ***（录入后仅财务可见明文）',
      period: payload.period || '—',
      status: 'PENDING_ACTIVATE',
      statusLabel: '待开通',
      createdAt: now().slice(0, 10),
      createdBy: currentRole.userName,
      remark: payload.remark || ''
    }
    orderList.unshift(row)
    audit({ module: 'ORDER', moduleLabel: '订单授权', action: 'CREATE', actionLabel: '新增', target: `订单 ${row.orderNo}（${tenant.name}）`, summary: `${row.typeLabel} · ${row.packageName} · 待开通` })
    return ok(clone(row))
  },

  updateOrderRemark(id, remark) {
    const row = orderList.find((o) => o.id === id)
    if (!row) return fail('订单不存在')
    const before = row.remark || '（空）'
    row.remark = remark
    audit({ module: 'ORDER', moduleLabel: '订单授权', action: 'UPDATE', actionLabel: '编辑', target: `订单 ${row.orderNo}`, summary: '编辑订单备注', before, after: remark })
    return ok(clone(row))
  },

  /** 授权开通：订单生效 + 租户续期 */
  activateOrder(id) {
    const row = orderList.find((o) => o.id === id)
    if (!row) return fail('订单不存在')
    if (row.status !== 'PENDING_ACTIVATE') return fail('仅「待开通」订单可执行开通')
    row.status = 'ACTIVE'
    row.statusLabel = '已开通'
    const tenant = tenantList.find((t) => t.id === row.tenantId)
    if (tenant && row.period.includes('~')) {
      tenant.expireAt = row.period.split('~')[1].trim()
      tenant.status = 'ACTIVE'
      tenant.statusLabel = '正式有效'
    }
    authorizationList.unshift({
      id: 'auth-n' + ++seed,
      tenantName: row.tenantName,
      moduleName: row.packageName,
      actionLabel: row.type === 'RENEW' ? '续期开通' : '整包开通',
      validUntil: tenant ? tenant.expireAt : '—',
      operator: currentRole.userName,
      time: now()
    })
    audit({ module: 'ORDER', moduleLabel: '订单授权', action: 'GRANT', actionLabel: '授权开通', target: `订单 ${row.orderNo}（${row.tenantName}）`, summary: '订单开通并同步租户有效期 / 模块授权' })
    return ok({ id, status: row.status })
  },

  voidOrder(id, { reason }) {
    const row = orderList.find((o) => o.id === id)
    if (!row) return fail('订单不存在')
    if (row.status === 'ACTIVE') return fail('已开通订单不可直接作废，请先执行授权回收流程')
    if (!reason || reason.trim().length < 5) return fail('作废原因必填且不少于 5 个字')
    row.status = 'VOID'
    row.statusLabel = '已作废'
    row.remark = '作废原因：' + reason
    audit({ module: 'ORDER', moduleLabel: '订单授权', action: 'DISABLE', actionLabel: '停用/作废', target: `订单 ${row.orderNo}`, summary: '作废订单（逻辑删除，流水保留）', reason })
    return ok({ id })
  },

  getAuthorizations() {
    return ok(clone(authorizationList))
  },

  exportOrders({ scope, fields }) {
    audit({ module: 'EXPORT', moduleLabel: '导入导出', action: 'EXPORT', actionLabel: '导出', target: `订单（${scope === 'RANGE_90D' ? '近 90 天' : '当前筛选结果'}）`, summary: `导出字段 ${(fields || []).length} 个（金额脱敏为区间）· 文件含水印` })
    return ok({ fileName: '订单导出_' + now().slice(0, 10) + '.xlsx' })
  },

  /* ==================== 集成开放 ==================== */

  getIntegrations(params = {}) {
    let list = [...integrationList]
    if (params.keyword) list = list.filter((i) => i.name.includes(params.keyword.trim()) || i.tenantName.includes(params.keyword.trim()))
    if (params.type) list = list.filter((i) => i.type === params.type)
    if (params.health) list = list.filter((i) => i.health === params.health)
    if (params.status) list = list.filter((i) => i.status === params.status)
    return ok(paginate(list, params))
  },

  getIntegrationDetail(id) {
    const preset = integrationDetailMap[id]
    if (preset) return ok(clone(preset))
    const row = integrationList.find((i) => i.id === id)
    if (!row) return fail('集成不存在')
    return ok({
      ...clone(row),
      endpoint: '（演示地址）', appKeyMasked: 'AK-****', secretMasked: '••••••••（已加密存储，页面不展示明文）',
      ipWhitelist: [], signAlg: 'HMAC-SHA256', timeoutMs: 3000,
      healthChecks: [], recentErrors: [],
      auditTrail: [{ who: row.owner, time: '—', action: '登记接入', affected: row.typeLabel }]
    })
  },

  saveIntegration(payload) {
    if (payload.id) {
      const row = integrationList.find((i) => i.id === payload.id)
      if (!row) return fail('集成不存在')
      Object.assign(row, { name: payload.name ?? row.name, owner: payload.owner ?? row.owner })
      audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'CONFIG', actionLabel: '配置变更', target: `集成「${row.name}」`, summary: '编辑集成配置（密钥不变更）' })
      return ok(clone(row))
    }
    if (!payload.name || !payload.type) return fail('系统名称与类型为必填项')
    const row = {
      id: 'itg-n' + ++seed,
      name: payload.name,
      tenantId: payload.tenantId || 'platform-operator',
      tenantName: payload.tenantName || '平台公共通道',
      type: payload.type,
      typeLabel: (filterOptions.integrationTypes.find((t) => t.value === payload.type) || {}).label || payload.type,
      authType: payload.authType || 'AppKey + 签名',
      health: 'HEALTHY',
      healthLabel: '正常',
      todayCalls: 0,
      failCalls: 0,
      lastCallAt: '—',
      owner: payload.owner || currentRole.userName,
      status: 'ENABLED',
      statusLabel: '启用中'
    }
    integrationList.unshift(row)
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'CREATE', actionLabel: '新增', target: `集成「${row.name}」`, summary: '登记外部系统（凭证已加密存储，页面不展示明文）' })
    return ok(clone(row))
  },

  setIntegrationStatus(id, { action, reason }) {
    const row = integrationList.find((i) => i.id === id)
    if (!row) return fail('集成不存在')
    if (action === 'DISABLE' && (!reason || reason.trim().length < 5)) return fail('停用原因必填且不少于 5 个字')
    row.status = action === 'DISABLE' ? 'DISABLED' : 'ENABLED'
    row.statusLabel = action === 'DISABLE' ? '已停用' : '启用中'
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'DISABLE', actionLabel: action === 'DISABLE' ? '停用/作废' : '恢复启用', target: `集成「${row.name}」`, summary: action === 'DISABLE' ? '停用集成：调用即时拦截，配置与日志保留' : '恢复集成', reason: reason || '' })
    return ok({ id, status: row.status })
  },

  testIntegration(id) {
    const row = integrationList.find((i) => i.id === id)
    if (!row) return fail('集成不存在')
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'TEST', actionLabel: '测试连接', target: `集成「${row.name}」`, summary: `健康检查：${row.healthLabel}` })
    return ok({ id, health: row.health, healthLabel: row.healthLabel, message: row.health === 'HEALTHY' ? '连通性 / 认证 / 接口均正常' : row.health === 'WARNING' ? '可连通，但存在字段映射缺失或错误率偏高' : '连接失败，请检查地址与凭证' })
  },

  exportIntegrations() {
    audit({ module: 'EXPORT', moduleLabel: '导入导出', action: 'EXPORT', actionLabel: '导出', target: '集成配置清单', summary: '导出集成配置（不含任何密钥明文），文件含水印' })
    return ok({ fileName: '集成配置_' + now().slice(0, 10) + '.xlsx' })
  },

  /* ==================== API 访问 / Webhook ==================== */

  getApiAccessList(params = {}) {
    let list = [...apiAccessList]
    if (params.keyword) list = list.filter((a) => a.appName.includes(params.keyword.trim()) || a.tenantName.includes(params.keyword.trim()))
    if (params.status) list = list.filter((a) => a.status === params.status)
    return ok(paginate(list, params))
  },

  saveApiAccess(payload) {
    if (payload.id) {
      const row = apiAccessList.find((a) => a.id === payload.id)
      if (!row) return fail('配置不存在')
      Object.assign(row, {
        appName: payload.appName ?? row.appName,
        ipWhitelist: payload.ipWhitelist ?? row.ipWhitelist,
        dataScopeLabel: payload.dataScopeLabel ?? row.dataScopeLabel
      })
      audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'CONFIG', actionLabel: '配置变更', target: `API 应用「${row.appName}」`, summary: '编辑访问配置（AppKey / Secret 不变更）' })
      return ok(clone(row))
    }
    if (!payload.appName) return fail('应用名称为必填项')
    const row = {
      id: 'api-n' + ++seed,
      appName: payload.appName,
      tenantName: payload.tenantName || '平台公共通道',
      appKeyMasked: 'AK-' + Math.random().toString(16).slice(2, 6) + '****' + Math.random().toString(16).slice(2, 6),
      secretMasked: '••••••••（已加密存储）',
      apiScopes: payload.apiScopes || [],
      dataScopeLabel: payload.dataScopeLabel || '按授权范围',
      ipWhitelist: payload.ipWhitelist || '—',
      validUntil: payload.validUntil || '—',
      todayCalls: 0,
      status: 'ENABLED',
      statusLabel: '启用中'
    }
    apiAccessList.unshift(row)
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'CREATE', actionLabel: '新增', target: `API 应用「${row.appName}」`, summary: 'AppSecret 已通过安全信道一次性下发，系统仅存密文' })
    return ok(clone(row))
  },

  /** 重置密钥：高危，双人复核 + 一次性下发，页面永不展示明文 */
  resetApiSecret(id, { reason }) {
    const row = apiAccessList.find((a) => a.id === id)
    if (!row) return fail('配置不存在')
    if (!reason || reason.trim().length < 5) return fail('重置原因必填且不少于 5 个字')
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'CONFIG', actionLabel: '重置密钥', target: `API 应用「${row.appName}」`, summary: '旧密钥立即失效；新密钥通过安全信道一次性下发（页面不展示明文）', reason })
    return ok({ id, notice: '新密钥已通过安全信道下发给对接责任人，旧密钥即时失效；本次操作已双人复核留痕' })
  },

  setApiAccessStatus(id, { action, reason }) {
    const row = apiAccessList.find((a) => a.id === id)
    if (!row) return fail('配置不存在')
    if (action === 'DISABLE' && (!reason || reason.trim().length < 5)) return fail('停用原因必填且不少于 5 个字')
    row.status = action === 'DISABLE' ? 'DISABLED' : 'ENABLED'
    row.statusLabel = action === 'DISABLE' ? '已停用' : '启用中'
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'DISABLE', actionLabel: action === 'DISABLE' ? '停用/作废' : '恢复启用', target: `API 应用「${row.appName}」`, summary: action === 'DISABLE' ? '停用后调用即时 403，配置与日志保留' : '恢复访问', reason: reason || '' })
    return ok({ id, status: row.status })
  },

  getApiCallLogs() {
    return ok(clone(apiCallLogs))
  },

  exportApiLogs() {
    audit({ module: 'EXPORT', moduleLabel: '导入导出', action: 'EXPORT', actionLabel: '导出', target: 'API 调用日志', summary: '导出调用日志（AppKey 脱敏），文件含水印' })
    return ok({ fileName: 'API调用日志_' + now().slice(0, 10) + '.xlsx' })
  },

  getWebhooks(params = {}) {
    let list = [...webhookList]
    if (params.keyword) list = list.filter((w) => w.name.includes(params.keyword.trim()))
    return ok(paginate(list, { page: 1, pageSize: 20, ...params }))
  },

  saveWebhook(payload) {
    if (payload.id) {
      const row = webhookList.find((w) => w.id === payload.id)
      if (!row) return fail('订阅不存在')
      Object.assign(row, { name: payload.name ?? row.name, retryPolicy: payload.retryPolicy ?? row.retryPolicy })
      audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'CONFIG', actionLabel: '配置变更', target: `Webhook「${row.name}」`, summary: '编辑订阅（签名密钥不变更）' })
      return ok(clone(row))
    }
    if (!payload.name || !payload.url) return fail('订阅名称与回调地址为必填项')
    const row = {
      id: 'wh-n' + ++seed,
      name: payload.name,
      tenantName: payload.tenantName || '平台公共通道',
      urlMasked: payload.url.replace(/(https?:\/\/[^/]+\/).*/, '$1****'),
      events: payload.events || [],
      signKeyMasked: 'SK-****（已加密存储）',
      retryPolicy: payload.retryPolicy || '指数退避 · 最多 5 次',
      lastDelivery: '—',
      failCount24h: 0,
      status: 'ENABLED',
      statusLabel: '启用中'
    }
    webhookList.unshift(row)
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'CREATE', actionLabel: '新增', target: `Webhook「${row.name}」`, summary: '签名密钥一次性下发，系统仅存密文' })
    return ok(clone(row))
  },

  setWebhookStatus(id, { action, reason }) {
    const row = webhookList.find((w) => w.id === id)
    if (!row) return fail('订阅不存在')
    if (action === 'DISABLE' && (!reason || reason.trim().length < 5)) return fail('停用原因必填且不少于 5 个字')
    row.status = action === 'DISABLE' ? 'DISABLED' : 'ENABLED'
    row.statusLabel = action === 'DISABLE' ? '已停用' : '启用中'
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'DISABLE', actionLabel: action === 'DISABLE' ? '停用/作废' : '恢复启用', target: `Webhook「${row.name}」`, summary: action === 'DISABLE' ? '停止事件投递，历史投递日志保留' : '恢复投递', reason: reason || '' })
    return ok({ id, status: row.status })
  },

  redeliverWebhook(id) {
    const row = webhookList.find((w) => w.id === id)
    if (!row) return fail('订阅不存在')
    row.lastDelivery = now() + ' · 重推成功'
    row.failCount24h = 0
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'UPDATE', actionLabel: '手动重推', target: `Webhook「${row.name}」`, summary: '失败事件重推成功，失败计数清零' })
    return ok({ id, lastDelivery: row.lastDelivery })
  },

  /* ==================== 同步任务 / 平台日志 ==================== */

  getSyncTasks(params = {}) {
    let list = [...syncTaskList]
    if (params.keyword) list = list.filter((s) => s.name.includes(params.keyword.trim()) || s.tenantName.includes(params.keyword.trim()))
    if (params.object) list = list.filter((s) => s.object === params.object)
    if (params.status) list = list.filter((s) => s.status === params.status)
    return ok(paginate(list, params))
  },

  getSyncTaskDetail(id) {
    const preset = syncTaskDetailMap[id]
    if (preset) return ok(clone(preset))
    const row = syncTaskList.find((s) => s.id === id)
    if (!row) return fail('任务不存在')
    return ok({
      ...clone(row), batchNo: '—',
      flow: '外部系统 → 字段映射 → 暂存区 → 校验 → 身份匹配 → 业务表写入 → 日志',
      runs: [{ time: row.lastRunAt, resultLabel: row.statusLabel, detail: row.lastResult, tone: row.failRows > 0 ? 'danger' : 'success' }],
      failedRows: [], suggestion: '',
      auditTrail: []
    })
  },

  /** 重试失败任务：幂等，仅处理失败行 */
  retrySyncTask(id) {
    const row = syncTaskList.find((s) => s.id === id)
    if (!row) return fail('任务不存在')
    if (row.failRows === 0) return fail('该任务没有失败行，无需重试')
    const failed = row.failRows
    row.failRows = 0
    row.successRows += failed
    row.status = 'ENABLED'
    row.statusLabel = '运行中'
    row.lastResult = `重试成功 ${failed} 行 · 失败 0`
    row.lastRunAt = now()
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'UPDATE', actionLabel: '重试任务', target: `同步任务「${row.name}」（${row.tenantName}）`, summary: `仅重试失败行 ${failed} 行（幂等），全部成功` })
    return ok({ id, retried: failed })
  },

  setSyncTaskStatus(id, { action, reason }) {
    const row = syncTaskList.find((s) => s.id === id)
    if (!row) return fail('任务不存在')
    if (action === 'DISABLE' && (!reason || reason.trim().length < 5)) return fail('停用原因必填且不少于 5 个字')
    row.status = action === 'DISABLE' ? 'PAUSED' : 'ENABLED'
    row.statusLabel = action === 'DISABLE' ? '已暂停' : '运行中'
    audit({ module: 'INTEGRATION', moduleLabel: '集成开放', action: 'DISABLE', actionLabel: action === 'DISABLE' ? '停用/作废' : '恢复启用', target: `同步任务「${row.name}」`, summary: action === 'DISABLE' ? '暂停调度，历史执行记录保留' : '恢复调度', reason: reason || '' })
    return ok({ id, status: row.status })
  },

  exportSyncLogs() {
    audit({ module: 'EXPORT', moduleLabel: '导入导出', action: 'EXPORT', actionLabel: '导出', target: '同步任务日志', summary: '导出执行记录与失败明细（学号脱敏），文件含水印' })
    return ok({ fileName: '同步任务日志_' + now().slice(0, 10) + '.xlsx' })
  },

  getPlatformLogs(params = {}) {
    let list = [...platformOperationLogs]
    if (params.keyword) list = list.filter((l) => l.who.includes(params.keyword.trim()) || l.target.includes(params.keyword.trim()))
    if (params.module) list = list.filter((l) => l.module === params.module)
    if (params.result) list = list.filter((l) => l.result === params.result)
    return ok(paginate(list, params))
  },

  getAuditLogs() {
    return ok(clone(auditLogs))
  },

  exportPlatformLogs({ scope, fields }) {
    audit({ module: 'EXPORT', moduleLabel: '导入导出', action: 'EXPORT', actionLabel: '导出', target: `平台操作日志（${scope === 'RANGE_30D' ? '近 30 天' : '当前筛选结果'}）`, summary: `导出字段 ${(fields || []).length} 个（IP 固定脱敏）· 文件含水印` })
    return ok({ fileName: '平台操作日志_' + now().slice(0, 10) + '.xlsx' })
  }
}

export default platformApi
