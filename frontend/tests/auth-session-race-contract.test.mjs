import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const clientUrl = new URL('../src/services/http/client.js', import.meta.url)

test('迟到的旧 refresh 不能覆盖或清空身份切换后的新会话', async () => {
  const source = await readFile(clientUrl, 'utf8')

  // SECURITY-P0: browser JS must never retain or transmit refreshToken. The browser-refresh
  // endpoint consumes the HttpOnly cookie while accessToken remains the only in-memory token.
  assert.match(source, /const state = \{ token: '', sessionGeneration: 0, offlineUntil: 0, notified: false \}/)
  assert.doesNotMatch(source, /state\.refreshToken/)
  assert.doesNotMatch(source, /body: \{ refreshToken:/)
  assert.match(source, /const generationAtStart = state\.sessionGeneration/)
  assert.match(source, /const accessTokenAtStart = state\.token/)
  assert.match(
    source,
    /rawRequest\('\/auth\/browser-refresh', \{[\s\S]*?method: 'POST', auth: false, forceProbe: true[\s\S]*?\}\)/
  )
  assert.match(source, /credentials: 'same-origin'/)
  assert.match(source, /if \(state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
  assert.match(source, /if \(e\?\.staleSession \|\| state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)

  assert.doesNotMatch(
    source,
    /catch \{\s*_replaceToken\(''\)\s*return false\s*\}/,
    'refresh failure must not unconditionally clear a newer session'
  )
})

test('旧 access token 的 401 不得借重新登录或切换角色后的新身份重放', async () => {
  const source = await readFile(clientUrl, 'utf8')

  assert.match(source, /function _advanceSession\(access\) \{[\s\S]*?state\.sessionGeneration \+= 1[\s\S]*?_replaceToken\(access\)/)
  assert.match(source, /export function applyAuthSession\([\s\S]*?_advanceSession\(accessToken\)/)
  assert.match(source, /export function clearAuthSession\(\) \{[\s\S]*?_advanceSession\(''\)/)
  assert.match(source, /loginWithPassword[\s\S]*?_advanceSession\(data\.accessToken \|\| ''\)/)

  const requestBlock = source.match(/export async function request\(path, options = \{\}\) \{([\s\S]*?)\n\}\n\nexport async function logoutRemote/)
  assert.ok(requestBlock, 'request() block must exist')
  assert.match(requestBlock[1], /const generationAtStart = state\.sessionGeneration/)
  assert.match(requestBlock[1], /if \(state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
  assert.doesNotMatch(
    requestBlock[1],
    /if \(state\.token && state\.token !== accessTokenAtStart\) return rawRequest\(path, options\)[\s\S]*?state\.sessionGeneration !== generationAtStart[^\n]*$/m,
    'new-session retry must never precede the generation guard'
  )

  const blobBlock = source.match(/export async function requestBlob\(path,[\s\S]*?\{([\s\S]*?)\n\}\n\nexport function withFallback/)
  assert.ok(blobBlock, 'requestBlob() block must exist')
  assert.match(blobBlock[1], /const generationAtStart = state\.sessionGeneration/)
  assert.match(blobBlock[1], /if \(state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
})

test('上传使用启动时 token，身份切换后的迟到结果必须作废', async () => {
  const source = await readFile(clientUrl, 'utf8')
  const uploadBlock = source.match(/export async function requestUpload\(path, file, fieldName = 'file'\) \{([\s\S]*?)\n\}\n\nexport async function requestBlob/)
  assert.ok(uploadBlock, 'requestUpload() block must exist')
  assert.match(uploadBlock[1], /const generationAtStart = state\.sessionGeneration/)
  assert.match(uploadBlock[1], /const accessTokenAtStart = state\.token/)
  assert.match(uploadBlock[1], /Authorization: `Bearer \$\{accessTokenAtStart\}`/)
  assert.match(uploadBlock[1], /if \(state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
})
