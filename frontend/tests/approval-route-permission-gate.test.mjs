import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const gate = fs.readFileSync(new URL('../src/security/permissionGate.js', import.meta.url), 'utf8')
const routes = fs.readFileSync(new URL('../src/modules/approval/approval.routes.js', import.meta.url), 'utf8')

test('approval direct URLs are covered by the production permission gate', () => {
  // Approval now uses the same generic module-entitlement projection as every
  // other guarded module. Do not pin this regression to the removed legacy
  // MODULE_CODE -> feature-array source shape; verify the actual production
  // boundary: APPROVAL is guarded, commercial entitlement is checked, and the
  // route still carries its exact permission code.
  assert.match(gate, /GUARDED_MODULES[\s\S]*'APPROVAL'/)
  assert.match(gate, /moduleEntitled\(moduleCode,[\s\S]*_moduleEntitlements/)
  assert.match(gate, /if \(!currentModuleEntitled\(meta\.moduleCode\)\) return false/)
  assert.match(routes, /path:\s*'done'[\s\S]*moduleCode:\s*'APPROVAL'[\s\S]*permissionKey:\s*'approval\.done\.view'/)
})
