import { workspaceSection, foundationStyles, legacyStyleImportLayout } from './graduation-workspace-style-sections.mjs'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const read = path => fs.readFileSync(new URL(`../src/modules/graduation/${path}`, import.meta.url), 'utf8')
const layout = read('views/AdminGraduationLayout.vue')
const css = foundationStyles(read('styles/graduation-workspaces.css'))
const script = layout.match(/<script>([\s\S]*?)<\/script>/)?.[1] || ''
const style = layout.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
const marker = layout.match(/:data-planning-workspace="([\s\S]*?)"/)?.[1]
const PLANNING_ROUTES = [
  'graduation-mentors', 'graduation-mentor-conflicts', 'graduation-topic-lib',
  'graduation-topic-rounds', 'graduation-topic-changes'
]
const BOUNDARY = '.gd-business-view[data-planning-workspace]'
const START = '/* Planning workspaces: presentation only, selected by existing route names.'
const hash = text => createHash('sha256').update(text).digest('hex')

function loadLayout() {
  const calls = { pushes: [], replaces: [], reads: 0 }
  const store = { selectedBatchId: '71', initialized: true, ensureLoaded: async () => {} }
  const ctx = { permissionReady: true, permissionPatterns: ['*'], scopeConfigured: true }
  const api = { getContext: async () => { calls.reads++; return { code: 0, data: ctx } } }
  const options = vm.runInNewContext(script.replace(/^import .+\n/gm, '').replace('export default', 'globalThis.layout ='), {
    URLSearchParams,
    BasePortalLayout: {}, LoadingState: {}, EmptyState: {}, AppInlineAlert: {},
    GraduationBatchStrip: {}, GraduationExtensionAdminPanel: {}, graduationPickerAdapters: {},
    useGraduationBatchStore: () => store, graduationApi: api,
    matchPermission: (patterns, key) => patterns.includes('*') || patterns.includes(key),
    router: { push: async value => { calls.pushes.push(value) }, replace: async value => { calls.replaces.push(value) } }
  }, { timeout: 1000 })
  return { options, store, calls }
}

function instance(options, overrides = {}) {
  const target = { ...options.data(), $route: { name: 'graduation-mentors', path: '/admin/graduation/mentors', fullPath: '/admin/graduation/mentors?batchId=71', query: { batchId: '71' }, meta: {} }, ...overrides }
  for (const [key, method] of Object.entries(options.methods)) target[key] = method.bind(target)
  for (const [key, getter] of Object.entries(options.computed)) Object.defineProperty(target, key, { get: () => getter.call(target) })
  return target
}

test('presentation marker is attached to the existing permission-gated business view', () => {
  assert.ok(marker, 'missing module-local presentation boundary')
  assert.match(layout, /v-if="canRenderBusiness"\s+class="gd-business-view"\s+:data-planning-workspace=/)
  assert.match(layout, /:class="\{ 'gd-student-readonly': isStudentList && !canManageStudents \}"/)
  assert.equal((layout.match(/<router-view\b/g) || []).length, 1)
  assert.match(layout, /<router-view v-else :key="businessViewKey" :ctx="businessCtx"/)
})

test('exact existing leaf route names opt in without a second navigation source', () => {
  assert.ok(marker)
  for (const name of PLANNING_ROUTES) assert.equal(vm.runInNewContext(marker, { $route: { name } }), true, name)
  assert.deepEqual([...marker.matchAll(/'([^']+)'/g)].map(item => item[1]), PLANNING_ROUTES)
})

test('nested forms and all other modules omit the marker, rather than a truthy false attribute', () => {
  for (const name of [undefined, null, 'graduation-students', 'graduation-dashboard', 'graduation-material-center', 'graduation-risk-archive', 'graduation-topic-lib-edit', 'graduation-topic-lib-detail', 'graduation-mentor-assign', 'graduation-mentor-detail', 'graduation-topic-round-create', 'graduation-topic-change-detail', 'student-affairs', 'internship', ...PLANNING_ROUTES.map(name => name + '-other')]) {
    assert.equal(vm.runInNewContext(marker, { $route: { name } }), undefined, String(name))
  }
})

test('parent layout keeps its production permission, outlet and navigation contracts', () => {
  const normalized = legacyStyleImportLayout(layout)
  assert.equal((layout.match(/<router-view\b/g) || []).length, 1)
  assert.match(normalized, /canRenderBusiness\(\) \{ return !!\(this\.ctx && this\.permissionReady && this\.scopeReady\) \}/)
  assert.match(normalized, /resolveWorkspaceDestination\(path\)/)
  assert.match(normalized, /if \(query\.has\('batchId'\)\) return path/)
  assert.match(normalized, /router\.push\(target\)\.catch\(\(\) => \{\}\)/)
  assert.match(normalized, /if \(panel === 'grad-qual'\)[\s\S]*?panel: 'roster'/)
  assert.doesNotMatch(style, /\.tw-|\.bpl-|:root|\bbody\s*\{/)
})

test('real layout permission and read-only computations remain closed until ready', () => {
  const { options } = loadLayout()
  const target = instance(options)
  assert.equal(target.canRenderBusiness, false)
  target.ctx = { permissionPatterns: ['*'], readonlyTenant: true }
  target.permissionReady = true
  assert.equal(target.canRenderBusiness, false)
  target.scopeReady = true
  assert.equal(target.canRenderBusiness, true)
  assert.equal(target.businessCtx.writeEnabled, false)
  target.ctx.readonlyTenant = false
  assert.equal(target.businessCtx.writeEnabled, true)
})

test('real navigation adapter keeps queries, explicit batch and cross-center isolation', async () => {
  const { options, calls } = loadLayout()
  const target = instance(options)
  target.onMenuSelect({ path: '/admin/graduation/topic-rounds?panel=choices&roundId=8#records' })
  target.onMenuSelect({ path: '/admin/graduation/mentors?batchId=90' })
  target.onMenuSelect({ path: '/admin/internship' })
  assert.deepEqual(calls.pushes, ['/admin/graduation/topic-rounds?panel=choices&roundId=8&batchId=71#records', '/admin/graduation/mentors?batchId=90', '/admin/internship'])
  assert.equal(calls.reads, 0)
})

test('material metric grid is owned only by the material route and cannot leak into mentor conflicts', () => {
  const material = workspaceSection('material')
  assert.doesNotMatch(css.slice(0, css.indexOf(START)), /\.mc-summary/)
  assert.match(material, /\[data-graduation-material-workspace='materials'\] \.mc-page \.mc-summary\s*\{[^}]*repeat\(auto-fit, minmax\(min\(136px, 100%\), 1fr\)\)/)
  assert.doesNotMatch(material, /\[data-planning-workspace\]/)
})

test('unrelated preamble, risk and student boundary text remains unchanged after material extraction', () => {
  assert.ok(css.includes(START))
  const original = css.slice(0, css.indexOf(START))
  assert.equal(hash(original), '3881968e4e39c06624b275203205028bf3e4a2cc5757ca99ef351e5a2b230993')
})

test('every new selector is inside the five-page marker and no hiding or new importance is introduced', () => {
  const body = css.slice(css.indexOf(START)).replace(/\/\*[\s\S]*?\*\//g, '')
  const selectors = [...body.matchAll(/([^{}]+)\{/g)].map(item => item[1].trim()).filter(text => !text.startsWith('@'))
  assert.ok(selectors.length > 50)
  for (const selector of selectors) assert.ok(selector.startsWith(BOUNDARY), selector)
  assert.doesNotMatch(body, /!important|display:\s*none|visibility:\s*hidden|opacity:\s*0(?:\s|;)|pointer-events:\s*none/)
  assert.doesNotMatch(body, /\.tw-|\.bpl-|:root|\bbody\s*\{|z-index|position:\s*fixed/)
})

test('planning text and fields consume existing theme tokens with keyboard focus preserved', () => {
  const body = css.slice(css.indexOf(START))
  const sizes = [...body.matchAll(/font-size:\s*([\d.]+)px/g)].map(item => Number(item[1]))
  assert.ok(sizes.length > 15 && Math.min(...sizes) >= 12)
  assert.match(body, /\.af__control\s*\{[^}]*min-height: 36px;[^}]*var\(--field-bg/)
  assert.match(body, /:focus-visible\s*\{[^}]*outline: 2px solid var\(--pri/)
  assert.match(body, /\.mp-btn--primary\s*\{[^}]*color: var\(--pri-on/)
  assert.match(body, /\.mp-link--danger\s*\{[^}]*var\(--danger/)
})

test('responsive layout follows module content width while retaining the table scroller and all conflict text', () => {
  const body = css.slice(css.indexOf(START))
  assert.match(body, /container: gd-planning \/ inline-size/)
  assert.match(body, /@container gd-planning \(max-width: 1080px\)/)
  assert.match(body, /@container gd-planning \(max-width: 760px\)/)
  assert.match(body, /\.dt__scroll\s*\{[^}]*overflow-x: auto/)
  assert.match(body, /:is\(\.mc-list strong, \.mc-list span\)\s*\{[^}]*white-space: normal/)
  assert.match(body, /\.mc-scope-note\s*\{[^}]*font-size: 12px/)
})
