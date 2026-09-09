import test from 'node:test'
import assert from 'node:assert/strict'
import { NAV_PLAN, getVisibleNavPlan } from '../src/config/navPlan.js'
import { workspacePages, restoreWorkspace } from '../src/components/workspace/teacherWorkspace.js'
import { usesAcademicWorkspace, activeWorkspacePage, workspaceRouteOwner, workspaceIdentity } from '../src/components/workspace/workspaceRouting.js'
const modules = getVisibleNavPlan({ includePlanned: false, permissionPatterns: ['*'] }).find(group => group.key === 'academic-affairs').children
const pages = workspacePages(modules)
const routeFor = page => { const url = new URL(page.destination || page.path, 'http://workspace.local'); return { path: url.pathname, fullPath: url.pathname + url.search, query: Object.fromEntries(url.searchParams) } }
test('leadership wall precedes the dashboard and retains the dashboard permission', () => {
  assert.equal(modules[0].key, 'aa-big-screen')
  assert.equal(modules[1].key, 'aa-dashboard')
  const wall = pages.find(page => page.moduleKey === 'aa-big-screen')
  assert.equal(wall.path, '/admin/academic-affairs?wall=1')
  const restricted = getVisibleNavPlan({ permissionPatterns: ['academicAffairs.term.view'] }).find(group => group.key === 'academic-affairs')
  assert.ok(!restricted.children.some(group => group.key === 'aa-big-screen'))
})
test('all 17 academic workspaces and their complete directory survive shell projection', () => {
  const original = NAV_PLAN.find(group => group.key === 'academic-affairs')
  assert.equal(modules.length, 17)
  assert.equal(pages.length, original.children.reduce((sum, mod) => sum + mod.children.filter(page => !page.hidden).length, 0))
  assert.equal(new Set(pages.map(page => page.id)).size, pages.length)
  for (const page of pages) if (page.path) assert.equal(usesAcademicWorkspace(page.path.split('?')[0], page.path), true, page.title)
})
test('every usable menu resolves to its own page, including shared routes and query tabs', () => {
  for (const page of pages.filter(page => page.path && !page.disabled)) {
    const route = routeFor(page)
    const owner = workspaceRouteOwner(route.path, route.fullPath)
    assert.equal(activeWorkspacePage(pages, route, owner.modKey)?.id, page.id, page.title + ' ' + page.moduleKey)
  }
})
test('details and filtered query pages retain their actual module and selected leaf', () => {
  const route = { path: '/admin/academic-affairs/orgs', fullPath: '/admin/academic-affairs/orgs?tab=major&keyword=software', query: {tab:'major',keyword:'software'} }
  assert.equal(activeWorkspacePage(pages, route, 'aa-terms').path, '/admin/academic-affairs/orgs?tab=major')
  const detail = { path: '/admin/academic-affairs/terms/123', fullPath: '/admin/academic-affairs/terms/123', query: {} }
  assert.equal(activeWorkspacePage(pages, detail, 'aa-terms').path, '/admin/academic-affairs/terms')
})
test('revoked and planned entries cannot be restored as actionable tabs or shortcuts', () => {
  const allowed = workspacePages(getVisibleNavPlan({ permissionPatterns: ['academicAffairs.org.view'] }).find(g=>g.key==='academic-affairs')?.children || [])
  const saved = { tabs: pages.map(p=>p.id), shortcuts: pages.map(p=>p.id) }
  const restored = restoreWorkspace(saved, allowed)
  assert.ok(restored.tabs.every(id => allowed.some(page=>page.id===id && !page.disabled)))
  assert.ok(!restored.tabs.some(id=>id.includes('/terms')))
  const planned = pages.filter(p=>p.disabled).map(p=>p.id)
  assert.deepEqual(restoreWorkspace({tabs:planned,shortcuts:planned},pages).tabs, [])
})
test('appearance identity is shared across module contexts and isolated across tenants and roles', () => {
  const user={tenantId:'1',userId:'2',currentRoleCode:'TEACHER',activeContextId:'3'}
  assert.equal(workspaceIdentity(user,{ctxKey:'academic'}),workspaceIdentity(user,{ctxKey:'student'}))
  assert.notEqual(workspaceIdentity(user,{}),workspaceIdentity({...user,tenantId:'4'},{}))
  assert.notEqual(workspaceIdentity(user,{}),workspaceIdentity({...user,currentRoleCode:'ACADEMIC'},{}))
})
