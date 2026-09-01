import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const pages = read('../src/pages.json')
const api = read('../src/services/realApi.js')
const arrival = read('../src/pages/student/orientation/arrival/index.vue')
const materials = read('../src/pages/student/orientation/materials/index.vue')
const credential = read('../src/pages/student/orientation/code/index.vue')

test('O3 student miniapp exposes canonical arrival and material submission', () => {
  assert.match(pages, /orientation\/arrival\/index/)
  assert.match(pages, /orientation\/materials\/index/)
  assert.match(api, /\/mobile\/orientation\/arrival'.*method: 'PUT'/)
  assert.match(api, /\/mobile\/orientation\/materials'.*method: 'POST'/)
  assert.match(arrival, /expectedVersion: Number\(this\.form\.expectedVersion \|\| 0\)/)
  assert.match(materials, /bizType: 'ORIENTATION_MATERIAL'/)
  assert.match(materials, /clientSubmissionId:/)
})

test('O3 does not disguise the admission number as a report credential', () => {
  assert.match(api, /status: r\.reportCodeStatus \|\| 'BLOCKED'/)
  assert.match(api, /canIssue: !!r\.checkinCredential\?\.canIssue/)
  assert.match(api, /expiresAt: r\.checkinCredential\?\.expiresAt \|\| ''/)
  assert.match(api, /note: r\.checkinCredential\?\.note \|\| '正式电子报到凭证尚未签发'/)
  assert.match(credential, /尚未签发/)
  assert.match(credential, /identity\.admissionNo/)
  assert.doesNotMatch(api, /reportCode:\s*\{\s*code:\s*r\.admissionNo/)
})
