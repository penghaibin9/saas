/** UI-only contracts. Authorization and business state remain server-owned. */
export function actionAllowed(ctx, key) {
  const value = ctx?.permissionActions?.[key]
  return value?.visible === true && value?.allowed === true
}

export function contextFingerprint(ctx = {}) {
  const access = ctx.permissionActions?.effectiveAccess || ctx
  return JSON.stringify([
    access.tenantId ?? null, access.subjectId ?? ctx.currentRole?.userId ?? null,
    access.activeContextId ?? null, ctx.currentRole?.roleCode ?? null,
    access.permissionVersion ?? null, access.securityRevision ?? null,
    access.permissionDigest ?? null, access.ctxKey ?? null
  ])
}

/** Each channel ignores late reads, including after unmount/context replacement. */
export function createRequestFence() {
  let generation = 0
  const requests = new Map()
  return {
    start(channel) {
      const id = (requests.get(channel) || 0) + 1
      const stamp = generation
      requests.set(channel, id)
      return () => stamp === generation && requests.get(channel) === id
    },
    invalidate() { generation += 1; requests.clear() }
  }
}

export function unwrap(result) {
  if (!result || result.code !== 0) {
    const error = new Error(result?.message || '未取得服务端结果，请重新读取后核对')
    error.bizCode = result?.bizCode || ''
    error.details = result?.details
    error.traceId = result?.traceId || ''
    throw error
  }
  return result.data
}

export function paged(data, key = 'items') {
  if (!data || !Array.isArray(data[key]) || !Number.isInteger(data.total) || data.total < 0
    || !Number.isInteger(data.page) || data.page < 1
    || !Number.isInteger(data.pageSize) || data.pageSize < 1) {
    throw new Error('分页结果不完整，不能将当前页当成完整清单')
  }
  return { rows: data[key], total: data.total, page: data.page, pageSize: data.pageSize }
}

export function concreteCodes(values) {
  if (!Array.isArray(values) || values.some(value => typeof value !== 'string' || !value.trim())) {
    throw new Error('权限数据结构异常，已暂停编辑')
  }
  return [...new Set(values)]
}

export function permissionGroups(tree) {
  if (!Array.isArray(tree)) throw new Error('权限目录未取得')
  const seen = new Set()
  return tree.map(group => {
    if (!group?.key || !Array.isArray(group.children)) throw new Error('权限目录结构异常')
    const rows = []
    for (const menu of group.children) {
      if (!menu?.key || !Array.isArray(menu.children)) throw new Error('权限目录结构异常')
      const nodes = [{ ...menu, parentKey: null, selectionType: 'menu' },
        ...menu.children.map(button => ({ ...button, parentKey: menu.key, selectionType: 'button' }))]
      for (const node of nodes) {
        if (typeof node.key !== 'string' || seen.has(node.key)) throw new Error('权限目录存在无效或重复编码')
        seen.add(node.key)
        rows.push(node)
      }
    }
    return { key: group.key, label: group.label, rows }
  })
}

export function makePermissionDraft(tree, detail, roleId) {
  if (!detail || String(detail.id) !== String(roleId)) throw new Error('角色详情与当前选择不一致')
  if (!Number.isInteger(detail.version) || detail.version < 0) throw new Error('未取得有效角色版本，请重新读取')
  const groups = permissionGroups(tree)
  const granted = concreteCodes(detail.permissionCodes)
  const nodes = groups.flatMap(group => group.rows)
  return {
    groups,
    menuKeys: nodes.filter(node => node.selectionType === 'menu' && granted.includes(node.key)).map(node => node.key),
    buttonKeys: nodes.filter(node => node.selectionType === 'button' && granted.includes(node.key)).map(node => node.key),
    scopeCode: detail.scopeCode,
    version: detail.version
  }
}

export function permissionDelta(before, after) {
  const old = concreteCodes(before)
  const next = concreteCodes(after)
  return { added: next.filter(code => !old.includes(code)), removed: old.filter(code => !next.includes(code)) }
}

/** Preserve the existing menu/child selection semantics; never mutate readonly codes. */
export function changePermission(draft, node, checked) {
  const next = { ...draft, menuKeys: [...draft.menuKeys], buttonKeys: [...draft.buttonKeys] }
  if (node.selectionType === 'button') {
    if (checked && !next.menuKeys.includes(node.parentKey)) return next
    next.buttonKeys = next.buttonKeys.filter(code => code !== node.key)
    if (checked) next.buttonKeys.push(node.key)
  } else {
    next.menuKeys = next.menuKeys.filter(code => code !== node.key)
    if (checked) next.menuKeys.push(node.key)
    else {
      const children = new Set((node.children || []).map(child => child.key))
      next.buttonKeys = next.buttonKeys.filter(code => !children.has(code))
    }
  }
  return next
}

export function newRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  if (!globalThis.crypto?.getRandomValues) throw new Error('浏览器不支持安全请求编号，请使用受支持的 HTTPS 浏览器')
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 15) | 64
  bytes[8] = (bytes[8] & 63) | 128
  const hex = [...bytes].map(value => value.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

/** Arguments for systemApi.saveRolePermissions, NOT an alternative HTTP client. */
export function permissionSaveArgs(draft, reason, requestId) {
  const menuKeys = concreteCodes(draft.menuKeys)
  const buttonKeys = concreteCodes(draft.buttonKeys)
  const codes = [...new Set([...menuKeys, ...buttonKeys])]
  const editable = new Set(draft.groups.flatMap(group => group.rows.map(node => node.key)))
  if (codes.some(code => !editable.has(code) || code.includes('*') || /^(system\.|platform\.|enterprise\.)/.test(code))) {
    throw new Error('包含不可编辑权限，必须重新取得服务端权限目录')
  }
  if (!Number.isInteger(draft.version) || draft.version < 0) throw new Error('角色版本无效')
  if (typeof draft.scopeCode !== 'string' || !draft.scopeCode) throw new Error('未取得默认数据范围')
  if (typeof reason !== 'string' || reason.trim().length < 5) throw new Error('调整原因至少 5 个字符')
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(requestId || '')) {
    throw new Error('请求编号必须是 UUID')
  }
  // This editor does not edit CUSTOM targets. Absence preserves the server target.
  return { menuKeys, buttonKeys, scopeCode: draft.scopeCode, expectedVersion: draft.version, reason: reason.trim(), requestId }
}

export function capabilityCanConfirm({ canWrite, busy, item, enabled, impactState, impact, contextMatches }) {
  if (!canWrite || busy || !contextMatches || typeof enabled !== 'boolean'
    || !item || !Number.isInteger(item.version) || item.version < 0) return false
  if (enabled) return item.entitled === true && !(item.dependencyUnmet || []).length
  return impactState === 'ready' && impact?.capabilityKey === item.capabilityKey
}

export function countLabel(value) {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? String(value) : '未取得'
}

export function visibleMenuPreview(groups, menuKeys) {
  return groups.flatMap(group => group.rows).filter(node => node.selectionType === 'menu'
    && !node.advanced && node.path && menuKeys.includes(node.key))
}

/** Account IDs and student-profile IDs are different domains. */
export function accessResource(row, resourceType) {
  if (['STUDENT', 'INTERN_STUDENT', 'GRADUATION_STUDENT'].includes(resourceType)) {
    if (row?.profileBound !== true || !row.studentId) throw new Error('未取得稳定学生主档绑定，不能用账号编号代替学生编号')
    return { type: resourceType, id: String(row.studentId), label: `${row.name || ''} / ${row.studentNo || ''}` }
  }
  if (resourceType === 'USER' && row?.id) return { type: 'USER', id: String(row.id), label: `${row.name || ''} / ${row.loginName || ''}` }
  if (['CLASS', 'MAJOR', 'COLLEGE'].includes(resourceType) && row?.type === resourceType && row.id) {
    return { type: resourceType, id: String(row.id), label: row.name }
  }
  throw new Error('对象类型与编号不一致，请重新选择')
}

export function flattenOrganizations(tree) {
  if (!Array.isArray(tree)) throw new Error('组织目录未取得')
  const result = []
  function walk(nodes) {
    for (const node of nodes) {
      if (!node?.id || !['COLLEGE', 'MAJOR', 'CLASS'].includes(node.type)) throw new Error('组织目录结构异常')
      result.push({ id: String(node.id), type: node.type, name: node.name })
      if (Array.isArray(node.children)) walk(node.children)
    }
  }
  walk(tree)
  return result
}

/** Read-only projection of the server's actual role codes; never a writable catalogue. */
export function makeReadOnlyDraft(detail, roleId) {
  const codes = concreteCodes(detail?.permissionCodes)
  const labels = new Map((detail.readOnlyPreservedPermissions || []).map(item => [item.permissionCode, item.label]))
  return makePermissionDraft([{ key: 'effective', label: '已生效权限（只读）',
    children: codes.map(code => ({ key: code, label: labels.get(code) || code, children: [] }))
  }], detail, roleId)
}

export function isRoleWorkspaceRoute(route) {
  return route.path === '/admin/system/roles' || (route.path === '/admin/system/iam'
    && ['roles', 'templates', 'permissions', 'members'].includes(String(route.query?.surface || '')))
}
