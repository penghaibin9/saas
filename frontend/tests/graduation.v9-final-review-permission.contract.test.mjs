import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const view = fs.readFileSync(path.resolve(here, '../src/modules/graduation/views/FinalSubmissionListView.vue'), 'utf8')

test('U3 final export is gated by the canonical RBAC final.export permission', () => {
  assert.match(view, /getPermissionPatterns/)
  assert.match(view, /matchPermission/)
  assert.match(view, /graduationDesign\.final\.export/)
  assert.doesNotMatch(view, /permissionActions\.exportStats/)
})
