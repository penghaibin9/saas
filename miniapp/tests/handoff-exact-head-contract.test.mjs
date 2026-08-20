import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { buildHandoff } from '../scripts/generate-v3-handoff.mjs'

const here = dirname(fileURLToPath(import.meta.url))
const miniapp = resolve(here, '..')
const repo = resolve(miniapp, '..')

test('S9 handoff seal 必须机器绑定 exact implementation HEAD', () => {
  const stored = JSON.parse(readFileSync(resolve(repo, 'miniapp-v3-handoff.json'), 'utf8'))
  const current = buildHandoff()
  assert.match(stored.studentMergeSha, /^[0-9a-f]{40}$/)
  assert.equal(
    stored.studentMergeSha,
    current.studentMergeSha,
    'handoff 未封住当前实现 HEAD；Teacher T8 不得消费过期交接物'
  )
})

test('S9 seal 验证不得依赖 shallow checkout 中不存在的父对象', () => {
  const source = readFileSync(resolve(miniapp, 'scripts/generate-v3-handoff.mjs'), 'utf8')
  assert.match(source, /implementationSha\(\)/)
  assert.match(source, /cat-file/)
  assert.match(source, /SEAL_SUBJECT/)
  assert.doesNotMatch(source, /diff-tree/)
  assert.doesNotMatch(source, /rev-parse['"], ['"]HEAD\^/)
  assert.doesNotMatch(source, /field === ['"]studentMergeSha['"]\) continue/)
})
