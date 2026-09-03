import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'
import test from 'node:test'

const source = fs.readFileSync(new URL('../src/modules/studentAffairs/views/StudentAffairsDashboardView.vue', import.meta.url), 'utf8')
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  .replace(/^import[^\n]*\n/gm, '')
  .replace('export default', 'globalThis.pageOptions =')
const env = {}
for (const name of ['AppAuditTrail', 'AppDateDisplay', 'AppExportButton', 'AppGlobalState', 'AppPageShell', 'AppPermissionButton', 'AppRiskTag', 'AppSectionCard', 'AppStatusTag']) env[name] = {}
vm.runInNewContext(script, env, { filename: 'StudentAffairsDashboardView.vue', timeout: 1000 })
const entries = (permissions, pageState = 'ready') => env.pageOptions.computed.crossCenterEntries.call({
  pageState,
  canBtn: (code) => permissions.includes(code)
})
const graduationPath = '/admin/graduation/risk-archive?panel=risk'

test('A1 graduation link consumes the target page canonical permission', () => {
  const result = entries(['graduationDesign.risk.view'])
  assert.equal(result.length, 1)
  assert.equal(result[0].path, graduationPath)
  assert.equal(result[0].code, 'graduationDesign.risk.view')
  const target = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationRiskArchiveView.vue', import.meta.url), 'utf8')
  assert.match(target, /canRiskView\(\)[^\n]*graduationDesign\.risk\.view/)
})
test('legacy or unrelated graduation permissions do not expose the risk entry', () => {
  for (const permissions of [[], ['graduation.risk.view'], ['graduationDesign.archive.view'], ['graduationDesign.dashboard.view']]) {
    assert.equal(entries(permissions).some((entry) => entry.path === graduationPath), false)
  }
})
test('each cross-center link requires its own existing permission', () => {
  for (const [code, path] of [['studentAffairs.orientation.view', '/admin/orientation'], ['internship.risk.view', '/admin/internship/risks']]) {
    const result = entries([code])
    assert.equal(result.length, 1)
    assert.equal(result[0].path, path)
  }
})
test('unready, forbidden and no-scope views do not expose cross-center links', () => {
  for (const state of ['loading', 'error', 'forbidden', 'empty']) {
    assert.equal(entries(['graduationDesign.risk.view', 'internship.risk.view'], state).length, 0)
  }
})
