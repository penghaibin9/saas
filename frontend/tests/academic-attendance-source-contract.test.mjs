import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import vm from 'node:vm'

const here = path.dirname(fileURLToPath(import.meta.url))
const page = fs.readFileSync(
  path.resolve(here, '../src/modules/academicAffairs/views/AaAttendanceStatsView.vue'),
  'utf8'
)

test('PC attendance statistics expose Chinese provenance labels', () => {
  assert.match(page, /管理员特殊补录/)
  assert.match(page, /sourceScopeLabel/)
  assert.match(page, /sessionTypeLabel/)
  assert.match(page, /sourceLabel/)
  assert.doesNotMatch(page, /\{ key: 'sessionType', title: '类别' \}/)
})

test('ADMIN_SPECIAL is audit-only and cannot trigger normal absence warning scan from PC', async () => {
  assert.match(page, /v-if="canScan && sessionType !== 'ADMIN_SPECIAL'"/)
  assert.match(page, /特殊补录仅用于审计核对，不进入标准课堂旷课预警/)
  let scans = 0
  const script = page.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/^import (.*?) from .*$/gm, (_, binding) => `const ${binding} = dependencies${binding.startsWith('{') ? '' : '.' + binding}`)
    .replace('export default', 'component =')
  const sandbox = { dependencies: {
    academicAffairsWarningApi: { scan: async () => { scans++; return { code: 0, data: { created: 0 } } } },
    toast: { success() {}, error() {} }
  } }
  vm.runInNewContext(script, sandbox)
  const scan = sandbox.component.methods.scanAbsent
  const state = { scanning: false, canScan: true, sessionType: 'ADMIN_SPECIAL', scanSeq: 0, identityKey: 'test-user' }
  await scan.call(state)
  assert.equal(scans, 0, 'special audit rows cannot be scanned even with the warning permission')
  state.sessionType = 'NORMAL'; state.canScan = false
  await scan.call(state)
  assert.equal(scans, 0, 'without permission the handler must also reject the scan')
  state.canScan = true
  await scan.call(state)
  assert.equal(scans, 1, 'ordinary authorized scanning remains available')
})
