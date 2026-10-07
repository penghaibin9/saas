const CONSOLE = '/admin/academic-affairs/textbooks'

export function textbookReturnPath(value, fallback = `${CONSOLE}?tab=distribution`) {
  if (typeof value !== 'string' || !value.startsWith(`${CONSOLE}?`)) return fallback
  const url = new URL(value, 'http://workspace.local')
  return url.pathname === CONSOLE && ['order', 'distribution'].includes(url.searchParams.get('tab'))
    ? url.pathname + url.search : fallback
}

export function textbookQueuePage(value) {
  const page = Number(value)
  return Number.isSafeInteger(page) && page > 0 ? page : 1
}

export function textbookQueueReturnPath(fullPath, tab, page) {
  const url = new URL(fullPath, 'http://workspace.local')
  url.searchParams.set('tab', tab)
  url.searchParams.set('page', String(textbookQueuePage(page)))
  return url.pathname + url.search
}
