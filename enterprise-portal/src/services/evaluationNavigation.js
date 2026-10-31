import { requireDecimalId } from './evaluationContext.js'

const origin = 'https://enterprise.invalid'
const keys = new Set(['tenantCode', 'campaignId', 'batchId', 'internshipId', 'entry'])

// Only the evaluation story can resume after login; URL parameters never grant access.
export function evaluationReturnTarget(raw) {
  if (typeof raw !== 'string' || !raw.startsWith('/') || raw.startsWith('//') || /[\\\u0000-\u0020]/.test(raw)) return null
  try {
    const url = new URL(raw, origin)
    if (url.origin !== origin || url.pathname !== '/evaluations' || url.hash) return null
    for (const key of url.searchParams.keys()) if (!keys.has(key) || url.searchParams.getAll(key).length !== 1) return null
    const tenantCode = url.searchParams.get('tenantCode') || ''
    if (!tenantCode || tenantCode.length > 100 || tenantCode !== tenantCode.trim()) return null
    const query = { tenantCode }
    for (const key of ['campaignId', 'batchId', 'internshipId']) query[key] = requireDecimalId(url.searchParams.get(key))
    if (url.searchParams.has('entry') && url.searchParams.get('entry') !== 'qr-evaluation') return null
    query.entry = 'qr-evaluation'
    return { path: '/evaluations', query }
  } catch { return null }
}

export function evaluationReturnPath(target) {
  return `${target.path}?${new URLSearchParams(target.query)}`
}

export function assertEvaluationReturnScope(target, context, tenantCode) {
  if (String(tenantCode) !== target.query.tenantCode || String(context?.batchId) !== target.query.batchId ||
      (context?.campaignId && String(context.campaignId) !== target.query.campaignId) || context?.capabilities?.internshipCollab !== true) {
    throw new Error('扫码任务与当前学校、企业或批次授权不匹配，请使用受邀企业账号重新选择正确范围')
  }
}
