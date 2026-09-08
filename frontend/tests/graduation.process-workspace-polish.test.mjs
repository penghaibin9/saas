import { workspaceSection, foundationStyles, legacyStyleImportLayout } from './graduation-workspace-style-sections.mjs'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const base = new URL('../src/modules/graduation/', import.meta.url)
const rawLayout = fs.readFileSync(new URL('views/AdminGraduationLayout.vue', base), 'utf8')
const layout = rawLayout.replace(/      :data-graduation-defense-workspace="[\s\S]*?"\n/, '')
const css = workspaceSection('process')
const marker = layout.match(/:data-graduation-process-workspace="([\s\S]*?)"/)?.[1]
const script = layout.match(/<script>([\s\S]*?)<\/script>/)[1]
const hash = text => createHash('sha256').update(text).digest('hex')
const scope = '.gd-business-view[data-graduation-process-workspace'

function loadLayout() {
  const calls = { pushes: [], replaces: [] }
  const store = { selectedBatchId: '71', initialized: true, ensureLoaded: async () => {} }
  const router = { push: async value => calls.pushes.push(value), replace: async value => calls.replaces.push(value) }
  const options = vm.runInNewContext(script.replace(/^import .+\n/gm, '').replace('export default', 'globalThis.layout ='), {
    URLSearchParams, BasePortalLayout: {}, LoadingState: {}, EmptyState: {}, AppInlineAlert: {},
    GraduationBatchStrip: {}, GraduationExtensionAdminPanel: {}, graduationPickerAdapters: {},
    useGraduationBatchStore: () => store, graduationApi: {},
    matchPermission: (patterns, key) => patterns.includes('*') || patterns.includes(key), router
  }, { timeout: 1000 })
  const instance = { ...options.data(), $route: { name: 'graduation-process', path: '/admin/graduation/process', fullPath: '/admin/graduation/process?batchId=71', query: { batchId: '71' }, meta: {} } }
  for (const [name, fn] of Object.entries(options.methods)) instance[name] = fn.bind(instance)
  for (const [name, fn] of Object.entries(options.computed)) Object.defineProperty(instance, name, { get: () => fn.call(instance) })
  return { instance, options, store, calls }
}

test('existing permission-gated business outlet owns the process presentation boundary', () => {
  assert.ok(marker, 'missing process presentation marker')
  const start = layout.indexOf('v-if="canRenderBusiness"')
  const end = layout.indexOf('    >', start)
  assert.ok(start >= 0 && end > start)
  assert.ok(layout.slice(start, end).includes(':data-graduation-process-workspace='))
  assert.equal((layout.match(/<router-view\b/g) || []).length, 1)
})

test('only the existing workbench and action route names opt in', () => {
  assert.ok(marker)
  for (const [name, expected] of [['graduation-process', 'workbench'], ['graduation-process-action', 'form']]) {
    assert.equal(vm.runInNewContext(marker, { $route: { name } }), expected)
  }
  assert.deepEqual([...marker.matchAll(/'([^']+)'/g)].map(match => match[1]), ['graduation-process', 'workbench', 'graduation-process-action', 'form'])
})

test('students, planning pages, other modules and unknown names omit the boundary', () => {
  assert.ok(marker)
  for (const name of [undefined, null, 'graduation-process-other', 'graduation-dashboard', 'graduation-students', 'graduation-mentors', 'graduation-mentor-assign', 'graduation-topic-lib', 'graduation-material-center', 'graduation-defense-scoring', 'student-affairs', 'internship']) {
    assert.equal(vm.runInNewContext(marker, { $route: { name } }), undefined, String(name))
  }
})

test('normalizing only the new marker and stylesheet restores the complete parent file', () => {
  // Exclude the later, independently protected material presentation addition.
  const withoutMaterial = legacyStyleImportLayout(layout).replace(/      :data-graduation-material-workspace="[\s\S]*?"\n/, '')
    .replace(/\n<style src="\.\.\/styles\/graduation-material-workspace\.css"><\/style>\n?$/, '')
  const original = withoutMaterial.replace(/      :data-graduation-process-workspace="[\s\S]*?"\n/, '')
    .replace(/\n<style src="\.\.\/styles\/graduation-process-workspace\.css"><\/style>\n?$/, '')
  assert.equal(hash(original), 'b783e18b64d6a7dccefa27457358401507f9f2b73f8c03bb3b03cb09ffcb04ff')
})

test('foundation remains frozen and the canonical stylesheet is imported once', () => {
  assert.equal(hash(foundationStyles()), 'ab00fa350f0927d7d9250c03bdede1ccfae3bf39878b489993b38488079aff64')
  assert.equal((rawLayout.match(/<style src="@\/modules\/graduation\/styles\/graduation-workspaces\.css"><\/style>/g) || []).length, 1)
  assert.equal((rawLayout.match(/<style\s+src=/g) || []).length, 1)
})

test('every process selector stays within the route marker, with no suppression of business states', () => {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const selectors = [...text.matchAll(/([^{}]+)\{/g)].map(match => match[1].trim()).filter(s => !s.startsWith('@'))
  assert.ok(selectors.length >= 60)
  for (const selector of selectors) assert.ok(selector.startsWith(scope), selector)
  assert.doesNotMatch(text, /display:\s*none|visibility:\s*hidden|pointer-events|opacity:\s*0|position:\s*fixed|:global\(|\.tw-|\.bpl-|:root|z-index/)
})

test('readability floors and theme-sensitive fields/actions are explicit', () => {
  const sizes = [...css.matchAll(/font-size:\s*([\d.]+)px/g)].map(match => Number(match[1]))
  assert.ok(sizes.length > 15 && Math.min(...sizes) >= 12)
  assert.match(css, /min-height:\s*36px/)
  assert.match(css, /background:\s*var\(--field-bg/)
  assert.match(css, /color:\s*var\(--pri-on/)
  assert.match(css, /:focus-visible[\s\S]*?outline:\s*2px solid var\(--pri/)
})

test('the sole important declaration counters the legacy 9px eyebrow only', () => {
  const text = css.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.equal((text.match(/!important/g) || []).length, 1)
  assert.match(text, /\[data-graduation-process-workspace='workbench'\] \.gp-context__identity \.gp-context__eyebrow\s*\{\s*font-size:\s*12px !important;\s*\}/)
})

test('content-width adaptation keeps the queue scrollable and form fields readable', () => {
  assert.match(css, /container:\s*gd-process \/ inline-size/)
  for (const width of [1120, 820, 560]) assert.ok(css.includes(`@container gd-process (max-width: ${width}px)`))
  assert.match(css, /\.gp-stu-list\s*\{[^}]*grid-auto-flow:\s*column;[^}]*overflow:\s*auto/)
  assert.match(css, /textarea\.ie-in\s*\{[^}]*min-height:\s*104px;[^}]*resize:\s*vertical/)
  assert.match(css, /\.gp-context-board strong\s*\{[^}]*white-space:\s*normal/)
})

test('actual layout permissions remain fail closed and tenant readonly stays readonly', () => {
  const { instance } = loadLayout()
  assert.equal(instance.canRenderBusiness, false)
  instance.ctx = { permissionPatterns: ['*'], readonlyTenant: true }
  instance.permissionReady = true
  assert.equal(instance.canRenderBusiness, false)
  instance.scopeReady = true
  assert.equal(instance.canRenderBusiness, true)
  assert.equal(instance.businessCtx.writeEnabled, false)
  instance.permissionReady = false
  assert.equal(instance.businessCtx.writeEnabled, false)
})

test('actual module navigation retains process deep-link identity without cross-module leakage', () => {
  const { instance, calls } = loadLayout()
  instance.onMenuSelect({ path: '/admin/graduation/process?panel=guidance&studentId=127&queue=late&source=workbench#record' })
  instance.onMenuSelect({ path: '/admin/graduation/process/127/guidance?batchId=88&studentId=127' })
  instance.onMenuSelect({ path: '/admin/internship?panel=list' })
  assert.deepEqual(calls.pushes, ['/admin/graduation/process?panel=guidance&studentId=127&queue=late&source=workbench&batchId=71#record', '/admin/graduation/process/127/guidance?batchId=88&studentId=127', '/admin/internship?panel=list'])
})

test('late process-context completion cannot rewrite another center URL', async () => {
  const { instance, calls } = loadLayout()
  instance.$route = { path: '/admin/student-affairs', query: {}, fullPath: '/admin/student-affairs' }
  await instance.syncBatchToUrl()
  assert.equal(calls.replaces.length, 0)
})
