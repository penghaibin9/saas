import assert from 'node:assert/strict'
import test from 'node:test'
import { NAV_PLAN, ACADEMIC_NAV_SOURCE_MODULES, getVisibleNavPlan, findActiveInPlan, searchNavPlan } from '../src/config/navPlan.js'
import { ACADEMIC_WORKSPACES } from '../src/modules/academicAffairs/config/academicNavigation.js'
import { workspaceMenuItems, workspacePages } from '../src/components/workspace/teacherWorkspace.js'

const academic = NAV_PLAN.find((group) => group.key === 'academic-affairs')
const projected = academic.children.flatMap((group) => group.children)

test('the agreed 17 workspaces cover all 30 source modules', () => {
  assert.equal(academic.children.length, 17)
  assert.deepEqual(academic.children.map(group => group.key), ACADEMIC_WORKSPACES.map(([key]) => key))
  assert.deepEqual(new Set(ACADEMIC_WORKSPACES.flatMap(([, , sources]) => sources)), new Set(ACADEMIC_NAV_SOURCE_MODULES.map(group => group.key)))
})

test('every original entry retains its route and permissions; only exact duplicates are hidden', () => {
  assert.equal(projected.length, ACADEMIC_NAV_SOURCE_MODULES.reduce((total, group) => total + group.children.length, 0))
  for (const source of ACADEMIC_NAV_SOURCE_MODULES) {
    source.children.forEach((leaf, index) => {
      const key = leaf.key || `${source.key}-${String(index + 1).padStart(2, '0')}`
      const actual = projected.find(leaf => leaf.sourceKey === `${source.key}:${index}`)
      assert.ok(actual, key)
      for (const field of ['path', 'permissionKey', 'permissionAny', 'permissionAll', 'disabled', 'status']) {
        assert.deepEqual(actual[field], leaf[field], `${key}.${field}`)
      }
      if (actual.hidden && !leaf.hidden) {
        const canonical = projected.find(item => item.sourceKey === actual.menuDuplicateOf)
        assert.ok(canonical && !canonical.hidden)
        for (const field of ['path', 'permissionKey', 'permissionAny', 'permissionAll', 'disabled', 'status']) assert.deepEqual(canonical[field], leaf[field], field)
        assert.ok(canonical.searchAliases.includes(leaf.label))
      }
    })
  }
})

test('term-only role sees only permitted term entries', () => {
  const result = getVisibleNavPlan({ permissionPatterns: ['academicAffairs.term.view'], ctxKey: 'aa-term-only' })
    .find((group) => group.key === 'academic-affairs')
  const foundation = result.children.find((group) => group.key === 'aa-terms')
  assert.ok(foundation.children.length > 0)
  assert.ok(foundation.children.every((leaf) => leaf.permissionKey === 'academicAffairs.term.view'))
  assert.equal(getVisibleNavPlan({ permissionPatterns: [], ctxKey: 'aa-no-perms' }).find((group) => group.key === 'academic-affairs'), undefined)
})

test('deep links retain correct ownership after label cleanup, including query tabs', () => {
  for (const workspace of academic.children) {
    for (const leaf of workspace.children.filter((item) => item.path && !item.hidden)) {
      const owner = findActiveInPlan(leaf.path.split('?')[0], leaf.path)
      assert.equal(owner.groupKey, 'academic-affairs', leaf.path)
      // Some cross-module paths intentionally have another primary menu owner.
      if (leaf.path.startsWith('/admin/academic-affairs') && workspace.children.filter((item) => item.path === leaf.path).length === 1) {
        assert.ok(academic.children.some((group) => group.key === owner.modKey), leaf.path)
      }
    }
  }
})

test('old module names remain searchable and permissionAny is enforced in search', () => {
  const source = ACADEMIC_NAV_SOURCE_MODULES.find((group) => group.key === 'aa-terms')
  assert.ok(searchNavPlan(source.label, ['academicAffairs.term.view']).some((item) => item.path === '/admin/academic-affairs/terms'))
  const correction = NAV_PLAN.flatMap((group) => group.children.flatMap((module) => module.children || [])).find((leaf) => leaf.permissionAny?.includes('academicAffairs.roster.correction.view') && !leaf.hidden)
  assert.ok(correction)
  assert.ok(!searchNavPlan(correction.label, []).some((item) => item.path === correction.path))
  assert.ok(searchNavPlan(correction.label, ['academicAffairs.roster.correction.view']).some((item) => item.path === correction.path))
})

test('secondary functions remain available in the complete searchable directory and on deep links', () => {
  const modules = getVisibleNavPlan({ permissionPatterns: ['*'] }).find(group => group.key === 'academic-affairs').children
  const pages = workspacePages(modules)
  for (const mod of modules) {
    const all = workspaceMenuItems(pages, mod.key, '', true)
    assert.equal(all.length, pages.filter(page => page.moduleKey === mod.key && !page.workspaceHidden).length)
    for (const page of all.filter(item => item.menuSecondary)) {
      assert.ok(workspaceMenuItems(pages, mod.key, page.id).some(item => item.id === page.id))
      assert.ok(workspaceMenuItems(pages, mod.key, '', true, page.label).some(item => item.id === page.id))
      assert.ok(searchNavPlan(page.label, ['*']).some(item => item.path === page.path))
    }
  }
})

test('daily operations, workload processing and supplementary exams have clear owners', () => {
  for (const [path, expected] of [
    ['/admin/academic-affairs/workload-review', 'aa-teaching-tasks'],
    ['/admin/academic-affairs/classroom-bookings', 'aa-daily'],
    ['/admin/academic-affairs/makeup?tab=makeup', 'aa-exam'],
    ['/admin/academic-affairs/makeup?tab=retake', 'aa-grades'],
    ['/admin/academic-affairs/warnings', 'aa-student-status']
  ]) assert.equal(findActiveInPlan(path.split('?')[0], path).modKey, expected, path)
  const stats = academic.children.find(group => group.key === 'aa-stats')
  assert.equal(stats.children.filter(leaf => !leaf.hidden && !leaf.menuSecondary).length, 7)
})

test('shared shell leaves other centers unchanged and retains the statistics parent for every dimension', () => {
  const other = [{ id: 'a', moduleKey: 'student', label: '学生列表' }, { id: 'b', moduleKey: 'student', label: '请假审批' }]
  assert.deepEqual(workspaceMenuItems(other, 'student', 'a'), other)
  const stats = academic.children.find(group => group.key === 'aa-stats')
  for (const leaf of stats.children.filter(item => !item.hidden && item.menuParentPath)) {
    assert.ok(stats.children.some(item => !item.hidden && !item.menuSecondary && item.path === leaf.menuParentPath), leaf.path)
  }
})

test('time band menu requires both its own permission and the slot catalog used by the route', () => {
  const entries = (permissions) => getVisibleNavPlan({ permissionPatterns: permissions, ctxKey: permissions.join(',') })
    .flatMap(group => group.children.flatMap(module => module.children))
  const bands = '/admin/academic-affairs/time-slots?tab=bands'
  assert.ok(!entries(['academicAffairs.classTimeBand.view']).some(leaf => leaf.path === bands))
  assert.ok(!entries(['academicAffairs.timeslot.view']).some(leaf => leaf.path === bands))
  assert.ok(entries(['academicAffairs.classTimeBand.view', 'academicAffairs.timeslot.view']).some(leaf => leaf.path === bands))
  assert.ok(!searchNavPlan('上课时间段', ['academicAffairs.classTimeBand.view']).some(leaf => leaf.path === bands))
})
