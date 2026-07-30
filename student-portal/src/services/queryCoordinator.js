const inflight = new Map()
const cache = new Map()

function cloneValue(value) {
  if (value == null || typeof value !== 'object') return value
  if (typeof structuredClone === 'function') return structuredClone(value)
  return JSON.parse(JSON.stringify(value))
}

export function runCoordinatedQuery(key, loader, { ttl = 0, force = false } = {}) {
  const queryKey = String(key || '')
  const now = Date.now()
  const cached = cache.get(queryKey)
  if (!force && cached && cached.expiresAt > now) {
    return Promise.resolve(cloneValue(cached.value))
  }
  if (!force && inflight.has(queryKey)) {
    return inflight.get(queryKey).then(cloneValue)
  }

  const promise = Promise.resolve()
    .then(loader)
    .then((value) => {
      if (Number(ttl) > 0) {
        cache.set(queryKey, {
          value: cloneValue(value),
          expiresAt: Date.now() + Number(ttl)
        })
      }
      return value
    })
    .finally(() => {
      if (inflight.get(queryKey) === promise) inflight.delete(queryKey)
    })

  inflight.set(queryKey, promise)
  return promise.then(cloneValue)
}

export function invalidateCoordinatedQueries(match = '') {
  const needle = String(match || '')
  for (const key of cache.keys()) {
    if (!needle || key.includes(needle)) cache.delete(key)
  }
}

export function resetQueryCoordinatorForTest() {
  inflight.clear()
  cache.clear()
}
