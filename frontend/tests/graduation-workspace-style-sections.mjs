import assert from 'node:assert/strict'
import fs from 'node:fs'

export const workspaceCssUrl = new URL('../src/modules/graduation/styles/graduation-workspaces.css', import.meta.url)
export const workspaceCss = fs.readFileSync(workspaceCssUrl, 'utf8').replace(/\r\n/g, '\n')
const sectionPrefix = '\n/* BEGIN graduation workspace: '
const integrationStyleStart = '\n<style scoped>\n/* Final graduation-only integration polish.'

// Test-only slicing: the product keeps a single stylesheet and a single import.
// Slices are exact; no CSS declarations or behavior assertions are normalized.
export function workspaceSection(name) {
  const begin = `${sectionPrefix}${name} */\n`
  const end = `/* END graduation workspace: ${name} */\n`
  assert.equal(workspaceCss.split(begin).length, 2, `exactly one ${name} section is required`)
  assert.equal(workspaceCss.split(end).length, 2, `exactly one ${name} end marker is required`)
  const start = workspaceCss.indexOf(begin) + begin.length
  const finish = workspaceCss.indexOf(end, start)
  assert.ok(finish >= start, `${name} section must close after its start`)
  return workspaceCss.slice(start, finish)
}

export function foundationStyles(source = workspaceCss) {
  const end = source.indexOf(sectionPrefix)
  assert.ok(end > 0, 'single owner must retain the foundation section')
  return source.slice(0, end)
}

// Final closeout adds only route-presentation markers and one extra scoped
// Graduation style block. Historical byte-hash tests may remove exactly those
// additions, never arbitrary template/script/style content.
export function stripFinalIntegrationPresentation(source) {
  let normalized = source
  for (const attribute of [
    'data-graduation-risk-workspace',
    'data-graduation-template-workspace',
    'data-graduation-content-workspace'
  ]) {
    normalized = normalized.replace(new RegExp(`      :${attribute}="[\\s\\S]*?"\\n`), '')
  }
  const index = normalized.indexOf(integrationStyleStart)
  if (index >= 0) normalized = normalized.slice(0, index)
  return normalized
}

// Historical layout hashes included the JS side-effect import. Only restore
// that transport statement for comparison; run behavior against the raw script.
export function legacyStyleImportLayout(source) {
  const tag = '\n<style src="@/modules/graduation/styles/graduation-workspaces.css"></style>\n'
  assert.equal(source.split(tag).length, 2, 'exactly one canonical SFC stylesheet import is required')
  const anchor = "import { useGraduationBatchStore } from '@/stores/graduationBatch'"
  const scriptImport = "import '@/modules/graduation/styles/graduation-workspaces.css'\n"
  assert.equal(source.split(anchor).length, 2)
  assert.equal(source.includes(scriptImport), false, 'do not duplicate the stylesheet import')
  return source.replace(tag, '').replace(anchor, scriptImport + anchor)
}
