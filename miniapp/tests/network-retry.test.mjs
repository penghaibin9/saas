import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as generation from '../src/services/sessionGeneration.mjs'

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
