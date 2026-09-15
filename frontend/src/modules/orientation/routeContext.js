// Carry only the batch context understood by the destination's real API.
const BATCH_PAGES = new Set([
  '/admin/orientation', '/admin/orientation/students', '/admin/orientation/verify',
  '/admin/orientation/data', '/admin/orientation/materials', '/admin/orientation/green-channels',
  '/admin/orientation/exceptions', '/admin/orientation/dorm',
  '/admin/orientation/no-show', '/admin/orientation/statistics'
])

export function orientationDestination(path, route) {
  if (typeof path !== 'string' || !route?.path?.startsWith('/admin/orientation')) return path
  const [target, query = ''] = path.split('?')
  if (!BATCH_PAGES.has(target) || !route.query?.batchId) return path
  const params = new URLSearchParams(query)
  if (!params.has('batchId')) params.set('batchId', String(route.query.batchId))
  return `${target}?${params}`
}
