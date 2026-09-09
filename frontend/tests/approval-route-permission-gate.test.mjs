import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const gate = fs.readFileSync(new URL('../src/security/permissionGate.js', import.meta.url), 'utf8')
const routes = fs.readFileSync(new URL('../src/modules/approval/approval.routes.js', import.meta.url), 'utf8')

test('approval direct URLs are covered by the production permission gate', () => {
  assert.match(gate, /GUARDED_MODULES[\s\S]*'APPROVAL'/)
  assert.match(gate, /APPROVAL:\s*\[[^\]]*'approval'/)
  assert.match(routes, /path:\s*'done'[\s\S]*permissionKey:\s*'approval\.done\.view'/)
})
