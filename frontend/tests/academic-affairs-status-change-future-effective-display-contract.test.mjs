import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const constantsUrl = new URL('../src/modules/academicAffairs/constants/status-change.js', import.meta.url)
const detailUrl = new URL('../src/modules/academicAffairs/views/AaStatusChangeDetailView.vue', import.meta.url)

test('D3-U exposes the canonical pending-effective status as a first-class display state', async () => {
  const source = await readFile(constantsUrl, 'utf8')

  assert.match(source, /APPROVED_PENDING_EFFECTIVE: '已通过·待生效'/)
  assert.match(source, /case 'APPROVED_PENDING_EFFECTIVE': return 'warning'/)
})

test('D3-U detail keeps completed approval nodes completed while waiting for effective date', async () => {
  const source = await readFile(detailUrl, 'utf8')

  assert.match(source, /const PENDING_EFFECTIVE = 'APPROVED_PENDING_EFFECTIVE'/)
  assert.match(source, /workflowFinished\(\)/)
  assert.match(source, /this\.change\?\.status === 'EFFECTIVE' \|\| this\.isPendingEffective/)
  assert.match(source, /if \(this\.workflowFinished\) return 'is-done'/)
  assert.match(source, /if \(this\.workflowFinished\) return '已通过'/)
})

test('D3-U final approval copy distinguishes scheduled effective from immediate effective', async () => {
  const source = await readFile(detailUrl, 'utf8')

  assert.match(source, /该申请设置指定生效时间/)
  assert.match(source, /将先进入「已通过·待生效」/)
  assert.match(source, /当前学籍不会提前改写/)
  assert.match(source, /通过后异动将立即生效并写入学籍主档/)
  assert.match(source, /终审已经通过，当前学籍尚未变更/)
})
