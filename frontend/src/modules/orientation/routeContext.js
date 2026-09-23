// Carry only the batch context understood by the destination's real API.
export const ORIENTATION_BATCH_PAGES = new Set([
  '/admin/orientation', '/admin/orientation/students', '/admin/orientation/verify',
  '/admin/orientation/data', '/admin/orientation/materials', '/admin/orientation/green-channels',
  '/admin/orientation/exceptions', '/admin/orientation/dorm',
  '/admin/orientation/no-show', '/admin/orientation/statistics',
  '/admin/orientation/qualification', '/admin/orientation/payment',
  '/admin/orientation/dorm-preassign', '/admin/orientation/progress'
])

const CONTEXT_PAGES = new Set([...ORIENTATION_BATCH_PAGES,
  '/admin/orientation/checkin', '/admin/orientation/batches',
  '/admin/orientation/flow-config', '/admin/orientation/checkin-points',
  '/admin/orientation/notices', '/admin/orientation/archive'
])

export function orientationDestination(path, route) {
  if (typeof path !== 'string' || !route?.path?.startsWith('/admin/orientation')) return path
  const [target, query = ''] = path.split('?')
  if ((!CONTEXT_PAGES.has(target) && !/^\/admin\/orientation\/students\/[^/]+$/.test(target)) || !route.query?.batchId) return path
  const params = new URLSearchParams(query)
  if (!params.has('batchId')) params.set('batchId', String(route.query.batchId))
  return `${target}?${params}`
}

// Only a batch selection is retained, never student data or credentials. The caller
// supplies the workspace identity (school, user, role and active context).
export function rememberOrientationBatch(storage, identity, route) {
  if (!identity || !route?.path?.startsWith('/admin/orientation')) return
  const batch = String(route.query?.batchId || '')
  if (!/^[1-9]\d{0,19}$/.test(batch) && !(batch === '' && route.query?.batchId === '')) return
  try { storage.setItem(`orientation-batch:${identity}`, batch) } catch { /* Storage is optional. */ }
}

export function restoreOrientationBatch(path, storage, identity, preferRememberedBatch = false) {
  if (!identity || typeof path !== 'string' || !path.startsWith('/admin/orientation')) return path
  try {
    const batchId = storage.getItem(`orientation-batch:${identity}`)
    if (!/^[1-9]\d{0,19}$/.test(batchId || '') && batchId !== '') return path
    if (preferRememberedBatch) {
      const [target, query = ''] = path.split('?')
      const params = new URLSearchParams(query)
      params.delete('batchId')
      path = params.size ? `${target}?${params}` : target
    }
    return orientationDestination(path, {path:'/admin/orientation',query:{batchId}})
  } catch { return path }
}
