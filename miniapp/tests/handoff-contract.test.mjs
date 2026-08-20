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
const DOWNSTREAM_SHARED_FIELDS = [
  'actionSchemaVersion', 'routeInventoryHash', 'subpackageHash',
  'networkPagerVersion', 'attachmentPickerVersion'
]

test('S9 handoff 覆盖手册要求的全部共享契约字段', () => {
  const stored = JSON.parse(read('miniapp-v3-handoff.json'))
  for (const field of REQUIRED_FIELDS) {
    assert.ok(field in stored, `handoff 缺少 ${field}`)
  }
  assert.equal(stored.schema, 'miniapp-v3-handoff/1')
})

test('S9 路由清单与分包结构都被哈希固定', () => {
  const current = buildHandoff()
  assert.match(current.routeInventoryHash, /^[0-9a-f]{64}$/)
  assert.match(current.subpackageHash, /^[0-9a-f]{64}$/)
  assert.ok(current.routeCount >= 134, '页面总数不得低于 S1 基线')
  const roots = current.subpackages.map((pkg) => pkg.root)
  assert.deepEqual(roots, ['pages/student', 'pages/teacher'])
})

test('S9 共享组件版本来自源码里的显式版本号，不靠人手维护', () => {
  const current = buildHandoff()
  assert.match(current.actionSchemaVersion, /^\d+\.\d+\.\d+$/)
  assert.match(current.networkPagerVersion, /^\d+\.\d+\.\d+$/)
  assert.match(current.attachmentPickerVersion, /^\d+\.\d+\.\d+$/)
  assert.match(read('miniapp/src/services/actionRouterCore.mjs'), /ACTION_SCHEMA_VERSION = '/)
  assert.match(read('miniapp/src/utils/networkPager.js'), /NETWORK_PAGER_VERSION = '/)
  assert.match(read('miniapp/src/components/MobileAttachmentPicker.vue'), /ATTACHMENT_PICKER_VERSION = '/)
})

test('S9 / T8 当前 alembic 必须继续保持单头', () => {
  const current = buildHandoff()
  assert.ok(current.alembicHead, '拿不到 alembic head 就不能继续下游施工')
  assert.equal(current.alembicHead.includes(','), false, `alembic 必须单头，实际=${current.alembicHead}`)
})

test('T8 落盘 Student handoff 与当前共享前端合同一致，允许下游业务迁移继续前进', () => {
  const path = resolve(repo, 'miniapp-v3-handoff.json')
  assert.ok(existsSync(path), '仓库里必须有 miniapp-v3-handoff.json')
  const stored = JSON.parse(readFileSync(path, 'utf8'))
  const current = buildHandoff()
  for (const field of DOWNSTREAM_SHARED_FIELDS) {
    assert.equal(stored[field], current[field], `${field} 已漂移，Teacher T8 不得据此接线`)
  }
  // Student seal freezes its own migration head; Teacher T7 may legally append a new single head.
  assert.ok(stored.alembicHead)
  assert.ok(current.alembicHead)
})
