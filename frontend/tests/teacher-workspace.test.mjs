import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { restoreWorkspace, workspacePages, workspaceShort, workspaceTokens, workspaceCurrentPage } from '../src/components/workspace/teacherWorkspace.js'
import { getVisibleNavPlan } from '../src/config/navPlan.js'

test('workspace selects the precise menu while preserving extra batch/filter and detail context', () => {
  const pages = [
    { path: '/admin/internship', moduleKey: 'home' },
    { path: '/admin/internship/students?panel=roster', moduleKey: 'students' },
    { path: '/admin/internship/students?panel=eligibility', moduleKey: 'qualification' },
    { path: '/admin/internship/agreements', moduleKey: 'agreements' }
  ]
  assert.equal(workspaceCurrentPage(pages, '/admin/internship/students?batchId=23&page=2&panel=eligibility').moduleKey, 'qualification')
  assert.equal(workspaceCurrentPage(pages, '/admin/internship/students?batchId=23').moduleKey, 'students')
  assert.equal(workspaceCurrentPage(pages, '/admin/internship/agreements/4?batchId=23&section=history').moduleKey, 'agreements')
  assert.equal(workspaceCurrentPage([], '/admin/internship/students?batchId=23'), undefined)
})

test('restoring teacher tabs and shortcuts removes revoked routes and never accepts arbitrary query data', () => {
  const pages = workspacePages([{ key: 'leave', label: '请假', children: [{ label: '审批', path: '/leave' }, { label: '禁用', path: '/denied', disabled: true }] }])
  assert.equal(pages.length, 1)
  const restored = restoreWorkspace({ tabs: ['/leave', '/leave', '/denied', '/leave?studentName=甲'], shortcuts: ['/denied', '/leave'], second: 'evil', theme: '__proto__' }, pages)
  assert.deepEqual(restored.tabs, ['/leave'])
  assert.deepEqual(restored.shortcuts, ['/leave'])
  assert.equal(restored.second, 'compact')
  assert.equal(restored.theme, 'blue')
})

test('agreement template deep links retain the agreement workspace without adding a duplicate menu', () => {
  const pages = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.agreement.view'] }).find(group => group.key === 'internship')?.children || [])
  for (const path of ['/admin/internship/agreement-templates', '/admin/internship/agreement-templates/new', '/admin/internship/agreement-templates/9/edit']) {
    assert.equal(workspaceCurrentPage(pages, `${path}?batchId=7`).title, '三方协议')
  }
  assert.equal(pages.filter(page => page.title === '三方协议').length, 1)
})
test('workspace restores compact and floating columns independently and preserves an intentionally empty dock', () => {
  const restored = restoreWorkspace({ second: 'auto', third: 'full', shortcuts: [], collapsed: false }, [])
  assert.equal(restored.second, 'auto')
  assert.equal(restored.third, 'full')
  assert.deepEqual(restored.shortcuts, [])
  assert.equal(restored.collapsed, false)
  assert.equal(workspaceShort({ label: '销假与续假' }), '返校')
})

test('the material workspace participates in tabs and shortcuts only with its existing route permission', () => {
  const path = '/admin/student-affairs/material-operations'
  const pagesFor = permissionPatterns => workspacePages(getVisibleNavPlan({ permissionPatterns }).find(group => group.key === 'student-affairs')?.children || [])
  const allowed = pagesFor(['studentAffairs.dashboard.view'])
  const material = allowed.find(page => page.id === path)
  assert.equal(material.title, '材料与档案'); assert.equal(material.moduleKey, 'sa-archive-stats')
  const saved = { tabs: [path], shortcuts: [path] }
  assert.deepEqual(restoreWorkspace(saved, allowed).tabs, [path])
  assert.deepEqual(restoreWorkspace(saved, allowed).shortcuts, [path])
  const revoked = restoreWorkspace(saved, pagesFor(['studentAffairs.leave.view']))
  assert.deepEqual(revoked.tabs, []); assert.deepEqual(revoked.shortcuts, [])
})

test('the internship workspace participates in tabs and shortcuts only with its existing route permission', () => {
  const path = '/admin/internship/insurance'
  const pagesFor = permissionPatterns => workspacePages(getVisibleNavPlan({ permissionPatterns }).find(group => group.key === 'internship')?.children || [])
  const allowed = pagesFor(['internship.insurance.view'])
  const insurance = allowed.find(page => page.id === path)
  assert.ok(insurance.title); assert.equal(insurance.moduleKey, 'in-match-assign')
  const saved = { tabs: [path], shortcuts: [path] }
  assert.deepEqual(restoreWorkspace(saved, allowed).tabs, [path])
  assert.deepEqual(restoreWorkspace(saved, allowed).shortcuts, [path])
  const revoked = restoreWorkspace(saved, pagesFor(['internship.report.view']))
  assert.deepEqual(revoked.tabs, []); assert.deepEqual(revoked.shortcuts, [])
})

test('teacher workspace uses the accepted four student colors without a pure white theme', () => {
  for (const key of ['blue', 'sage', 'plum', 'dark']) {
    const theme = workspaceTokens(key)
    assert.ok(theme['--pri'])
    assert.equal(theme['--bg-card'], theme['--surface'])
  }
  assert.equal(workspaceTokens('dark')['--bg'], '#151619')
})
test('workspace menu is a permission projection and leaves identity controls in the existing shell', () => {
  const source = readFileSync(new URL('../src/layouts/BasePortalLayout.vue', import.meta.url), 'utf8')
  assert.match(source, /workspaceModules\(\)[\s\S]*?const permissions = this\.ctx\?\.permissionPatterns \|\| \[\][\s\S]*?includePlanned: false, permissionPatterns: permissions/)
  assert.match(source, /:identity-key="workspaceIdentityKey"/)
  assert.match(source, /<AppUserChip embedded/)
  const frame = readFileSync(new URL('../src/components/workspace/TeacherWorkspaceFrame.vue', import.meta.url), 'utf8')
  assert.match(frame, /onBeforeRouteLeave\(confirmUnsubmitted\)/)
  assert.match(frame, /onBeforeRouteUpdate\(confirmUnsubmitted\)/)
})

test('exception list and detail stay in the attendance workspace with view permission', () => {
  const pages = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.attendance.view'] }).find(group => group.key === 'internship')?.children || [])
  for (const path of ['/admin/internship/exceptions', '/admin/internship/exceptions/9007199254740999', '/admin/internship/attendance?panel=exceptions']) {
    const current = workspaceCurrentPage(pages, path + (path.includes('?') ? '&' : '?') + 'batchId=7')
    assert.equal(current.title, '异常核验')
    assert.equal(current.moduleKey, 'in-attendance-leave')
  }
})
