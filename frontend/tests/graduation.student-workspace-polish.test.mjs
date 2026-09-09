import { foundationStyles } from './graduation-workspace-style-sections.mjs'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import process from 'node:process'
import { createHash } from 'node:crypto'
import vm from 'node:vm'
import test from 'node:test'

const source = fs.readFileSync(process.env.STUDENT_SOURCE || new URL('../src/modules/graduation/views/GraduationStudentListView.vue', import.meta.url), 'utf8')
const moduleCss = foundationStyles(fs.readFileSync(process.env.GRADUATION_CSS || new URL('../src/modules/graduation/styles/graduation-workspaces.css', import.meta.url), 'utf8'))
const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
const style = source.match(/<style scoped>([\s\S]*?)<\/style>/)[1]
const plain = value => JSON.parse(JSON.stringify(value))

// Execute the production page options, with external component and API/Router IO doubles.
function page({ panel = 'roster', writeEnabled = true, batchId = '71' } = {}) {
  const calls = { reads: [], exports: [], writes: [], pushes: [], replaces: [] }
  const data = [{ id: '7', name: '测试学生', studentNo: 'FAKE-0007' }]
  const store = { selectedBatchId: batchId, selectedBatchName: '隔离测试批次' }
  const queryBuilder = (filters, extra = {}) => ({ ...filters, ...extra })
  const gdStudentApi = {
    getStudents: async params => { calls.reads.push(params); return { code: 0, data: { list: data, total: 31 } } },
    getStats: async () => ({ code: 0, data: { total: 31, withoutTopic: 4 } }),
    getStudentGroups: async () => ({ code: 0, data: [] }),
    exportStudents: async params => { calls.exports.push(params); return { code: 0, data: {} } },
    setEligibility: async (...args) => { calls.writes.push(['eligibility', ...args]); return { code: 0, data: {} } },
    setStage: async (...args) => { calls.writes.push(['stage', ...args]); return { code: 0, data: {} } },
    batchArchive: async (...args) => { calls.writes.push(['archive', ...args]); return { code: 0, data: {} } }
  }
  const components = Object.fromEntries('ModulePageShell ModuleToolbar AdvancedFilter DataTable StatusTag RiskTag LoadingState ErrorState EmptyState AppConfirmDialog AppSensitiveText AppExportButton AppPageGuide AppExcelImportDrawer'.split(' ').map(name => [name, {}]))
  const constants = Object.fromEntries('GD_STAGE GD_RISK_LEVEL HAS_TOPIC GD_ELIGIBILITY GD_GRAD_QUAL HAS_DEFENSE_GROUP MATERIAL_COMPLETE ARCHIVE_VIEW'.split(' ').map(name => [name, []]))
  const sandbox = { ...components, ...constants, gdStudentApi, useGraduationBatchStore: () => store,
    buildStudentQuery: queryBuilder, exportFilenameHint: (...args) => args.join('-'), toast: { success() {}, error() {} } }
  const options = vm.runInNewContext(script.replace(/^import[\s\S]*?from ['"][^'"]+['"]\s*$/gm, '').replace('export default', 'globalThis.options ='), sandbox, { timeout: 1000 })
  const p = { ...options.data(), ctx: { writeEnabled, currentRole: { roleName: '测试角色' }, dataScope: { scopeName: '测试范围' } },
    $route: { query: { panel, batchId, page: '3', keyword: '保留词' } },
    $router: { push: value => { calls.pushes.push(value); return Promise.resolve() },
      replace: value => { calls.replaces.push(value); return Promise.resolve() },
      resolve: ({ path, query }) => ({ fullPath: path + '?' + new URLSearchParams(query) }) }
  }
  for (const [key, method] of Object.entries(options.methods)) p[key] = method.bind(p)
  for (const [key, getter] of Object.entries(options.computed)) Object.defineProperty(p, key, { get: () => getter.call(p) })
  p.applyInitialRouteState(p.$route.query)
  return { p, calls, store, api: gdStudentApi, options }
}

test('only the three approved task labels differ in the complete production script', () => {
  const normalized = script.replace("label: '选题 / 导师 / 资格'", "label: '关系与资格'")
    .replace("label: '材料 / 答辩'", "label: '材料与答辩'").replace("label: '毕业资格 / 归档'", "label: '收口与归档'")
  assert.equal(createHash('sha256').update(normalized).digest('hex'), '4f11fb4f9ad979f005cdaa957b5b486c93432887b323b087d81738f0c3acf5fb')
})

test('five task groups retain all eleven panel keys and original default destinations', () => {
  const { p } = page()
  assert.deepEqual(plain(p.primaryGroups.map(({ key, defaultPanel, panels }) => ({ key, defaultPanel, panels }))), [
    { key: 'roster', defaultPanel: 'roster', panels: ['roster'] },
    { key: 'progress', defaultPanel: 'progress', panels: ['progress', 'risk'] },
    { key: 'relations', defaultPanel: 'topic', panels: ['topic', 'mentor', 'eligibility', 'grouping'] },
    { key: 'materials', defaultPanel: 'materials', panels: ['materials', 'defense'] },
    { key: 'closure', defaultPanel: 'grad-qual', panels: ['grad-qual', 'archive'] }
  ])
  assert.equal(new Set(p.primaryGroups.flatMap(group => group.panels)).size, 11)
})

test('task labels match the supplied HTML and selected states are exposed without new navigation', () => {
  const { p } = page()
  assert.deepEqual(plain(p.primaryGroups.map(group => group.label)), ['名单', '进度与风险', '选题 / 导师 / 资格', '材料 / 答辩', '毕业资格 / 归档'])
  assert.match(source, /:aria-pressed="activeGroupKey === group.key"/)
  assert.match(source, /:aria-pressed="activePanel === panel.key"/)
  assert.match(source, /@click="switchGroup\(group\)"/)
  assert.match(source, /@click="switchPanel\(panel.key\)"/)
})

test('panel changes preserve original filter presets, batch, keyword and selection reset', () => {
  const expected = { progress: ['stage', 'GUIDING'], risk: ['riskLevel', 'HIGH'], topic: ['hasTopic', 'false'], mentor: ['hasTopic', 'true'], eligibility: ['eligibility', 'PENDING'], materials: ['materialComplete', 'false'], defense: ['hasDefenseGroup', 'false'], 'grad-qual': ['gradQualStatus', 'UNKNOWN'], archive: ['archiveView', 'candidates'] }
  const { p, calls } = page()
  for (const [panel, [key, value]] of Object.entries(expected)) {
    p.selectedIds = ['7']; p.switchPanel(panel)
    assert.equal(p.filters[key], value, panel)
    assert.equal(p.filters.keyword, '保留词')
    assert.equal(p.page, 1); assert.deepEqual(plain(p.selectedIds), [])
    assert.equal(calls.replaces.at(-1).query.batchId, '71')
  }
})

test('each panel remains a page-local task, not a new sidebar or copied route', () => {
  for (const panel of ['roster', 'progress', 'risk', 'topic', 'mentor', 'eligibility', 'grouping', 'materials', 'defense', 'grad-qual', 'archive']) {
    const { p, calls } = page({ panel })
    assert.equal(p.activePanel, panel)
    p.openDetail({ id: '7' })
    const target = calls.pushes.at(-1)
    assert.equal(target.path, '/admin/graduation/students/7')
    const returnTo = new URL(target.query.returnTo, 'https://test.invalid')
    assert.equal(returnTo.searchParams.get('panel'), panel)
    assert.equal(returnTo.searchParams.get('page'), '3')
    assert.equal(returnTo.searchParams.get('keyword'), '保留词')
  }
})

test('read-only toolbar stays disabled and does not open write entrypoints', () => {
  for (const panel of ['roster', 'grouping', 'archive']) {
    const { p, calls } = page({ panel, writeEnabled: false })
    p.selectedIds = ['7']
    assert.ok(p.toolbarActions.every(action => action.disabled))
    for (const action of ['create', 'import', 'batchGroup', 'batchArchive']) p.onToolbar(action)
    assert.equal(calls.pushes.length, 0); assert.equal(p.importVisible, false); assert.equal(p.confirm.visible, false)
  }
})

test('the readonly academic mirror and every real Excel callback stay in the template', () => {
  assert.match(source, /毕业资格是教务只读镜像/)
  assert.match(source, /AppSensitiveText :value="row.studentNo"/)
  for (const method of ['downloadImportTemplate()', 'uploadImportXlsx(file)', 'importConfirm(rows, previewToken)', 'downloadImportErrors(rows, errors)']) assert.ok(source.includes(`gdStudentApi.${method}`))
  assert.match(source, /@imported="onImported"/)
  assert.match(source, /:submitting="submitting" @confirm="onConfirm"/)
})

test('export still uses current filters and batch rather than only the displayed page', async () => {
  const { p, calls } = page({ panel: 'risk' })
  await p.exportStudentsFn()
  assert.equal(calls.exports.length, 1)
  assert.equal(calls.exports[0].riskLevel, 'HIGH')
  assert.equal(calls.exports[0].batchId, '71')
  assert.equal(calls.exports[0].keyword, '保留词')
  assert.equal(calls.exports[0].page, undefined)
})

test('unavailable statistics remain unknown and list failures do not become success', async () => {
  const { p, api } = page()
  assert.ok(p.heroMetrics.every(metric => metric.value === '—'))
  p.statsError = '读取失败'; assert.match(p.workConclusion, /全量统计暂未读取/)
  api.getStudents = async () => ({ code: 403001, message: '测试权限失败' })
  assert.equal(await p.load(), false); assert.equal(p.error, '测试权限失败'); assert.equal(p.rows.length, 0)
})

test('student presentation uses container width and readable controls without global shell overrides', () => {
  assert.match(source, /class="gd-student-workspace"/)
  assert.match(style, /container:\s*gd-students \/ inline-size/)
  assert.match(style, /@container gd-students/)
  assert.match(style, /\.dt__scroll\)[\s\S]*?overflow-x:\s*auto/)
  assert.doesNotMatch(style, /font-size:\s*(?:8|9|10)px|!important|\.tw-|\.bpl-|:global\(/)
  assert.doesNotMatch(moduleCss, /\.gd-student-page/)
  assert.match(style, /min-height:\s*36px/)
})

test('unrelated risk and preamble styles remain frozen after material presentation moved to its owner', () => {
  const boundary = moduleCss.indexOf('/* Student roster')
  assert.ok(boundary > 0)
  // Only the audited material compression block and its two media rules moved out.
  assert.doesNotMatch(moduleCss.slice(0, boundary), /\.mc-(?:summary|hero|filters|tabs|panel|table-wrap)/)
  assert.equal(createHash('sha256').update(moduleCss.slice(0, boundary)).digest('hex'), '3c5cb582374510e172953f14c98c12d96f643a567804caf3d22f2d8d6f2481fd')
})
