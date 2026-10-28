import { resolveWorkspacePageId } from './teacherWorkspace.js'

export function activeWorkspacePage(pages, route, activeModule) {
  const entry = route.query?._workspace
  const explicitId = resolveWorkspacePageId(entry, pages.filter(page => pageMatchScore(route.fullPath, page) >= 0))
  const explicit = pages.find(page => page.id === explicitId && pageMatchScore(route.fullPath, page) >= 0)
  if (explicit) return explicit
  const matches = pages.filter(page => pageMatchScore(route.fullPath, page) >= 0)
  matches.sort((a, b) => pageMatchScore(route.fullPath, b) - pageMatchScore(route.fullPath, a))
  return matches.find(page => page.moduleKey === activeModule) || matches[0]
}

function pageMatchScore(current, page) {
  return Math.max(-1, ...[page.path, ...(page.workspacePaths || [])]
    .filter(path => workspacePageMatches(current, path))
    .map(path => (path.includes('?') ? 10000 : 0) + path.length))
}

export function workspacePageMatches(current, candidate) {
  if (!candidate) return false
  const route = new URL(current, 'http://workspace.local')
  const page = new URL(candidate, 'http://workspace.local')
  if (page.pathname === '/admin/internship' && route.pathname !== page.pathname) return false
  if (page.search) return route.pathname === page.pathname && [...page.searchParams].every(([key, value]) => route.searchParams.get(key) === value)
  return route.pathname === page.pathname || route.pathname.startsWith(page.pathname + '/')
}

