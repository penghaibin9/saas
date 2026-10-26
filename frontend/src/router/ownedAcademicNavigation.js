// Caller-owned academic navigation commit capability; not an authorization boundary.
// A nested plain capability survives Vue Router's shallow state merges. Its exact
// identity, never a path/current Frame/FIFO guess, determines request ownership.
export const OWNED_HISTORY_STATE_KEY = '__academicFrameOwnedNavigationCapability'

export function createOwnedHistoryAdapter(originalHistory, { shouldEnforce, resolveLocation }) {
  if (typeof shouldEnforce !== 'function') throw new TypeError('shouldEnforce must be a function')
  if (typeof resolveLocation !== 'function') throw new TypeError('Public resolveLocation must be a function')
  const issued = new WeakMap()
  const active = new WeakMap()
  const owns = value => value !== null && typeof value === 'object' && issued.has(value)
  function commit(method, location, data) {
    const token = data?.[OWNED_HISTORY_STATE_KEY]
    if (!owns(token)) return originalHistory[method].call(originalHistory, location, data)
    const cleanData = { ...data }
    delete cleanData[OWNED_HISTORY_STATE_KEY]
    // Classification only. Fresh denial does not reconstruct an accessNotice or
    // replace the canonical permission guard. Caller proof is the issued token.
    if (shouldEnforce(location)) {
      const current = active.get(token)
      if (!current || !current.isCurrent()) throw issued.get(token).error
    }
    const result = originalHistory[method].call(originalHistory, location, cleanData)
    active.delete(token)
    return result
  }
  const push = (location, data) => commit('push', location, data)
  const replace = (location, data) => commit('replace', location, data)
  const history = new Proxy(originalHistory, {
    get(target, key) {
      if (key === 'push') return push
      if (key === 'replace') return replace
      return Reflect.get(target, key, target)
    }
  })
  function issue(rawLocation, { isCurrent }) {
    if (typeof isCurrent !== 'function') throw new TypeError('isCurrent must be a function')
    // Object-form path does not parse a string's query/hash in pinned Router.
    // Use its PUBLIC resolver; no handwritten URL parsing or global push patch.
    const resolved = typeof rawLocation === 'string' ? resolveLocation(rawLocation) : null
    const raw = resolved ? { path: resolved.path, query: resolved.query, hash: resolved.hash } : rawLocation
    if (!raw || typeof raw !== 'object') throw new TypeError('A raw route location is required')
    const priorState = raw.state ?? {}
    if (Object.hasOwn(priorState, OWNED_HISTORY_STATE_KEY)) throw new TypeError('Reserved owned navigation state key collision')
    const token = Object.freeze({})
    const error = new Error('Frame-owned navigation source is stale')
    error.name = 'FrameOwnedNavigationStaleError'
    issued.set(token, { error })
    active.set(token, { isCurrent })
    return Object.freeze({
      location: { ...raw, state: { ...priorState, [OWNED_HISTORY_STATE_KEY]: token } },
      isOwnStale: candidate => candidate === error,
      // Idempotent, identity-local cleanup. Retired issued tokens are still
      // recognized/stripped; they retain no owner callback and cannot be replayed
      // to an enforceable target. Errors from any other request are not owned.
      finish: () => { active.delete(token) }
    })
  }
  return Object.freeze({ history, issue })
}

// Explicit router-instance registration; no global push replacement and no router/index import cycle.
const routerAdapters = new WeakMap()
export function registerOwnedHistoryAdapter(router, adapter) {
  if (routerAdapters.has(router)) throw new Error('Owned history adapter already registered')
  routerAdapters.set(router, adapter)
  return () => { if (routerAdapters.get(router) === adapter) routerAdapters.delete(router) }
}
export function issueFrameOwnedNavigation(router, rawLocation, options) {
  const adapter = routerAdapters.get(router)
  if (!adapter) throw new Error('Academic Frame requires its registered owned history adapter')
  return adapter.issue(rawLocation, options)
}
