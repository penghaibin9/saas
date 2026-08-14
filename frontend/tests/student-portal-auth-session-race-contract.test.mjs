import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const requestUrl = new URL('../../student-portal/src/services/request.js', import.meta.url)

// 本仓 core.autocrlf=true 且无 .gitattributes：Windows 检出把源码换成 CRLF，
// 而下面的结构性正则按 LF 书写。不归一化则这些会话竞态守卫在 Windows 本地
// 全部静默不匹配（只有 Linux CI 才真的跑到）。只统一换行，不放宽任何断言。
async function source() {
  return (await readFile(requestUrl, 'utf8')).split('\r\n').join('\n')
}

test('student portal refresh is generation-bound and cannot overwrite a newer session', async () => {
  const text = await source()

  assert.match(text, /let sessionGeneration = 0/)
  assert.match(text, /const generationAtStart = sessionGeneration/)
  assert.match(text, /const accessTokenAtStart = accessToken/)
  assert.match(
    text,
    /if \(sessionGeneration !== generationAtStart \|\| accessToken !== accessTokenAtStart\) \{\s*throw staleSessionError\(\)/
  )
  assert.match(text, /e\.code = 'SESSION_CHANGED'/)
  assert.match(text, /e\.staleSession = true/)
  assert.match(
    text,
    /if \(!e\.staleSession && sessionGeneration === generationAtStart && accessToken === accessTokenAtStart\) \{\s*_invalidateIfCurrent\(accessTokenAtStart\)/
  )
})

test('student portal business requests cannot replay under a newer login session', async () => {
  const text = await source()

  const requestBlock = text.match(/export async function request\(path,[\s\S]*?\{([\s\S]*?)\n\}\n\nexport async function uploadFile/)
  assert.ok(requestBlock, 'request() block must exist')
  assert.match(requestBlock[1], /const generationAtStart = sessionGeneration/)
  assert.match(requestBlock[1], /if \(auth && sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
  assert.match(requestBlock[1], /await refreshOnce\(\)[\s\S]*?if \(sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)

  const uploadBlock = text.match(/export async function uploadFile\(path,[\s\S]*?\{([\s\S]*?)\n\}\n\nexport async function downloadFile/)
  assert.ok(uploadBlock, 'uploadFile() block must exist')
  assert.match(uploadBlock[1], /const generationAtStart = sessionGeneration/)
  assert.match(uploadBlock[1], /if \(auth && sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)

  const downloadBlock = text.match(/export async function downloadFile\(path,[\s\S]*?\{([\s\S]*?)\n\}\s*$/)
  assert.ok(downloadBlock, 'downloadFile() block must exist')
  assert.match(downloadBlock[1], /const generationAtStart = sessionGeneration/)
  assert.match(downloadBlock[1], /if \(sessionGeneration !== generationAtStart\) throw staleSessionError\(\)/)
})

test('student portal F5 restores only auth me through HttpOnly refresh cookie', async () => {
  const text = await source()

  assert.match(
    text,
    /if \(auth && !_retried && path === '\/auth\/me' && !getToken\(\)\) \{\s*await refreshOnce\(\)\s*return request\(path, \{ method, body, auth, params, query, _retried: true \}\)/
  )
  assert.match(text, /if \(auth && !_retried && !path\.startsWith\('\/auth\/'\)\) \{/)
  assert.doesNotMatch(text, /path === '\/auth\/login' && !getToken\(\)[\s\S]*?await refreshOnce\(\)/)
  assert.doesNotMatch(text, /path === '\/auth\/captcha' && !getToken\(\)[\s\S]*?await refreshOnce\(\)/)
})

test('student portal late 401 only invalidates the token that actually made that request', async () => {
  const text = await source()

  assert.match(text, /function _invalidateIfCurrent\(tokenAtStart\)/)
  assert.match(text, /if \(accessToken !== tokenAtStart\) return false/)
  assert.doesNotMatch(text, /if \(auth\) accessToken = ''/)

  const guardedInvalidations = text.match(/_invalidateIfCurrent\(token\)/g) || []
  assert.ok(guardedInvalidations.length >= 2, 'normal requests and uploads need current-token invalidation')
  assert.match(text, /downloadFile[\s\S]*?_invalidateIfCurrent\(token\)/)
})

test('student portal browser session stays memory plus HttpOnly-cookie only', async () => {
  const text = await source()

  assert.match(text, /\/auth\/browser-refresh/)
  assert.match(text, /return path === '\/auth\/login' \? '\/auth\/browser-login' : path/)
  // Student Portal supports a configured API origin, so browser auth requests must include the
  // HttpOnly refresh cookie for that explicitly CORS-whitelisted origin.
  assert.match(text, /credentials: 'include'/)
  assert.match(text, /let accessToken = ''/)
  assert.doesNotMatch(text, /sessionStorage\.setItem\(TOKEN_KEY/)
  assert.doesNotMatch(text, /localStorage\.setItem\(TOKEN_KEY/)
  assert.doesNotMatch(text, /sessionStorage\.setItem\(REFRESH_KEY/)
  assert.doesNotMatch(text, /localStorage\.setItem\(REFRESH_KEY/)
})


test('student portal browser auth binds HttpOnly refresh to this tab id only', async () => {
  const text = await source()
  assert.match(text, /const BROWSER_SESSION_ID_KEY = 'gx_browser_session_id_v2'/)
  assert.match(text, /sessionStorage\.getItem\(BROWSER_SESSION_ID_KEY\)/)
  assert.match(text, /sessionStorage\.setItem\(BROWSER_SESSION_ID_KEY, generated\)/)
  assert.doesNotMatch(text, /localStorage\.setItem\(BROWSER_SESSION_ID_KEY/)
  assert.match(text, /'X-Browser-Session-Id': getOrCreateBrowserSessionId\(\)/)
  assert.match(text, /value === '\/auth\/login' \|\| value\.startsWith\('\/auth\/browser-'\)/)
  assert.match(text, /\.\.\.browserSessionHeaders\(\)/)
})
