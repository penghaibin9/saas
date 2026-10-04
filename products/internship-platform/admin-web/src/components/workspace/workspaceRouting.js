import { navRefMatches } from '../../config/navPlan.js'
import { resolveWorkspacePageId } from './teacherWorkspace.js'

export function activeWorkspacePage(pages, route, activeModule) {
  const entry = route.query?._workspace
  const explicitId = resolveWorkspacePageId(entry, pages.filter(page => matchesPage(route.fullPath, page)))
  const explicit = pages.find(page => page.id === explicitId && matchesPage(route.fullPath, page))
  if (explicit) return explicit
  const matches = pages.filter(page => matchesPage(route.fullPath, page))
  matches.sort((a, b) => (b.path.includes('?') ? 10000 : 0) + b.path.length - (a.path.includes('?') ? 10000 : 0) - a.path.length)
  return matches.find(page => page.moduleKey === activeModule) || matches[0]
}

function matchesPage(current, page) {
  return workspacePageMatches(current, page.path) || (page.workspacePaths || []).some(path => workspacePageMatches(current, path))
}

export function workspacePageMatches(current, candidate) {
  if (!candidate) return false
  const route = new URL(current, 'http://workspace.local')
  const page = new URL(candidate, 'http://workspace.local')
  if (page.pathname === '/admin/internship' && route.pathname !== page.pathname) return false
  if (page.search) return route.pathname === page.pathname && [...page.searchParams].every(([key, value]) => route.searchParams.get(key) === value)
  return navRefMatches(route.pathname, page.pathname)
}

