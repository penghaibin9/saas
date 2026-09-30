import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/modules/studentAffairs/views/funding/WorkStudyView.vue', import.meta.url), 'utf8')
const fundingWorkbench = readFileSync(new URL('../src/modules/studentAffairs/views/FundingWorkbenchView.vue', import.meta.url), 'utf8')

test('teacher PC work-study opens on pending work without duplicate overview cards', () => {
  assert.match(source, /recordQuery: \{ postId: '', status: 'APPLIED'/)
  assert.match(source, /class="ws-statusbar"/)
  assert.match(source, /setRecordStatus\('APPLIED'\)/)
  assert.match(source, /setRecordStatus\('ONBOARD'\)/)
  assert.match(source, /title: '下一步'/)
  assert.doesNotMatch(source, /ws-overview|本月先处理|ws-status-line/)
})

test('teacher PC funding workbench avoids duplicate empty panels and opens the first task', () => {
  assert.match(fundingWorkbench, /v-if="batchId" class="fd-toolbar"/)
  assert.match(fundingWorkbench, /v-if="batchId && filteredList\.length" class="fd-detail"/)
  assert.match(fundingWorkbench, /this\.selected = this\.list\[0\]/)
  assert.doesNotMatch(fundingWorkbench, /请从左侧选择一条申请/)
})
