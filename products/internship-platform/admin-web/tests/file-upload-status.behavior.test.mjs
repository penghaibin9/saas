import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { normalizeUiError } from '../src/utils/presentationSafety.js'

const source = fs.readFileSync(new URL('../src/services/file/fileSdk.js', import.meta.url), 'utf8')
  .replace(/^import[^\n]*\n/gm, '')
  .replace(/^export default fileSdk\s*$/m, '')
  .replace(/^export /gm, '')

for (const [status, expectedState] of [[500, 'error'], [403, 'forbidden'], [409, 'error'], [408, 'error']]) {
  test(`上传失败保留真实响应状态 ${status}，业务数字码不覆盖它`, async () => {
    class UploadRequest {
      status = status
      responseText = JSON.stringify({ code: 1, message: '上传未完成' })
      upload = {}
      open() {}
      setRequestHeader() {}
      send() { queueMicrotask(() => this.onload()) }
    }
    const createUpload = new Function('XMLHttpRequest', 'FormData', 'getToken', 'API_BASE_URL', 'API_PREFIX',
      `${source}\nreturn createFileUploadTask`)(UploadRequest, class { append() {} }, () => '', '', '/api/v1')
    const task = createUpload({ name: '合成材料.pdf', size: 10 })
    await assert.rejects(task.promise, error => {
      assert.equal(error.code, 1)
      assert.equal(error.httpStatus, status)
      assert.equal(normalizeUiError(error).pageState, expectedState)
      if (status === 500) assert.equal(normalizeUiError(error).userMessage, '系统暂时无法完成该操作，请稍后重试')
      return true
    })
  })
}
