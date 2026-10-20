const statuses = new Set(['ALL','DRAFT','PENDING','PUBLISHED','OFFLINE','SUSPENDED','FULL','RISK','ARCHIVED'])
export function positionListQuery(query = {}) {
  const result = {}
  if (statuses.has(query.status) && query.status !== 'ALL') result.status = query.status
  if (typeof query.q === 'string' && query.q.trim()) result.q = query.q.trim().slice(0, 100)
  const page = Number(query.page)
  if (Number.isSafeInteger(page) && page > 1) result.page = String(page)
  if (typeof query.campaignId === 'string' && /^\d+$/.test(query.campaignId)) result.campaignId = query.campaignId
  return result
}
