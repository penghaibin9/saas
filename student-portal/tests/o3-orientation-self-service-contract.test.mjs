import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const router = read('../src/router/index.js')
const api = read('../src/services/portalApi.js')
const view = read('../src/views/orientation/OrientationView.vue')

test('O3 student PC exposes exact information, arrival, and material routes', () => {
  for (const path of ['orientation/info', 'orientation/arrival', 'orientation/materials']) {
    assert.match(router, new RegExp(`path: '${path}'`))
  }
  assert.match(api, /\/portal\/orientation\/arrival'.*method: 'PUT'/)
  assert.match(api, /\/portal\/orientation\/materials'.*method: 'POST'/)
  assert.match(api, /fileSdk\.upload\(file, \{ bizType: 'ORIENTATION_MATERIAL' \}\)/)
})

test('O3 student PC preserves CAS and formal file identifiers', () => {
  assert.match(view, /expectedVersion: arrival\.version/)
  assert.match(view, /fileId: uploaded\.fileId/)
  assert.match(view, /clientSubmissionId: clientSubmissionId\(\)/)
  assert.doesNotMatch(view, /reportCode\s*:\s*admissionNo/)
})
