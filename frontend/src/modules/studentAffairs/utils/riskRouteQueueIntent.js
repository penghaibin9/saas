export const RISK_QUEUE_QUERY_KEYS = Object.freeze([
  'priority',
  'overdueOnly',
  'unassignedOnly',
  'ownerId'
])

export function resolveRiskQueueIntent(query = {}) {
  if (String(query.priority || '') === 'HIGH_CRITICAL') return 'HIGH'
  if (String(query.overdueOnly || '').toLowerCase() === 'true') return 'OVERDUE'
  if (String(query.unassignedOnly || '').toLowerCase() === 'true') return 'UNASSIGNED'
  if (String(query.ownerId || '') === 'me') return 'MINE'
  if (String(query.status || '').toUpperCase() === 'FOLLOWING') return 'FOLLOWING'
  return 'ALL'
}
