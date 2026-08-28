const states = new Map()

async function settleLatest(key, token, promise) {
  let value
  let failure
  try {
    value = await promise
  } catch (error) {
    failure = error
  }

  const current = states.get(key)
  if (current && current.token !== token) {
    return settleLatest(key, current.token, current.promise)
  }
  if (failure) throw failure
  return value
}

/**
 * Latest-request-wins for read-only mobile projections.
 * Older reads follow the newest in-flight read instead of delivering stale UI state.
 * Mutations are deliberately excluded: their idempotency / optimistic-lock contracts remain authoritative.
 */
export function latestRead(key, loader) {
  const previous = states.get(key)
  const token = Number(previous?.token || 0) + 1
  const promise = Promise.resolve().then(loader)
  states.set(key, { token, promise })
  return settleLatest(key, token, promise)
}

export default latestRead
