import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as generation from '../src/services/sessionGeneration.mjs'

function responseApi(statusCode, data) {
  const source = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '')
    .replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const toasts = []
  const reply = options => options.success({ statusCode, data })
  const uni = { getStorageSync: () => '', showToast: value => toasts.push(value), request: reply, uploadFile: reply }
  return { ...new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation),
    `${source}\nreturn { realRequest, realUpload, normalizeError, isNetworkError }`)(
    { useMock: false, allowMockFallback: false, apiBaseUrl: 'http://127.0.0.1:8000', apiPrefix: '/api/v1' },
    () => {}, uni, ...Object.values(generation)), toasts }
}

test('login and uploads preserve gateway HTTP errors without claiming a network failure or exposing HTML', async () => {
  for (const status of [404, 405, 502, 503]) {
    for (const body of ['<html>gateway secret</html>', { detail: 'Not Found' }, { code: 0, data: { accessToken: 'must-not-accept' } }]) {
      const api = responseApi(status, body)
      for (const send of [() => api.realRequest('/auth/login', { method: 'POST', auth: false }),
        () => api.realUpload('/files', '/test.pdf', { auth: false })]) {
        await assert.rejects(send(), error => {
          assert.equal(error.code, 'HTTP_ERROR')
          assert.equal(error.httpStatus, status)
          assert.equal(api.isNetworkError(error), false)
          assert.equal(api.normalizeError(error).pageState, 'error')
          assert.doesNotMatch(error.message, /secret|html|响应结构异常/)
          if (status < 500) assert.match(error.message, new RegExp(`HTTP ${status}`))
          return true
        })
      }
      assert.deepEqual(api.toasts, [])
    }
  }
})

test('HTTP handling preserves business rejection, valid login JSON and malformed success rejection', async () => {
  const denied = responseApi(422, { code: 422001, message: '请填写学校编码' })
  await assert.rejects(denied.realRequest('/auth/login', { method: 'POST', auth: false }), error =>
    error.code === 422001 && error.biz === true && error.message === '请填写学校编码')
  const valid = responseApi(200, JSON.stringify({ code: 0, data: { accessToken: 'test-only' } }))
  assert.deepEqual(await valid.realRequest('/auth/login', { method: 'POST', auth: false }), { accessToken: 'test-only' })
  const malformed = responseApi(200, '<html>bad body</html>')
  await assert.rejects(malformed.realRequest('/auth/login', { method: 'POST', auth: false }), error => error.code === 'BAD_RESPONSE')
})

test('unauthenticated password login presents captcha and credential rejection instead of session expiry', async () => {
  const captcha = responseApi(401, {
    code: 401001,
    bizCode: 'CAPTCHA_REQUIRED',
    message: '请输入图形验证码后继续',
    details: { captchaRequired: true, scene: 'PASSWORD_LOGIN' }
  })
  await assert.rejects(captcha.realRequest('/auth/login', { method: 'POST', auth: false }), error => {
    assert.equal(error.loginAttempt, true)
    assert.equal(error.message, '请输入图形验证码后继续')
    assert.equal(error.bizCode, 'CAPTCHA_REQUIRED')
    assert.equal(captcha.normalizeError(error).kind, 'invalid')
    assert.doesNotMatch(captcha.normalizeError(error).text, /登录已失效/)
    return true
  })

  const credentials = responseApi(401, {
    code: 401001,
    bizCode: 'UNAUTHORIZED',
    message: '账号、学校编码或密码不正确'
  })
  await assert.rejects(credentials.realRequest('/auth/browser-login', { method: 'POST', auth: false }), error => {
    assert.equal(error.message, '账号、学校编码或密码不正确')
    assert.equal(credentials.normalizeError(error).text, '账号、学校编码或密码不正确')
    return true
  })

  const expired = responseApi(401, { code: 401001, bizCode: 'UNAUTHORIZED', message: '令牌已失效' })
  await assert.rejects(expired.realRequest('/protected', { auth: true, _retried: true }), error => {
    assert.equal(error.loginAttempt, false)
    assert.equal(error.message, '登录已失效，请重新登录')
    assert.equal(expired.normalizeError(error).pageState, 'unauthorized')
    return true
  })
})

function setup(allowMockFallback = false) {
  const source = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '')
    .replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  let calls = 0
  const uni = {
    getStorageSync: () => '', showToast() {},
    request(options) {
      calls++
      if (calls === 1) options.fail({ errMsg: 'request:fail timeout' })
      else options.success({ statusCode: 200, data: { code: 0, data: { recovered: true } } })
    }
  }
  const api = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation),
    `${source}\nreturn { realRequest, realFirstStrict, normalizeError }`)(
    { useMock: false, allowMockFallback, apiBaseUrl: 'http://127.0.0.1:18310', apiPrefix: '/api/v1', requestTimeout: 8000 },
    () => {}, uni, ...Object.values(generation))
  return { ...api, calls: () => calls }
}

test('real-only retry sends a new request immediately after a timeout without mock fallback', async () => {
  const api = setup()
  const read = () => api.realFirstStrict('workbench', () => api.realRequest('/workbench', { auth: false }),
    () => { throw new Error('mock must never run') })
  await assert.rejects(read(), error => error.code === 'NETWORK')
  assert.deepEqual(await read(), { recovered: true })
  assert.equal(api.calls(), 2)
})

test('explicit development fallback keeps its existing offline cooldown', async () => {
  const api = setup(true)
  await assert.rejects(api.realRequest('/workbench', { auth: false }))
  assert.equal(await api.realFirstStrict('demo', () => api.realRequest('/workbench'), () => 'demo'), 'demo')
  assert.equal(api.calls(), 1)
})

test('GET omits absent optional query values before the H5 adapter serializes them', async () => {
  const source = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '')
    .replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  let sent
  const uni = {
    getStorageSync: () => '', showToast() {},
    request(options) {
      sent = options
      queueMicrotask(() => options.success({ statusCode: 200, data: { code: 0, data: { ok: true } } }))
    }
  }
  const realRequest = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), `${source}\nreturn realRequest`)(
    { useMock: false, allowMockFallback: false, apiBaseUrl: 'http://127.0.0.1:18310', apiPrefix: '/api/v1', requestTimeout: 8000 },
    () => {}, uni, ...Object.values(generation))

  await realRequest('/mobile/academic/schedule/my', {
    auth: false,
    data: { week: undefined, term: null, page: 1, keyword: '' }
  })
  assert.deepEqual(sent.data, { page: 1, keyword: '' })
})

test('mobile request presentation distinguishes denial, license, auth and transport failure', () => {
  const { normalizeError } = setup()
  for (const [error, expected] of [
    [{ code: '403001', bizCode: 'NO_PERMISSION' }, 'forbidden'],
    [{ httpStatus: 403 }, 'forbidden'],
    [{ response: { status: 403 } }, 'forbidden'],
    [{ code: 403001, message: '模块未购买或未授权：academicAffairs' }, 'noLicense'],
    [{ code: 401001 }, 'unauthorized'],
    [{ code: 'NETWORK', message: '没有权限' }, 'offline'],
    [{ httpStatus: 503, code: 403001 }, 'error']
  ]) {
    const result = normalizeError(error)
    assert.equal(result.pageState, expected)
    assert.doesNotMatch(result.text, /academicAffairs|NO_PERMISSION/)
  }
})

test('transport never exposes gateway or database text, while a short Chinese validation reason remains actionable', async () => {
  const source = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '')
    .replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const makeApi = (body) => {
    const uni = {
      getStorageSync: () => '', showToast() {},
      request(options) { queueMicrotask(() => options.success({ statusCode: 200, data: body })) }
    }
    return new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), `${source}\nreturn { realRequest, normalizeError }`)(
      { useMock: false, allowMockFallback: false, apiBaseUrl: 'https://school.test', apiPrefix: '/api/v1', requestTimeout: 1000 },
      () => {}, uni, ...Object.values(generation))
  }

  const unsafe = makeApi({ code: 422001, bizCode: 'VALIDATION_ERROR', message: 'sqlalchemy.exc: SELECT password FROM users' })
  await assert.rejects(unsafe.realRequest('/safe-error', { auth: false }), (error) => {
    assert.equal(error.message, '填写内容有误，请检查后重试')
    assert.equal(error.serverMessage, 'sqlalchemy.exc: SELECT password FROM users')
    assert.equal(unsafe.normalizeError(error).text, '填写内容有误，请检查后重试')
    return true
  })

  const actionable = makeApi({ code: 422001, bizCode: 'VALIDATION_ERROR', message: '请填写不少于5字的退回原因' })
  await assert.rejects(actionable.realRequest('/safe-error', { auth: false }), (error) => {
    assert.equal(error.message, '请填写不少于5字的退回原因')
    assert.equal(actionable.normalizeError(error).text, '请填写不少于5字的退回原因')
    return true
  })
})

test('download transport never displays a native error string', async () => {
  const source = readFileSync(new URL('../src/services/request.js', import.meta.url), 'utf8')
    .replace(/^import[\s\S]*?from ['"][^'"]+['"];?\r?\n/gm, '')
    .replace(/export default[\s\S]*$/, '').replace(/^export /gm, '')
  const uni = {
    getStorageSync: () => '', showToast() {},
    downloadFile(options) { queueMicrotask(() => options.fail({ errMsg: 'downloadFile:fail https://gateway.internal/secret' })) }
  }
  const api = new Function('ENV', 'markMobileViewsDirty', 'uni', ...Object.keys(generation), `${source}\nreturn { realDownload }`)(
    { useMock: false, allowMockFallback: false, apiBaseUrl: 'https://school.test', apiPrefix: '/api/v1', requestTimeout: 1000 },
    () => {}, uni, ...Object.values(generation))
  await assert.rejects(api.realDownload('/files/1', { auth: false }), (error) => {
    assert.equal(error.message, '附件下载失败，请检查网络后重试')
    assert.equal(error.serverMessage, 'downloadFile:fail https://gateway.internal/secret')
    return true
  })
})
