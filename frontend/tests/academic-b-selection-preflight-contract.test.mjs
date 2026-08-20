import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const apiUrl = new URL('../src/modules/academicAffairs/api/academic-affairs.api.js', import.meta.url)
const viewUrl = new URL('../src/modules/academicAffairs/views/AaSelectionConsoleView.vue', import.meta.url)

test('B-W1 admin lifecycle consumes backend preflight before command', async () => {
  const api = await readFile(apiUrl, 'utf8')
  const view = await readFile(viewUrl, 'utf8')
  assert.match(api, /batchPreflight\(id, action\)/)
  assert.match(view, /await this\.refreshPreflight\(\)/)
  assert.match(view, /if \(!checked \|\| !checked\.allowed\)/)
  assert.match(view, /preflightMessage\(preflight\)/)
  assert.match(view, /PUBLISH.*OPEN.*CLOSE.*LOCK/s)
  const start = view.indexOf('async lifecycle(fn, label)')
  const lifecycle = view.slice(start, view.indexOf('openAddCourse()', start))
  assert.ok(lifecycle.indexOf('refreshPreflight') < lifecycle.indexOf('this.confirmTitle = label'))
  assert.ok(lifecycle.indexOf('refreshPreflight') < lifecycle.indexOf('api[fn]'))
})
