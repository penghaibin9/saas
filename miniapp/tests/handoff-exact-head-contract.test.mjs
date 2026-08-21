import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const miniapp = resolve(here, '..')
const repo = resolve(miniapp, '..')

test('S9 seal SHA 作为不可变 Student 基线保留，Teacher downstream 不把当前 HEAD 冒充 Student seal', () => {
  const stored = JSON.parse(readFileSync(resolve(repo, 'miniapp-v3-handoff.json'), 'utf8'))
  assert.match(stored.studentMergeSha, /^[0-9a-f]{40}$/)
  const source = readFileSync(resolve(miniapp, 'scripts/generate-v3-handoff.mjs'), 'utf8')
  assert.match(source, /implementationSha\(\)/)
  assert.match(source, /SEAL_SUBJECT/)
})

test('T8 handoff generator 被 import 时不得重写证据文件', () => {
  const source = readFileSync(resolve(miniapp, 'scripts/generate-v3-handoff.mjs'), 'utf8')
  assert.match(source, /function isCliEntry\(\)/)
  assert.match(source, /if \(isCliEntry\(\)\)/)
  assert.doesNotMatch(source, /const isVerify = process\.argv\.includes\('--verify'\)\s*\nif \(isVerify\)/)
})

test('T8 downstream verifier 必须用祖先关系而不是 current HEAD equality', () => {
  const source = readFileSync(resolve(miniapp, 'scripts/verify-v3-handoff-downstream.mjs'), 'utf8')
  assert.match(source, /merge-base', '--is-ancestor'/)
  assert.match(source, /fetch-depth: 0/)
  assert.match(source, /SHARED_FIELDS/)
  assert.doesNotMatch(source, /stored\.studentMergeSha\s*===\s*current\.studentMergeSha/)
})
