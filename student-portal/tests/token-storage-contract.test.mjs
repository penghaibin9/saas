/**
 * 会话令牌存储契约：门户令牌只能进 sessionStorage，不得进 localStorage。
 *
 * 为什么要锁：学生门户大量跑在机房/图书馆的公用电脑上。localStorage 关掉浏览器
 * 仍然保留，下一个人打开浏览器就直接是上一个学生（或家长）的登录态。
 * sessionStorage 随标签页结束即清。
 *
 * 允许的例外：迁移期兼容代码——读到旧 localStorage 值时搬进 sessionStorage
 * 并立刻 removeItem。所以 localStorage.setItem 一律禁止，removeItem/getItem 允许。
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const here = dirname(fileURLToPath(import.meta.url))
const files = [
  join(here, '../src/services/request.js'),
  join(here, '../src/services/guardianApi.js'),
]

const TOKEN_KEYS = ['sp_token_v1', 'sp_refresh_v1', 'sp_guardian_v1']

test('令牌相关文件不得调用 localStorage.setItem', () => {
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    const code = source
      .split('\n')
      .filter((line) => !line.trimStart().startsWith('//') && !line.trimStart().startsWith('*'))
      .join('\n')
    assert.equal(
      code.includes('localStorage.setItem'),
      false,
      `${file} 不得把会话数据写入 localStorage（公用电脑上会残留登录态）`,
    )
  }
})

test('令牌读写走 sessionStorage', () => {
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    assert.ok(
      source.includes('sessionStorage.setItem'),
      `${file} 应使用 sessionStorage 保存会话令牌`,
    )
  }
})

test('迁移期必须清掉遗留在 localStorage 的旧令牌', () => {
  for (const file of files) {
    const source = readFileSync(file, 'utf8')
    assert.ok(
      source.includes('localStorage.removeItem'),
      `${file} 必须删除历史遗留的 localStorage 令牌，否则旧值会一直留在磁盘上`,
    )
  }
})

test('令牌 key 未被改名（改名会让迁移期兼容逻辑失效）', () => {
  const combined = files.map((f) => readFileSync(f, 'utf8')).join('\n')
  for (const key of TOKEN_KEYS) {
    assert.ok(combined.includes(key), `令牌 key ${key} 应保持不变`)
  }
})
