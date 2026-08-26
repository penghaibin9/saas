import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

async function importRequestWithViteEnv() {
  const fileUrl = new URL('../src/services/request.js', import.meta.url)
  const source = await readFile(fileUrl, 'utf8')
  const viteEnv = `({ VITE_API_BASE_URL: '', DEV: false })`
  const transformed = source.replaceAll('import.meta.env', viteEnv)
  const dataUrl = `data:text/javascript;base64,${Buffer.from(transformed).toString('base64')}`
  return import(`${dataUrl}#captcha-test=${Date.now()}`)
}

test('public login 401 preserves captcha bizCode and details', async () => {
  const previousFetch = globalThis.fetch
  globalThis.fetch = async () => ({
    status: 401,
    json: async () => ({
      code: 401001,
      bizCode: 'CAPTCHA_REQUIRED',
      message: '请输入验证码',
      details: { captchaRequired: true, scene: 'PASSWORD_LOGIN' },
      traceId: 'trace-captcha'
    })
  })
  try {
    const mod = await importRequestWithViteEnv()
    await assert.rejects(
      () => mod.request('/auth/login', { method: 'POST', auth: false, body: { loginName: 'student' } }),
      (error) => {
        assert.equal(error.code, 401001)
        assert.equal(error.bizCode, 'CAPTCHA_REQUIRED')
        assert.deepEqual(error.details, { captchaRequired: true, scene: 'PASSWORD_LOGIN' })
        assert.equal(error.traceId, 'trace-captcha')
        return true
      }
    )
  } finally {
    globalThis.fetch = previousFetch
  }
})
