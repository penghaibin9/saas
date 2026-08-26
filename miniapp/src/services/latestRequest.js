const latestStates = new Map()

async function settleLatest(key, token, promise) {
  let value
  let failure
  try {
    value = await promise
  } catch (error) {
    failure = error
  }

  const current = latestStates.get(key)
  if (current && current.token !== token) {
    return settleLatest(key, current.token, current.promise)
  }
  if (failure) throw failure
  return value
}

/**
 * Latest-request-wins for read-only UI projections.
 *
 * If an older request finishes after a newer request has started, callers of the
 * older request follow the newest in-flight request instead of receiving stale
 * data. This is intentionally read-only: mutations must keep their own idempotency,
 * optimistic-lock and FileVersion contracts.
 */
export function latestRequest(key, loader) {
  const previous = latestStates.get(key)
  const token = Number(previous?.token || 0) + 1
  const promise = Promise.resolve().then(loader)
  latestStates.set(key, { token, promise })
  return settleLatest(key, token, promise)
}

export default latestRequest
