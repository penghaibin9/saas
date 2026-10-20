// Explicit page scope travels with each request; never change the user's global batch.
export function selectionScope(input = {}) {
  const keys = ['batchId', 'campaignId', 'recordId']
  if (!keys.some(key => input[key] !== undefined && input[key] !== null && input[key] !== '')) return {}
  const result = {}
  for (const key of keys) {
    const value = input[key]
    if (!['string', 'number'].includes(typeof value) || !/^[1-9]\d*$/.test(String(value))) throw new Error('原招聘季定位不完整，请从志愿结果重新进入。')
    result[key] = String(value)
  }
  return result
}

export function selectionScopePath(path, scope) {
  const query = Object.entries(scope).map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join('&')
  return query ? `${path}${path.includes('?') ? '&' : '?'}${query}` : path
}

export function selectionScopeBody(body = {}, scope = {}) {
  for (const key of ['batchId', 'campaignId', 'recordId']) {
    if (scope[key] && body[key] != null && String(body[key]) !== scope[key]) throw new Error('办理内容与原招聘季不一致，请刷新后重试。')
  }
  if (scope.recordId && body.internshipId != null && String(body.internshipId) !== scope.recordId) throw new Error('办理内容与原实习记录不一致，请刷新后重试。')
  return { ...scope, ...body }
}
