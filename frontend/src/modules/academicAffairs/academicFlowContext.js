// Navigation references only. Business state, authorization and versions remain server-owned.
export function academicIdentity(claims, context = {}) {
  if (!claims?.tenantId || !claims?.userId || !claims?.currentRoleCode) return ''
  return JSON.stringify([String(claims.tenantId), String(claims.userId), claims.currentRoleCode,
    claims.activeContextId || '', context.ctxKey || '', context.permissionVersion ?? '',
    context.dataScopeVersion ?? '', [...(context.permissionPatterns || [])].sort(), context.dataScope || null])
}

export function routeScalar(value) {
  return typeof value === 'string' ? value.trim() : ''
}

export function academicRouteState(route, { tabs = [], defaultTab = '' } = {}) {
  const query = route?.query || {}, params = route?.params || {}
  const state = { tab: routeScalar(query.tab) || defaultTab, error: '' }
  if ((query.tab != null && typeof query.tab !== 'string') || (tabs.length && !tabs.includes(state.tab))) state.error = '无法识别该业务视图，请从原目录重新选择入口。'
  for (const key of ['termId', 'batchId', 'taskId', 'classId', 'studentId', 'teacherKey', 'warningId', 'resultId']) {
    const raw = params[key] ?? query[key]
    state[key] = routeScalar(raw)
    const valid = key === 'teacherKey'
      ? state[key].length <= 128 && [...state[key]].every(char => char.charCodeAt(0) >= 32 && char.charCodeAt(0) !== 127)
      : /^[A-Za-z0-9_-]{1,128}$/.test(state[key])
    if (raw != null && (typeof raw !== 'string' || (state[key] && !valid))) {
      state.error = '业务对象参数无效，请返回原队列重新进入。'
    }
  }
  for (const [key, fallback, max] of [['page', 1, 1000000], ['pageSize', 20, 200]]) {
    const value = Number(routeScalar(query[key]))
    state[key] = Number.isInteger(value) && value > 0 && value <= max ? value : fallback
  }
  state.returnToken = routeScalar(query.returnToken)
  return state
}

// A late response may settle, but cannot update a different identity/object/view.
export function createAcademicRequestGate(readContext) {
  let generation = 0
  return {
    begin() {
      const ticket = ++generation, context = readContext()
      return () => ticket === generation && context === readContext()
    },
    invalidate() { generation++ }
  }
}

const RETURN_KEY = 'academic-return-positions-v1'
const RETURN_TTL = 30 * 60 * 1000
const RETURN_QUERY_KEYS = new Set(['tab', 'panel', 'category', 'wall', 'termId', 'batchId', 'taskId', 'classId', 'studentId',
  'teacherKey', 'warningId', 'resultId', 'collegeId', 'status', 'keyword', 'type', 'date', 'dateFrom', 'dateTo', 'term', 'itemId',
  'year', 'week', 'resourceKind', 'resourcePage', 'page', 'pageSize', '_workspace', 'returnToken'])

export function academicReturnPath(route) {
  const path = route?.path
  if (typeof path !== 'string' || !/^\/admin\/academic-affairs(?:\/[A-Za-z0-9_-]+)*$/.test(path)) return ''
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(route.query || {})) {
    if (RETURN_QUERY_KEYS.has(key) && typeof value === 'string' && value.length <= 200) query.set(key, value)
  }
  return path + (query.size ? `?${query}` : '')
}

export function createAcademicReturnStore(storage, { now = Date.now, token = () => globalThis.crypto.randomUUID() } = {}) {
  function read(identity) {
    try {
      const saved = JSON.parse(storage.getItem(RETURN_KEY) || 'null')
      return saved?.identity === identity && Array.isArray(saved.entries)
        ? saved.entries.filter(entry => now() - entry.at >= 0 && now() - entry.at < RETURN_TTL).slice(-30) : []
    } catch { return [] }
  }
  return {
    remember(route, identity, scrollTop = 0) {
      const path = academicReturnPath(route)
      if (!path || !identity) return ''
      const id = token(), entries = read(identity)
      entries.push({ id, path, at: now(), scrollTop: Math.max(0, Math.min(Number(scrollTop) || 0, 1000000)) })
      try { storage.setItem(RETURN_KEY, JSON.stringify({ identity, entries: entries.slice(-30) })); return id } catch { return '' }
    },
    resolve(id, identity) {
      if (!id || !identity) return null
      const entry = read(identity).find(item => item.id === id)
      if (!entry) return null
      try {
        const url = new URL(entry.path, 'http://academic.local')
        const path = academicReturnPath({ path: url.pathname, query: Object.fromEntries(url.searchParams) })
        return url.origin === 'http://academic.local' && path === entry.path
          ? { path, scrollTop: Math.max(0, Math.min(Number(entry.scrollTop) || 0, 1000000)) } : null
      } catch { return null }
    },
    clear() { try { storage.removeItem(RETURN_KEY) } catch { /* storage may be unavailable */ } }
  }
}
