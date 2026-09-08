import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'
import { workspaceCss, workspaceCssUrl, workspaceSection, foundationStyles, legacyStyleImportLayout } from './graduation-workspace-style-sections.mjs'

const root = new URL('../src/modules/graduation/', import.meta.url)
const layout = fs.readFileSync(new URL('views/AdminGraduationLayout.vue', root), 'utf8')
const marker = layout.match(/:data-graduation-defense-workspace="([\s\S]*?)"/)?.[1]
const css = workspaceSection('defense')
const hash = text => createHash('sha256').update(text).digest('hex')
const identities = [
  ['graduation-defense', 'schedule'], ['graduation-defense-scoring', 'scoring'],
  ['graduation-defense-confirmation', 'confirmation'], ['graduation-grade-ledger', 'grades']
]

test('four original defense routes have separate presentation identities', () => {
  assert.ok(marker)
  assert.deepEqual([...marker.matchAll(/'([^']+)'/g)].map(m => m[1]), identities.flat())
  for (const [name, expected] of identities) assert.equal(vm.runInNewContext(marker, { $route: { name } }), expected)
})

test('plagiarism, review, forms, aliases and other modules never inherit defense styles', () => {
  for (const name of [undefined, null, 'graduation-defense-grade', 'graduation-defense-group-create', 'graduation-defense-group-edit', 'graduation-defense-grade-student-form', 'graduation-defense-grade-form', 'graduation-plagiarism-ledger', 'graduation-review-tasks', 'graduation-students', 'graduation-process', 'graduation-risk-archive', 'internship', 'student-affairs', ...identities.map(([name]) => name + '-other')]) {
    assert.equal(vm.runInNewContext(marker, { $route: { name } }), undefined, String(name))
  }
})

test('the exact original single-style-owner architecture requirement is restored', () => {
  const styleFiles = fs.readdirSync(new URL('styles/', root)).filter(name => name.endsWith('.css')).sort()
  assert.deepEqual(styleFiles, ['graduation-workspaces.css'])
  assert.equal((layout.match(/<style src="@\/modules\/graduation\/styles\/graduation-workspaces\.css"><\/style>/g) || []).length, 1)
  assert.equal((layout.match(/<style\s+src=/g) || []).length, 1)
  assert.ok(layout.trimEnd().endsWith('<style src="@/modules/graduation/styles/graduation-workspaces.css"></style>'))
  for (const selector of ['.gd-business-view', '.gd-student-page', '.mc-summary', '.rk-rules']) assert.ok(workspaceCss.includes(selector), selector)
  assert.equal(fs.realpathSync(workspaceCssUrl), fs.realpathSync(new URL('styles/graduation-workspaces.css', root)))
})

test('consolidation retains every previous process and material declaration byte for byte', () => {
  assert.equal(hash(workspaceSection('process')), 'e13f186ec4bfb709e6303569c8da150810f7caa21e992896a6267ddf0b3f111d')
  assert.equal(hash(workspaceSection('material')), '4393cd1c08291c1f25ca7fa6e6fd1a05e6a23c1dd9a4c1d0c1a1a5c861dc5cc8')
  assert.equal(hash(foundationStyles()), 'ab00fa350f0927d7d9250c03bdede1ccfae3bf39878b489993b38488079aff64')
  assert.equal(workspaceSection('student-host'), '.gd-business-view .gd-student-page { min-width: 0; }\n')
})

test('reversing only display marker and stylesheet consolidation restores the entire previous parent', () => {
  const prior = legacyStyleImportLayout(layout).replace(/      :data-graduation-defense-workspace="[\s\S]*?"\n/, '')
    + '\n<style src="../styles/graduation-process-workspace.css"></style>\n'
    + '\n<style src="../styles/graduation-material-workspace.css"></style>\n'
  assert.equal(hash(prior), 'f27e5500b3c8ebbe517750202ca1dd96366a26bcc6e36fb9f91314498373c48e')
})

test('parent business script, permission gate, router outlet and grad-qual compatibility are untouched', () => {
  assert.equal(hash(legacyStyleImportLayout(layout).match(/<script>([\s\S]*?)<\/script>/)[1]), '04895c6dfa36018a5bb0a50b45d2e841689d56048b01dbaaa4c30d915a224c91')
  assert.equal(hash(layout.match(/<style scoped>([\s\S]*?)<\/style>/)[1]), 'b8312f8500649ccabaeed4fe70d3bee87af8245fa413e1fddc99074a0986b3c5')
  assert.match(layout, /v-if="canRenderBusiness"[\s\S]*?:data-graduation-defense-workspace=/)
  assert.equal((layout.match(/<router-view\b/g) || []).length, 1)
  assert.match(layout, /if \(panel === 'grad-qual'\)[\s\S]*?panel: 'roster'/)
})

test('every defense selector has an explicit module and route boundary', () => {
  const body = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const selectors = [...body.matchAll(/([^{}]+)\{/g)].map(m => m[1].trim()).filter(s => !s.startsWith('@'))
  assert.ok(selectors.length > 50)
  for (const selector of selectors) assert.ok(selector.startsWith('.gd-business-view[data-graduation-defense-workspace]'), selector)
  assert.doesNotMatch(body, /:root|:global\(|\.tw-|\.bpl-|@import/)
})

test('visual rules do not replace responsibilities, suppress gaps or unlock commands', () => {
  const body = css.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(body, /display:\s*none|visibility:\s*hidden|pointer-events|opacity:|!important|(?:^|[;{])\s*content:/)
  for (const state of ['ds-danger', 'ds-preflight-warning', 'gp-miss', 'ds-receipt', 'dg-receipt']) assert.ok(body.includes('.' + state), state)
})

test('readable typography and themed fields do not depend on hard white backgrounds', () => {
  const sizes = [...css.matchAll(/font-size:\s*([\d.]+)px/g)].map(m => Number(m[1]))
  assert.ok(sizes.length > 20 && Math.min(...sizes) >= 12)
  assert.match(css, /min-height: 36px/)
  assert.match(css, /background: var\(--field-bg/)
  assert.match(css, /color: var\(--pri-on/)
  assert.match(css, /:focus-visible\s*\{[^}]*outline: 2px solid var\(--pri/)
})

test('layout adapts intrinsically to actual content width and keeps table scrolling local', () => {
  assert.match(css, /\.gp-layout\s*\{[^}]*display: flex;[^}]*flex-wrap: wrap/)
  assert.match(css, /\.gp-main\s*\{[^}]*flex: 999 1 520px/)
  assert.match(css, /\.dt__scroll\s*\{[^}]*overflow-x: auto/)
  assert.match(css, /@container gd-defense-queue \(min-width: 480px\)/)
  const contained = [...css.matchAll(/([^{}]+)\{[^{}]*\bcontainer:/g)].map(m => m[1].trim())
  assert.deepEqual(contained, ['.gd-business-view[data-graduation-defense-workspace] .gp-side'])
  assert.doesNotMatch(css, /position:\s*fixed|z-index|transform:|contain:/)
})

test('long identity, receipt and role text remains available instead of ellipsis-only evidence', () => {
  assert.match(css, /\.gp-context__identity strong\s*\{[^}]*white-space: normal;[^}]*overflow-wrap: anywhere/)
  assert.match(css, /\.dg-command__facts > div:last-child b\s*\{[^}]*font-size: 16px/)
  assert.doesNotMatch(css, /text-overflow:\s*ellipsis|font-size:\s*0/)
})
