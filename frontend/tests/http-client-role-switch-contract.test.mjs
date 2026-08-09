import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const clientUrl = new URL('../src/services/http/client.js', import.meta.url)

test('身份切换后只允许安全读请求自动重放', async () => {
  const source = await readFile(clientUrl, 'utf8')

  assert.match(source, /const safeToReplayAcrossContext = !isWriteMethod\(options\.method\)/)
  assert.match(source, /if \(safeToReplayAcrossContext\) return rawRequest\(path, options\)\s+throw authContextChangedError\(\)/)
})

test('二进制请求同样禁止跨身份重放写操作', async () => {
  const source = await readFile(clientUrl, 'utf8')

  assert.match(source, /const safeToReplayAcrossContext = !isWriteMethod\(method\)/)
  assert.match(source, /if \(safeToReplayAcrossContext\) return doFetch\(\)\s+throw authContextChangedError\(\)/)
  assert.match(source, /err\.bizCode = 'AUTH_CONTEXT_CHANGED'/)
})
