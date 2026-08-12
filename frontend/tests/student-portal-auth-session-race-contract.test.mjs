import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const requestUrl = new URL('../../student-portal/src/services/request.js', import.meta.url)

async function source() {
  return readFile(requestUrl, 'utf8')
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
  assert.match(text, /credentials: 'same-origin'/)
  assert.match(text, /let accessToken = ''/)
  assert.doesNotMatch(text, /sessionStorage\.setItem\(TOKEN_KEY/)
  assert.doesNotMatch(text, /localStorage\.setItem\(TOKEN_KEY/)
  assert.doesNotMatch(text, /sessionStorage\.setItem\(REFRESH_KEY/)
  assert.doesNotMatch(text, /localStorage\.setItem\(REFRESH_KEY/)
})
