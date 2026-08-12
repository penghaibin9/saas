import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const printUrl = new URL('../src/modules/academicAffairs/views/AaStatusChangePrintView.vue', import.meta.url)
const portalUrl = new URL('../../student-portal/src/views/academic/StudentStatusView.vue', import.meta.url)
const miniappUrl = new URL('../../miniapp/src/pages/student/academic-affairs/status.vue', import.meta.url)

test('D3-U print shows scheduled effective time independently from suspend expiry', async () => {
  const source = await readFile(printUrl, 'utf8')

  assert.match(source, /<th>生效方式<\/th>/)
  assert.match(source, /<th>计划生效时间<\/th>/)
  assert.match(source, /change\.effectiveDate \? '指定日期' : '终审通过立即生效'/)
  assert.match(source, /<tr v-if="change\.expireDate"><th>休学到期<\/th><td colspan="3">/)
  assert.doesNotMatch(source, /v-if="change\.expireDate"[^\n]*change\.effectiveDate/)
})

test('D3-U student portal consumes canonical change records and statuses', async () => {
  const source = await readFile(portalUrl, 'utf8')

  assert.match(source, /data\.changes/)
  assert.match(source, /IN_REVIEW: '审批中'/)
  assert.match(source, /APPROVED_PENDING_EFFECTIVE: '已通过·待生效'/)
  assert.match(source, /EFFECTIVE: '已生效'/)
  assert.match(source, /record\.effectiveDate/)
})

test('D3-U miniapp localizes pending-effective and shows planned time', async () => {
  const source = await readFile(miniappUrl, 'utf8')

  assert.match(source, /APPROVED_PENDING_EFFECTIVE: '已通过·待生效'/)
  assert.match(source, /c\.status === 'APPROVED_PENDING_EFFECTIVE'/)
  assert.match(source, /c\.effectiveDate/)
})
