const calls = globalThis.__APPROVAL_BATCH_VERSION_CALLS__
  || (globalThis.__APPROVAL_BATCH_VERSION_CALLS__ = [])

export async function request(path, options = {}) {
  calls.push({ path, options })
  const state = globalThis.__APPROVAL_BATCH_VERSION_STATE__ || {}

  const detailMatch = /^\/approvals\/tasks\/([^/]+)$/.exec(path)
  if (detailMatch) {
    const taskId = decodeURIComponent(detailMatch[1])
    const row = state.details?.[taskId]
    if (!row) throw new Error(`missing detail fixture: ${taskId}`)
    return structuredClone(row)
  }

  if (path === '/approvals/batch') {
    state.lastBatchBody = structuredClone(options.body || {})
    return {
      action: options.body?.action || '',
      succeeded: (options.body?.items || []).length,
      failed: 0,
      skipped: 0,
      results: (options.body?.items || []).map((x) => ({
        id: x.taskId,
        result: 'SUCCESS',
        errorCode: null,
        newVersion: Number(x.version || 0) + 1
      }))
    }
  }

  throw new Error(`unexpected request: ${path}`)
}
