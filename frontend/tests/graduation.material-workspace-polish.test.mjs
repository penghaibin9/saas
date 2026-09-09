import { workspaceSection, foundationStyles, legacyStyleImportLayout, stripFinalIntegrationPresentation } from './graduation-workspace-style-sections.mjs'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const root = new URL('../src/modules/graduation/', import.meta.url)
const read = path => fs.readFileSync(new URL(path, root), 'utf8')
const rawLayout = read('views/AdminGraduationLayout.vue')
const layout = stripFinalIntegrationPresentation(rawLayout).replace(/ {6}:data-graduation-defense-workspace="[\s\S]*?"\n/, '')
const css = workspaceSection('material')
const oldCss = foundationStyles(read('styles/graduation-workspaces.css'))
const marker = layout.match(/:data-graduation-material-workspace="([\s\S]*?)"/)?.[1]
const digest = text => createHash('sha256').update(text).digest('hex')
const routes = new Map([
  ['graduation-material-center', 'materials'],
  ['graduation-plagiarism-ledger', 'plagiarism'],
  ['graduation-review-tasks', 'review']
])

test('three existing routes choose their exact presentation identity', () => {
  assert.ok(marker)
  for (const [name, expected] of routes) assert.equal(vm.runInNewContext(marker, { $route: { name } }), expected)
  assert.deepEqual([...marker.matchAll(/'([^']+)'/g)].map(item => item[1]), [...routes].flat())
})

test('defense, grades, nested forms, mentor conflicts and unknown routes opt out', () => {
  assert.ok(marker)
  for (const name of [undefined, null, 'graduation-defense-scoring', 'graduation-defense-confirmation', 'graduation-grade-ledger', 'graduation-defense-grade-student-form', 'graduation-review-assign', 'graduation-mentor-conflicts', 'graduation-process', 'graduation-students', 'internship', ...[...routes.keys()].map(name => name + '-other')]) {
    assert.equal(vm.runInNewContext(marker, { $route: { name } }), undefined, String(name))
  }
})

test('removing the material marker restores the parent layout without retired style imports', () => {
  const parent = legacyStyleImportLayout(layout).replace(/ {6}:data-graduation-material-workspace="[\s\S]*?"\n/, '')
  // The previous layout ended with this import, now moved intact into the one owner.
  const legacyParent = parent + '\n<style src="../styles/graduation-process-workspace.css"></style>\n'
  assert.equal(digest(legacyParent), 'ae239624fcd5d5ff2789720c12382e613037b0c27dbac369e93bbdfcf570ee00')
  assert.equal((rawLayout.match(/<style src="@\/modules\/graduation\/styles\/graduation-workspaces\.css"><\/style>/g) || []).length, 1)
  assert.equal((rawLayout.match(/<style\s+src=/g) || []).length, 1)
})

test('parent business script, scoped styles and grad-qual compatibility remain unchanged', () => {
  assert.equal(digest(legacyStyleImportLayout(layout).match(/<script>([\s\S]*?)<\/script>/)[1]), '04895c6dfa36018a5bb0a50b45d2e841689d56048b01dbaaa4c30d915a224c91')
  assert.equal(digest(layout.match(/<style scoped>([\s\S]*?)<\/style>/)[1]), 'b8312f8500649ccabaeed4fe70d3bee87af8245fa413e1fddc99074a0986b3c5')
  assert.match(layout, /if \(panel === 'grad-qual'\)[\s\S]*?panel: 'roster'/)
  assert.match(layout, /v-if="canRenderBusiness"[\s\S]*?:data-graduation-material-workspace=/)
  assert.equal((layout.match(/<router-view\b/g) || []).length, 1)
})

test('the complete non-material module stylesheet remains byte-identical', () => {
  assert.equal(digest(oldCss), 'ab00fa350f0927d7d9250c03bdede1ccfae3bf39878b489993b38488079aff64')
  assert.doesNotMatch(oldCss.slice(0, oldCss.indexOf('/* Planning workspaces:')), /\.mc-(?:page|hero|summary|filters|tabs|panel|table-wrap)/)
})

test('every new selector has a graduation material route boundary', () => {
  const body = css.replace(/\/\*[\s\S]*?\*\//g, '')
  const selectors = [...body.matchAll(/([^{}]+)\{/g)].map(m => m[1].trim()).filter(s => !s.startsWith('@'))
  assert.ok(selectors.length > 80)
  for (const selector of selectors) assert.ok(selector.startsWith('.gd-business-view[data-graduation-material-workspace'), selector)
  assert.doesNotMatch(body, /\.tw-|\.bpl-|:root|:global\(|@import|z-index/)
})

test('UI rules neither suppress blockers nor unlock controls', () => {
  const body = css.replace(/\/\*[\s\S]*?\*\//g, '')
  assert.doesNotMatch(body, /display:\s*none|visibility:\s*hidden|pointer-events|opacity:|!important|(?:^|[;{])\s*content:/)
  for (const name of ['mc-reader__error', 'w74-blockers', 'w74-history-lock', 'w74-form-error', 'w74-summary-warning']) assert.ok(body.includes('.' + name), name)
})

test('fields, metadata and actions retain readable sizes and existing theme tokens', () => {
  const sizes = [...css.matchAll(/font-size:\s*([\d.]+)px/g)].map(m => Number(m[1]))
  assert.ok(sizes.length > 30 && Math.min(...sizes) >= 12)
  assert.match(css, /min-height: 36px/)
  assert.match(css, /background: var\(--field-bg/)
  assert.match(css, /color: var\(--pri-on/)
  assert.match(css, /textarea\s*\{[^}]*min-height: 104px;[^}]*resize: vertical/)
  assert.match(css, /:focus-visible\s*\{[^}]*outline: 2px solid var\(--pri/)
})

test('responsive material metrics and filters follow available width without root containment', () => {
  assert.match(css, /repeat\(auto-fit, minmax\(min\(136px, 100%\), 1fr\)\)/)
  assert.match(css, /repeat\(auto-fit, minmax\(min\(170px, 100%\), 1fr\)\)/)
  assert.match(css, /\.mc-table-wrap\s*\{[^}]*overflow: auto/)
  assert.doesNotMatch(css, /\bcontainer(?:-type)?:|\bcontain:|\btransform:|\bfilter:/)
})

test('historical and current file identity wrap rather than being replaced by a visual-only label', () => {
  assert.match(css, /\.mc-reader__identity strong\s*\{[^}]*white-space: normal;[^}]*overflow-wrap: anywhere/)
  assert.match(css, /\.mc-page \.mc-summary :is\(span, small\)[^{]*\{[^}]*font-size: 12px/)
  assert.doesNotMatch(css, /text-overflow: ellipsis|font-size: 0/)
})