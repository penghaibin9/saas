import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'
import { routeScalar } from '../src/modules/academicAffairs/academicFlowContext.js'

function page(name, query = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding.replace(/ as /g, ': ')} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: new Proxy({ routeScalar }, { get: (target, key) => target[key] || {} }) }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component, navigations = []
  const state = Object.assign(definition.data(), definition.methods, {
    $route: { path: '/admin/academic-affairs/orgs', query },
    $router: { push: value => navigations.push(value), replace: value => navigations.push(value) },
    busy: false, reload() {}, hasPermission: () => true,
    academicFlow: { captureReturn: () => 'origin' }
  })
  return { state, navigations, definition }
}

test('organization drill-down preserves the selected parent and rejects navigation during a write', () => {
  const { state, navigations } = page('AaOrgConsole')
  state.goToOrganization('major', { collegeId: '9007199254740999' })
  assert.equal(navigations[0].query.collegeId, '9007199254740999')
  assert.equal(navigations[0].query.tab, 'major')
  state.busy = true
  state.goToOrganization('class', { majorId: '17' })
  assert.equal(navigations.length, 1)
})

test('organization refresh restores filters and page without carrying another tab filters', () => {
  const { state } = page('AaOrgConsole', { tab: 'major', collegeId: '12', majorId: '99', keyword: '软件', page: '3' })
  state.tab = 'major'; state.restoreListQuery()
  assert.equal(state.filters.collegeId, '12')
  assert.equal(state.filters.majorId, '')
  assert.equal(state.filters.keyword, '软件')
  assert.equal(state.pagination.page, 3)
  state.$route.query = { tab: 'class', majorId: '18', page: '-1' }
  state.tab = 'class'; state.restoreListQuery()
  assert.equal(state.filters.collegeId, '')
  assert.equal(state.filters.majorId, '18')
  assert.equal(state.filters.keyword, '')
  assert.equal(state.pagination.page, 1)
})

test('search and pagination persist the active filter while resetting search to page one', () => {
  const { state, navigations } = page('AaOrgConsole', { tab: 'major', returnToken: 'origin' })
  state.tab = 'major'; state.filters.collegeId = '12'; state.filters.keyword = '软件'
  state.pagination.page = 4; state.search()
  assert.equal(navigations[0].query.page, '1')
  assert.equal(navigations[0].query.collegeId, '12')
  assert.equal(navigations[0].query.returnToken, 'origin')
  state.onPageChange(2)
  assert.equal(navigations[1].query.page, '2')
  assert.equal(navigations[1].query.keyword, '软件')
})

test('calendar handoff carries the chosen historical term instead of using the current term', () => {
  const { state, navigations } = page('AaTermListView')
  state.goCalendar({ termId: 'historical-term' })
  assert.equal(navigations[0].query.termId, 'historical-term')
  assert.equal(navigations[0].query.returnToken, 'origin')
  state.hasPermission = () => false
  state.goCalendar({ termId: 'other' })
  assert.equal(navigations.length, 1)
})

test('same-tab parent navigation applies the new filter and reloads exactly once', () => {
  const { state, definition } = page('AaOrgConsole', { tab: 'major', collegeId: '12' })
  state.tab = 'major'; state.restoreListQuery()
  let reads = 0
  state.reload = () => reads++
  state.$route.query = { tab: 'major', collegeId: '13' }
  definition.watch['$route.fullPath'].call(state)
  assert.equal(state.filters.collegeId, '13')
  assert.equal(reads, 1)
  definition.watch['$route.fullPath'].call(state)
  assert.equal(reads, 1)
})

test('invalid repeated query values are not used as organization filters', () => {
  const { state } = page('AaOrgConsole', { tab: 'major', collegeId: ['12', '13'], page: 'Infinity' })
  state.tab = 'major'; state.restoreListQuery()
  assert.equal(state.filters.collegeId, '')
  assert.equal(state.pagination.page, 1)
})

test('reference check opens the exact class roster without searching by a possibly duplicate name', async () => {
  const { state, navigations } = page('AaOrgConsole')
  state.canViewOrganizations = true
  let reads = 0
  state.reloadStudentDrawer = async () => reads++
  await state.viewCheckedStudents({ targetType: 'CLASS', targetId: '9007199254740999', targetName: '同名班级' })
  assert.equal(state.students.classId, '9007199254740999')
  assert.equal(state.referenceReturn.targetId, '9007199254740999')
  assert.equal(reads, 1)
  assert.equal(navigations.length, 0)
  state.canViewOrganizations = false
  await state.viewCheckedStudents({ targetType: 'CLASS', targetId: 'other' })
  state.canViewOrganizations = true; state.busy = true
  await state.viewCheckedStudents({ targetType: 'CLASS', targetId: 'other' })
  state.busy = false
  await state.viewCheckedStudents({ targetType: 'MAJOR', targetId: 'other' })
  assert.equal(reads, 1)
})

test('returning from roster rereads the original check and keeps the applied results page', async () => {
  const { state } = page('AaOrgConsole')
  state.canViewOrganizations = true
  state.referenceReturn = { targetType: 'CLASS', targetId: '17' }
  state.students.visible = true
  const reads = []
  state.$refs = { referencePanel: { pagination: { page: 3 },
    changePage: page => reads.push(page), openDetail: target => reads.push(target.targetId) } }
  await state.returnToReference()
  assert.deepEqual(reads, [3, '17'])
  assert.equal(state.students.visible, false)
  assert.equal(state.referenceReturn, null)
  await state.returnToReference()
  assert.equal(reads.length, 2)
})

test('opening an unrelated roster clears the previous check return target', async () => {
  const { state } = page('AaOrgConsole')
  state.referenceReturn = { targetType: 'CLASS', targetId: 'old' }
  state.reloadStudentDrawer = async () => {}
  await state.openStudents({ id: 'new', className: '另一个班' })
  assert.equal(state.referenceReturn, null)
})
