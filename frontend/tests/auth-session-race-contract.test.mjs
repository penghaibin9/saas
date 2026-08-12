import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const clientUrl = new URL('../src/services/http/client.js', import.meta.url)

test('迟到的旧 refresh 不能覆盖或清空身份切换后的新会话', async () => {
  const source = await readFile(clientUrl, 'utf8')

  // SECURITY-P0: browser JS must never retain or transmit refreshToken. The browser-refresh
  // endpoint consumes the HttpOnly cookie while accessToken remains the only in-memory token.
  assert.match(source, /const state = \{ token: '', offlineUntil: 0, notified: false \}/)
  assert.doesNotMatch(source, /state\.refreshToken/)
  assert.doesNotMatch(source, /body: \{ refreshToken:/)
  assert.match(source, /const accessTokenAtStart = state\.token/)
  assert.match(
    source,
    /rawRequest\('\/auth\/browser-refresh', \{[\s\S]*?method: 'POST', auth: false, forceProbe: true[\s\S]*?\}\)/
  )
  assert.match(source, /credentials: 'same-origin'/)

  const staleSessionGuards = source.match(
    /if \(state\.token && state\.token !== accessTokenAtStart\) return true/g
  ) || []
  assert.ok(staleSessionGuards.length >= 2, 'refresh success/failure both need stale-session guards')

  assert.doesNotMatch(
    source,
    /catch \{\s*_holdToken\(''\)\s*return false\s*\}/,
    'refresh failure must not unconditionally clear a newer session'
  )
})

test('旧 access token 的 401 优先重试新会话而不是触发旧 refresh', async () => {
  const source = await readFile(clientUrl, 'utf8')

  const newerSessionRetries = source.match(
    /if \(state\.token && state\.token !== accessTokenAtStart\) return (?:rawRequest\(path, options\)|doFetch\(\))/g
  ) || []
  assert.ok(newerSessionRetries.length >= 4, 'normal requests and blob downloads need before/after-refresh guards')

  assert.match(
    source,
    /const accessTokenAtStart = state\.token[\s\S]*?if \(state\.token && state\.token !== accessTokenAtStart\) return rawRequest\(path, options\)[\s\S]*?if \(await tryRefresh\(\)\) return rawRequest\(path, options\)/
  )
})
