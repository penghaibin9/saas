import assert from 'node:assert/strict'
import test from 'node:test'
import { scanState, scanFilesReady, refreshScanFiles } from '../src/services/fileScanState.js'

const pending = { fileId: '9007199254740993', fileName: '实习成果.docx', status: 'QUARANTINED', scanStatus: 'PENDING', readyForBusiness: false }
test('pending upload retains its string identity and blocks submission', () => {
  const file = scanState(pending)
  assert.equal(file.fileId, '9007199254740993')
  assert.equal(file.statusText, '等待安全扫描')
  assert.equal(scanFilesReady([file]), false)
})
test('refresh releases only an explicitly ready clean available file', async () => {
  const files = await refreshScanFiles([pending], async () => ({ ...pending, status: 'AVAILABLE', scanStatus: 'CLEAN', readyForBusiness: true }))
  assert.equal(scanFilesReady(files), true)
})
test('infected or unavailable files cannot be marked ready by a truthy value', () => {
  for (const patch of [{ scanStatus: 'INFECTED', readyForBusiness: true }, { readyForBusiness: 'true' }, { status: 'DELETED', scanStatus: 'CLEAN', readyForBusiness: true }]) {
    assert.equal(scanState({ ...pending, ...patch }).readyForBusiness, false)
  }
})
test('unknown machine status and raw scanner response never reach the display', () => {
  const file = scanState({ ...pending, scanStatus: 'NEW_ENGINE_ERROR', statusText: '/secret/path: SQL error' })
  assert.equal(file.statusText, '文件状态待确认')
})
test('late response after a context switch is discarded', async () => {
  assert.equal(await refreshScanFiles([pending], async () => pending, () => false), null)
})
test('network failure retains the original pending attachment', async () => {
  const original = [pending]
  await assert.rejects(refreshScanFiles(original, async () => { throw new Error('network') }))
  assert.equal(original[0], pending)
})
test('a mismatched file response is rejected without replacing the original', async () => {
  await assert.rejects(refreshScanFiles([pending], async () => ({ fileId: 'other' })), /附件读取结果不一致/)
})
test('approved legacy business attachment remains submittable', () => {
  assert.equal(scanFilesReady([{ fileId: '88', fileName: '原审核附件.pdf' }]), true)
})
