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
