import { getToken } from './request'
import { portalApi } from './portalApi'
import { invalidateCoordinatedQueries, runCoordinatedQuery } from './queryCoordinator'

let installed = false

const READ_TTLS = {
  portalConfig: 60_000,
  overview: 10_000,
  todos: 5_000,
  messages: 5_000,
  homeOverview: 15_000,
  academicGraduationAudit: 30_000,
  messagesInbox: 5_000,
  messagePreferences: 30_000
}

const INVALIDATIONS = {
  messageRead: ['messages', 'homeOverview'],
  messagesReadAll: ['messages', 'homeOverview'],
  messageReceipt: ['messages', 'homeOverview'],
  messageSetPreference: ['messages', 'messagePreferences']
}

function identityKey() {
  const token = String(getToken() || '')
  return token ? token.slice(-32) : 'anonymous'
}

function stableArgs(args) {
  try { return JSON.stringify(args || []) } catch { return String(args || '') }
}

export function installStudentPortalPerformanceGuards() {
  if (installed) return
  installed = true

  for (const [name, ttl] of Object.entries(READ_TTLS)) {
    const original = portalApi[name]
    if (typeof original !== 'function') continue
    portalApi[name] = (...args) => runCoordinatedQuery(
      `${identityKey()}|${name}|${stableArgs(args)}`,
      () => original(...args),
      { ttl }
    )
  }

  for (const [name, targets] of Object.entries(INVALIDATIONS)) {
    const original = portalApi[name]
    if (typeof original !== 'function') continue
    portalApi[name] = async (...args) => {
      const result = await original(...args)
      targets.forEach((target) => invalidateCoordinatedQueries(target))
      return result
    }
  }
}
