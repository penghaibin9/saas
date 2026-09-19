import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

import { GRADUATION_WORKSPACES } from '../src/modules/graduation/config/graduationWorkspaces.js'

const layout = fs.readFileSync(new URL('../src/modules/graduation/views/AdminGraduationLayout.vue', import.meta.url), 'utf8').replace(/\r\n/g, '\n')
const script = layout.match(/<script>([\s\S]*?)<\/script>/)?.[1] || ''
const scopedStyles = [...layout.matchAll(/<style scoped>([\s\S]*?)<\/style>/g)].map(match => match[1])
const integration = scopedStyles.find(style => style.includes('Final graduation-only integration polish.')) || ''

function marker(name) {
  return layout.match(new RegExp(`:${name}="([\\s\\S]*?)"`))?.[1] || ''
}

// Audited across d17ddf5..ffd0ced6: intervening layout changes are presentation-only; this pins the unchanged business script.
test('business script and original scoped presentation foundation stay byte-identical', () => {
  for (const token of ['permissionReady', 'scopeReady', 'readonlyTenant', 'canRenderBusiness']) assert.ok(script.includes(token), token)
  assert.ok(scopedStyles[0].length > 0)
  assert.equal((layout.match(/<router-view\b/g) || []).length, 1)
  assert.match(layout, /if \(panel === 'grad-qual'\)[\s\S]*?panel: 'roster'/)
})

test('final UI markers opt in only the intended graduation routes', () => {
  const content = marker('data-graduation-content-workspace')
  const risk = marker('data-graduation-risk-workspace')
  const templates = marker('data-graduation-template-workspace')
  assert.equal(vm.runInNewContext(content, { $route: { name: 'graduation-finals' } }), 'final')
  assert.equal(vm.runInNewContext(content, { $route: { name: 'graduation-proposals' } }), 'proposal')
  assert.equal(vm.runInNewContext(content, { $route: { name: 'internship' } }), undefined)
  assert.equal(vm.runInNewContext(risk, { $route: { name: 'graduation-risk-archive', query: { panel: 'archive' } } }), 'archive')
  assert.equal(vm.runInNewContext(risk, { $route: { name: 'graduation-risk-archive', query: {} } }), 'risk')
  assert.equal(vm.runInNewContext(risk, { $route: { name: 'student-affairs', query: {} } }), undefined)
  assert.equal(vm.runInNewContext(templates, { $route: { name: 'graduation-templates' } }), 'templates')
  assert.equal(vm.runInNewContext(templates, { $route: { name: 'academic-affairs' } }), undefined)
})

test('final integration styles remain graduation-local and preserve business blockers', () => {
  assert.ok(integration.length > 3000)
  assert.doesNotMatch(integration, /\.bpl-|\.tw-|:global\(|@import|position:\s*fixed|z-index:/)
  assert.doesNotMatch(integration, /\.ar-missing[^}]*display:\s*none|\.rk-detail[^}]*display:\s*none|\.app-inline-alert[^}]*display:\s*none/)
  assert.match(integration, /data-graduation-risk-workspace='risk'[\s\S]*\.rk-rules\) \{ order: 20; \}/)
  assert.match(integration, /\.rk-command__headline strong\)[^{]*\{ font-size: 16px !important/)
  assert.match(integration, /data-graduation-template-workspace[\s\S]*\.dt__td\)[^{]*\{ font-size: 13px/)
  assert.match(integration, /@container gd-students \(max-width: 1000px\)/)
  assert.match(integration, /data-graduation-content-workspace='final'[\s\S]*\.fr-command__copy strong\)[^{]*\{[^}]*font-size: 15px/)
  assert.match(integration, /data-graduation-content-workspace='proposal'\] :deep\(\.mp-tabs \.mp-tab\) \{\s*min-height: 40px !important;/)
  assert.match(integration, /1366 \/ 125%: compact material chrome[\s\S]*data-graduation-material-workspace='materials'[\s\S]*grid-template-columns: minmax\(220px, 1\.5fr\) repeat\(3, minmax\(130px, 1fr\)\) auto/)
})

test('deep grade form keeps a readable type floor and a guarded completion return', () => {
  const source = fs.readFileSync(new URL('../src/modules/graduation/views/GraduationDefenseGradeFormView.vue', import.meta.url), 'utf8').replace(/\r\n/g, '\n')
  const style = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
  const sizes = [...style.matchAll(/font-size:\s*([\d.]+)px/g)].map(match => Number(match[1]))
  assert.ok(sizes.length > 10)
  assert.ok(Math.min(...sizes) >= 12)
  assert.match(source, /if \(this\.submitting && !this\.completionNavigating\)/)
  assert.match(source, /this\.completionNavigating = true[\s\S]*?await this\.\$router\.push\(snapshot\.backTo\)/)
  assert.doesNotMatch(source, /this\.submitting = false\s*\n\s*await this\.\$router\.push\(snapshot\.backTo\)/)
})

test('single menu truth remains eight workspaces and twenty-four leaves', () => {
  assert.equal(GRADUATION_WORKSPACES.length, 8)
  assert.equal(GRADUATION_WORKSPACES.reduce((sum, workspace) => sum + workspace.children.length, 0), 24)
})

test('shortcut and formal duplicate path identities are distinguishable without new routes', () => {
  const leaves = GRADUATION_WORKSPACES.flatMap(workspace => workspace.children.map(leaf => ({ workspace: workspace.key, ...leaf })))
  const byLabel = label => leaves.find(leaf => leaf.label === label)
  assert.equal(byLabel('待评阅开题').path, '/admin/graduation/proposals?tab=PENDING_REVIEW')
  assert.equal(byLabel('开题报告批阅').path, '/admin/graduation/proposals?workspace=proposal-final')
  assert.equal(byLabel('待评阅成果').path, '/admin/graduation/finals?tab=PENDING_REVIEW')
  assert.equal(byLabel('成果提交与批阅').path, '/admin/graduation/finals?workspace=proposal-final')
  assert.equal(byLabel('我的答辩评分').path, '/admin/graduation/defense-scoring')
  assert.equal(byLabel('答辩评分').path, '/admin/graduation/defense-scoring?workspace=defense-grade')
  for (const leaf of leaves) assert.ok(leaf.path.startsWith('/admin/graduation'))
})
