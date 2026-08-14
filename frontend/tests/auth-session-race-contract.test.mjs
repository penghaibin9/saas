import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const clientUrl = new URL('../src/services/http/client.js', import.meta.url)

// 本仓 core.autocrlf=true 且无 .gitattributes：Windows 检出把源码换成 CRLF，
// 而下面的结构性正则按 LF 书写。不归一化则这些会话竞态守卫在 Windows 本地
// 全部静默不匹配（只有 Linux CI 才真的跑到）。只统一换行，不放宽任何断言。
async function readSource(url) {
  return (await readFile(url, 'utf8')).split('\r\n').join('\n')
}

test('迟到的旧 refresh 不能覆盖或清空身份切换后的新会话', async () => {
  const source = await readSource(clientUrl)

  // SECURITY-P0: browser JS must never retain or transmit refreshToken. The browser-refresh
  // endpoint consumes the HttpOnly cookie while accessToken remains the only in-memory token.
  assert.match(source, /const state = \{ token: '', sessionGeneration: 0, roleSwitchInFlight: false, offlineUntil: 0, notified: false \}/)
  assert.doesNotMatch(source, /state\.refreshToken/)
  assert.doesNotMatch(source, /body: \{ refreshToken:/)
  assert.match(source, /const generationAtStart = state\.sessionGeneration/)
  assert.match(source, /const accessTokenAtStart = state\.token/)
  assert.match(
    source,
    /rawRequest\('\/auth\/browser-refresh', \{[\s\S]*?method: 'POST', auth: false, forceProbe: true[\s\S]*?\}\)/
  )
  // The API origin is configurable, so the HttpOnly refresh cookie must be included for the
  // explicitly CORS-whitelisted API origin instead of being limited to the page's same origin.
  assert.match(source, /credentials: 'include'/)
  assert.match(source, /if \(state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
  assert.match(source, /if \(e\?\.staleSession \|\| state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)

  assert.doesNotMatch(
    source,
    /catch \{\s*_replaceToken\(''\)\s*return false\s*\}/,
    'refresh failure must not unconditionally clear a newer session'
  )
})

test('旧 access token 的 401 不得借重新登录或切换角色后的新身份重放', async () => {
  const source = await readSource(clientUrl)

  assert.match(source, /function _advanceSession\(access\) \{[\s\S]*?state\.sessionGeneration \+= 1[\s\S]*?_replaceToken\(access\)/)
  assert.match(source, /export function applyAuthSession\([\s\S]*?_advanceSession\(accessToken\)/)
  assert.match(source, /export function clearAuthSession\(\) \{[\s\S]*?_advanceSession\(''\)/)
  assert.match(source, /loginWithPassword[\s\S]*?_advanceSession\(data\.accessToken \|\| ''\)/)

  const requestBlock = source.match(/export async function request\(path, options = \{\}\) \{([\s\S]*?)\n\}\n\nexport async function logoutRemote/)
  assert.ok(requestBlock, 'request() block must exist')
  assert.match(requestBlock[1], /const generationAtStart = state\.sessionGeneration/)
  const requestGuard = 'if (state.sessionGeneration !== generationAtStart) throw staleSessionError()'
  const requestRetry = 'if (state.token && state.token !== accessTokenAtStart) return rawRequest(path, options)'
  const requestGuardIndex = requestBlock[1].indexOf(requestGuard)
  const requestRetryIndex = requestBlock[1].indexOf(requestRetry)
  assert.ok(requestGuardIndex >= 0, 'request() must guard the original logical session')
  assert.ok(requestRetryIndex >= 0, 'request() may retry only after same-session token rotation')
  assert.ok(
    requestGuardIndex < requestRetryIndex,
    'generation guard must execute before any retry with a changed access token'
  )

  const blobBlock = source.match(/export async function requestBlob\(path,[\s\S]*?\{([\s\S]*?)\n\}\n\nexport function withFallback/)
  assert.ok(blobBlock, 'requestBlob() block must exist')
  assert.match(blobBlock[1], /const generationAtStart = state\.sessionGeneration/)
  const blobGuardIndex = blobBlock[1].indexOf(requestGuard)
  const blobRetryIndex = blobBlock[1].indexOf('if (state.token && state.token !== accessTokenAtStart) return doFetch()')
  assert.ok(blobGuardIndex >= 0, 'requestBlob() must guard the original logical session')
  assert.ok(blobRetryIndex >= 0, 'requestBlob() may retry only after same-session token rotation')
  assert.ok(
    blobGuardIndex < blobRetryIndex,
    'blob generation guard must execute before any retry with a changed access token'
  )
})

test('上传使用启动时 token，身份切换后的迟到结果必须作废', async () => {
  const source = await readSource(clientUrl)
  const uploadBlock = source.match(/export async function requestUpload\(path, file, fieldName = 'file'\) \{([\s\S]*?)\n\}\n\nexport async function requestBlob/)
  assert.ok(uploadBlock, 'requestUpload() block must exist')
  assert.match(uploadBlock[1], /const generationAtStart = state\.sessionGeneration/)
  assert.match(uploadBlock[1], /const accessTokenAtStart = state\.token/)
  assert.match(uploadBlock[1], /Authorization: `Bearer \$\{accessTokenAtStart\}`/)
  assert.match(uploadBlock[1], /if \(state\.sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
})

test('身份切换在途时禁止旧页面新发业务请求或 refresh', async () => {
  const source = await readSource(clientUrl)

  assert.match(source, /function assertNoRoleSwitchTransition\(\) \{\s*if \(state\.roleSwitchInFlight\) throw staleSessionError\(\)\s*\}/)

  const refreshBlock = source.match(/async function tryRefresh\(\) \{([\s\S]*?)\n\}\n\nasync function ensureToken/)
  assert.ok(refreshBlock, 'tryRefresh() block must exist')
  assert.ok(
    refreshBlock[1].indexOf('assertNoRoleSwitchTransition()') < refreshBlock[1].indexOf("rawRequest('/auth/browser-refresh'"),
    'browser-refresh must be fenced before a request can be sent during role switch'
  )

  const switchBlock = source.match(/export async function switchAuthContext\(contextId, clientType = 'PC'\) \{([\s\S]*?)\n\}\n\nexport function isPlatformSuperAdmin/)
  assert.ok(switchBlock, 'switchAuthContext() block must exist')
  const switchOn = switchBlock[1].indexOf('state.roleSwitchInFlight = true')
  const switchRequest = switchBlock[1].indexOf("rawRequest('/auth/browser-switch-role'")
  const switchOff = switchBlock[1].indexOf('state.roleSwitchInFlight = false')
  assert.ok(switchOn >= 0 && switchRequest >= 0 && switchOff >= 0, 'role switch transition must be explicitly fenced')
  assert.ok(switchOn < switchRequest, 'fence must close before browser-switch-role is sent')
  assert.ok(switchOff > switchRequest, 'fence must reopen only after switch request settles')
  assert.match(switchBlock[1], /try \{[\s\S]*?rawRequest\('\/auth\/browser-switch-role'[\s\S]*?\} finally \{\s*state\.roleSwitchInFlight = false/)

  const requestBlock = source.match(/export async function request\(path, options = \{\}\) \{([\s\S]*?)\n\}\n\nexport async function logoutRemote/)
  const uploadBlock = source.match(/export async function requestUpload\(path, file, fieldName = 'file'\) \{([\s\S]*?)\n\}\n\nexport async function requestBlob/)
  const blobBlock = source.match(/export async function requestBlob\(path,[\s\S]*?\{([\s\S]*?)\n\}\n\nexport function withFallback/)
  for (const [name, block] of [['request', requestBlock], ['upload', uploadBlock], ['blob', blobBlock]]) {
    assert.ok(block, `${name} block must exist`)
    const firstFence = block[1].indexOf('assertNoRoleSwitchTransition()')
    const ensure = block[1].indexOf('await ensureToken()')
    const secondFence = block[1].indexOf('assertNoRoleSwitchTransition()', firstFence + 1)
    assert.ok(firstFence >= 0 && ensure >= 0 && secondFence >= 0, `${name} must fence before and after token restore`)
    assert.ok(firstFence < ensure && ensure < secondFence, `${name} must not send old-role traffic during a switch transition`)
  }
})


test('browser refresh is bound to a nonsecret per-tab session id', async () => {
  const source = await readFile(clientUrl, 'utf8')
  assert.match(source, /const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'/)
  assert.match(source, /sessionStorage\.getItem\(BROWSER_SESSION_ID_KEY\)/)
  assert.match(source, /sessionStorage\.setItem\(BROWSER_SESSION_ID_KEY, generated\)/)
  assert.doesNotMatch(source, /localStorage\.setItem\(BROWSER_SESSION_ID_KEY/)
  assert.match(source, /'X-Browser-Session-Id': getOrCreateBrowserSessionId\(\)/)
  assert.match(source, /loginWithPassword[\s\S]*?headers: browserSessionHeaders\(\)/)
  assert.match(source, /switchAuthContext[\s\S]*?headers: browserSessionHeaders\(\)/)
  assert.match(source, /logoutRemote[\s\S]*?headers: browserSessionHeaders\(\)/)
})
