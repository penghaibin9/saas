import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { buildHandoff, canonicalize, resolveSealedSha } from '../scripts/generate-v3-handoff.mjs'

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


// ── 回归：handoff 交付物只能由命令行生成，import 不得有副作用 ──
//
// handoff-contract 本身就 import 这个脚本，而 ESM 的 import 会执行模块顶层。
// 少了直接执行判断时，`npm test` 会顺手把 miniapp-v3-handoff.json 重写一遍——
// 在 main 上它会把封存的实现 SHA 覆盖成 merge 提交 SHA，等于测试毁掉交付物。

test('S9-G: 仅 import 生成脚本不得改写 handoff 交付物', async () => {
  const { execFileSync } = await import('node:child_process')
  const target = resolve(repo, 'miniapp-v3-handoff.json')
  if (!existsSync(target)) return
  const before = readFileSync(target, 'utf8')
  execFileSync(process.execPath, [
    '-e', "import('./miniapp/scripts/generate-v3-handoff.mjs').then(() => {})"
  ], { cwd: repo })
  assert.equal(readFileSync(target, 'utf8'), before, 'import 生成脚本后交付物被改写了')
})

// ── 回归：被封存实现 SHA 必须能在合入后的 main 上解析出来 ──
//
// 手册 §13.1 要求 Teacher T8 从合入后的 main 机器校验，所以 merge 提交必须能穿过去；
// 只认「HEAD 就是 seal」的旧实现在 main 上必然误报漂移，等于交付物在唯一该用的地方不可用。

const SEAL = 'chore(miniapp-v3): seal exact-head handoff'

function fakeGraph(entries) {
  return (ref) => entries[ref] || null
}

test('S9-G: seal 提交解析成它封住的实现提交', () => {
  const read = fakeGraph({ seal: { subject: SEAL, parents: ['impl'] } })
  assert.deepEqual(resolveSealedSha(read, 'seal'), { sha: 'impl', unresolved: false })
})

test('S9-G: main 上的 merge 提交要穿过 seal 找到实现提交', () => {
  const read = fakeGraph({
    merge: { subject: 'Merge pull request #182 from x', parents: ['mainBase', 'seal'] },
    seal: { subject: SEAL, parents: ['impl'] }
  })
  assert.deepEqual(resolveSealedSha(read, 'merge'), { sha: 'impl', unresolved: false })
})

test('S9-G: seal 之后的普通业务提交必须判为漂移源（返回它自己）', () => {
  const read = fakeGraph({ later: { subject: 'feat: 新功能', parents: ['seal'] } })
  assert.deepEqual(resolveSealedSha(read, 'later'), { sha: 'later', unresolved: false })
})

test('S9-G: 并进来的不是 seal 时，被封存的就是 HEAD 这棵树本身', () => {
  // 典型情形：我们把 main 合进自己分支。这时不能返回 main 的尖端——那是别人的提交，
  // 拿它当「本 handoff 封住的实现提交」既不真实，也会让紧接着的 seal 与 verify
  // 各算各的、永远对不上（实测踩过：生成时写 main 尖端、校验时算 seal 的父，必然漂移）。
  const read = fakeGraph({
    merge: { subject: 'Merge pull request #999 from y', parents: ['mainBase', 'otherTip'] },
    otherTip: { subject: 'feat: 别的分支', parents: ['x'] }
  })
  assert.deepEqual(resolveSealedSha(read, 'merge'), { sha: 'merge', unresolved: false })
})

test('S9-G: 浅克隆读不到父对象时报「无法解析」而不是「漂移」', () => {
  const read = fakeGraph({
    merge: { subject: 'Merge pull request #182 from x', parents: ['mainBase', 'seal'] }
  })
  const result = resolveSealedSha(read, 'merge')
  assert.equal(result.unresolved, true)
  assert.equal(result.sha, '')
  assert.match(result.reason, /seal/)
})


// ── 回归：packageReportSha 必须只反映包本身 ──
//
// 包体报告里带 generatedAt。直接哈希整份文件的话，同一份产物每构建一次就换一个哈希，
// 这个字段永远无法被独立复现，Teacher T8 拿它比不出任何东西——字段名说的是"包体报告
// 的指纹"，实际测的是"构建发生在哪一秒"。

test('S9-G: 包体报告哈希忽略构建时间，同样的包给同样的值', () => {
  const at = (stamp) => ({ generatedAt: stamp, totalBytes: 123, packages: [{ root: 'pages/student', bytes: 1 }] })
  assert.equal(
    JSON.stringify(canonicalize(at('2026-08-20T07:06:03.866Z'))),
    JSON.stringify(canonicalize(at('2030-01-01T00:00:00.000Z')))
  )
})

test('S9-G: 包体报告哈希对键序不敏感，但内容变了必须变', () => {
  const a = { totalBytes: 1, budgetPass: true }
  const b = { budgetPass: true, totalBytes: 1 }
  assert.equal(JSON.stringify(canonicalize(a)), JSON.stringify(canonicalize(b)))
  assert.notEqual(
    JSON.stringify(canonicalize({ totalBytes: 1 })),
    JSON.stringify(canonicalize({ totalBytes: 2 }))
  )
})
