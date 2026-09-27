import { currentSessionGeneration, sessionChangedError } from './sessionGeneration.mjs'

const states = new Map()

export function staleReadError(key) {
  return {
    code: 'STALE_READ',
    bizCode: 'STALE_READ',
    biz: true,
    staleRead: true,
    message: `页面已刷新，请以最新${key ? '数据' : '结果'}为准`
  }
}

export function isStaleReadError(error) {
  return !!(error && (error.staleRead || error.staleSession
    || error.code === 'STALE_READ' || error.code === 'SESSION_CHANGED'))
}

/**
 * Latest-request-wins for one read projection in one login generation.
 *
 * A previous implementation forwarded the newer Promise to the old caller. That
 * could put B-account data into an A-account page during an account switch.
 * Obsolete callers receive neither old nor new private data: they reject and the
 * live page keeps its own epoch/session result. Mutations remain excluded.
 */
export function latestRead(key, loader) {
  const generation = currentSessionGeneration()
  const stateKey = `${generation}:${String(key || '')}`
  const promise = Promise.resolve().then(loader)
  // Compare the request state by identity instead of a per-key counter. Once a
  // newer request completes its state is removed; a later request must not be
  // allowed to reuse the same numeric token and accidentally revive an older
  // in-flight result (A/B/A ABA race).
  const state = { promise }
  states.set(stateKey, state)

  return promise.then(
    (value) => {
      if (currentSessionGeneration() !== generation) throw sessionChangedError()
      if (states.get(stateKey) !== state) throw staleReadError(key)
      return value
    },
    (error) => {
      if (currentSessionGeneration() !== generation) throw sessionChangedError()
      if (states.get(stateKey) !== state) throw staleReadError(key)
      throw error
    }
  ).finally(() => {
    if (states.get(stateKey) === state) states.delete(stateKey)
  })
}

export default latestRead
