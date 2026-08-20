import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { buildHandoff } from '../scripts/generate-v3-handoff.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const repo = resolve(root, '..')
const read = (path) => readFileSync(resolve(repo, path), 'utf8')

const REQUIRED_FIELDS = [
  'studentMergeSha', 'actionSchemaVersion', 'routeInventoryHash',
  'subpackageHash', 'networkPagerVersion', 'attachmentPickerVersion',
  'alembicHead', 'packageReportSha'
]

test('S9 handoff 覆盖手册要求的全部共享契约字段', () => {
  const handoff = buildHandoff()
  for (const field of REQUIRED_FIELDS) {
    assert.ok(field in handoff, `handoff 缺少 ${field}`)
  }
  assert.equal(handoff.schema, 'miniapp-v3-handoff/1')
})

test('S9 路由清单与分包结构都被哈希固定', () => {
  const handoff = buildHandoff()
  assert.match(handoff.routeInventoryHash, /^[0-9a-f]{64}$/)
  assert.match(handoff.subpackageHash, /^[0-9a-f]{64}$/)
  assert.ok(handoff.routeCount >= 134, '页面总数不得低于 S1 基线')
  const roots = handoff.subpackages.map((pkg) => pkg.root)
  assert.deepEqual(roots, ['pages/student', 'pages/teacher'])
})

test('S9 共享组件版本来自源码里的显式版本号，不靠人手维护', () => {
  const handoff = buildHandoff()
  assert.match(handoff.actionSchemaVersion, /^\d+\.\d+\.\d+$/)
  assert.match(handoff.networkPagerVersion, /^\d+\.\d+\.\d+$/)
  assert.match(handoff.attachmentPickerVersion, /^\d+\.\d+\.\d+$/)
  assert.match(read('miniapp/src/services/actionRouterCore.mjs'), /ACTION_SCHEMA_VERSION = '/)
  assert.match(read('miniapp/src/utils/networkPager.js'), /NETWORK_PAGER_VERSION = '/)
  assert.match(read('miniapp/src/components/MobileAttachmentPicker.vue'), /ATTACHMENT_PICKER_VERSION = '/)
})

test('S9 alembic 必须是单头', () => {
  const handoff = buildHandoff()
  assert.ok(handoff.alembicHead, '拿不到 alembic head 就不能交接')
  assert.equal(handoff.alembicHead.includes(','), false, `alembic 必须单头，实际=${handoff.alembicHead}`)
})

test('S9 落盘的 handoff 与当前代码一致（漂移即失败）', () => {
  const path = resolve(repo, 'miniapp-v3-handoff.json')
  assert.ok(existsSync(path), '仓库里必须有 miniapp-v3-handoff.json')
  const stored = JSON.parse(readFileSync(path, 'utf8'))
  const current = buildHandoff()
  for (const field of ['actionSchemaVersion', 'routeInventoryHash', 'subpackageHash',
    'networkPagerVersion', 'attachmentPickerVersion', 'alembicHead']) {
    assert.equal(stored[field], current[field], `${field} 已漂移，Teacher T8 不得据此接线`)
  }
})
