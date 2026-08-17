import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const api = fs.readFileSync(path.join(root, 'src/modules/platform/api/platformPam.api.js'), 'utf8')
const view = fs.readFileSync(path.join(root, 'src/modules/platform/views/control/PlatformAccessView.vue'), 'utf8')

test('P-04 command client exposes revoke terminate and review close with optimistic version', () => {
  assert.match(api, /access-assignments\/\$\{encodeURIComponent\(id\)\}\/revoke/)
  assert.match(api, /elevation-sessions\/\$\{encodeURIComponent\(id\)\}\/revoke/)
  assert.match(api, /support-sessions\/\$\{encodeURIComponent\(id\)\}\/terminate/)
  assert.match(api, /access-reviews\/\$\{encodeURIComponent\(id\)\}\/close/)
  assert.match(api, /body: \{ expectedVersion, reason \}/)
  assert.match(api, /body: \{ tenantId, expectedVersion, reason \}/)
  assert.match(api, /body: \{ expectedVersion, reason, decisions \}/)
})

test('P-04 UI exposes complete action and exact review-decision workflow', () => {
  assert.match(view, /beginAction\('assignment', item\)/)
  assert.match(view, /beginAction\('elevation', item\)/)
  assert.match(view, /beginAction\('support', item\)/)
  assert.match(view, /value="KEEP"/)
  assert.match(view, /value="REVOKE"/)
  assert.match(view, /reviewDecisions\[item\.itemKey\]/)
  assert.match(view, /item\.version/)
  assert.match(view, /platformPamApi\.closeReview/)
  assert.match(view, /itemKey/)
  assert.match(view, /decision/)
})
