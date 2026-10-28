import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizePreviewError } from '../src/components/file/viewer/viewer-contract.js'

test('文档预览不向用户透传浏览器引擎错误或内部地址', () => {
  const result = normalizePreviewError(new Error('Setting up fake worker failed: Failed to fetch dynamically imported module: https://private.invalid/assets/pdf.worker.mjs'))
  assert.equal(result.message, '文件预览失败，请重试或下载原文查看')
  assert.equal(result.retryable, true)
  assert.doesNotMatch(result.message, /https|worker|module/)
})

test('文档预览保留中文业务原因和不可重试限制', () => {
  const result = normalizePreviewError({ code: 'PREVIEW_TOO_LARGE', message: '文件超过站内阅读上限，请下载原文查看' })
  assert.equal(result.message, '文件超过站内阅读上限，请下载原文查看')
  assert.equal(result.retryable, false)
  assert.equal(normalizePreviewError({ message: '材料需要更换', retryable: false }).retryable, false)
})
