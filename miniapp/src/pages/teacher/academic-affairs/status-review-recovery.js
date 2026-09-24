// A completed task proves its business outcome, not which network request delivered it.
// Only the authenticated actor's formal done queue may be passed to this matcher.
export function matchCompletedStatusTask(attempt, page) {
  if (!attempt || !Array.isArray(page?.items)) return null
  const expected = { APPROVE: ['APPROVED'], REJECT: ['REJECTED'], RETURN: ['TRANSFERRED', 'RETURNED'] }[attempt.action]
  if (!expected) return null
  const matches = page.items.filter(row =>
    row.sourceModule === 'academic-affairs' && row.sourceBizType === 'AA_STATUS_CHANGE' &&
    String(row.sourceBizId) === String(attempt.objectId) && row.nodeCode === attempt.beforeNode &&
    expected.includes(row.status) && row.actedAt &&
    (!attempt.beforeTaskId || String(row.taskId) === String(attempt.beforeTaskId)))
  if (matches.length !== 1) return null
  if (attempt.beforeTaskId) return matches[0]
  // Older installations did not retain task IDs. Never infer success from an old
  // loop through the same node, a partial page, or an unreadable timestamp.
  if (!Number.isFinite(page.total) || page.total > page.items.length) return null
  const started = parseInt(String(attempt.attemptKey || '').split('-')[0], 36)
  const utc = value => Date.parse(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`)
  const submitted = utc(matches[0].submittedAt || '')
  const acted = utc(matches[0].actedAt)
  if (!Number.isFinite(started) || !Number.isFinite(submitted) || !Number.isFinite(acted)) return null
  return submitted <= started && acted + 999 >= started ? matches[0] : null
}
