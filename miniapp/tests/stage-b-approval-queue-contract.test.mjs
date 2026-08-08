import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const api = fs.readFileSync(new URL('../src/services/approvalApi.js', import.meta.url), 'utf8')
const page = fs.readFileSync(new URL('../src/pages/teacher/approval/index.vue', import.meta.url), 'utf8')

test('Stage B B2 pending/done/mine share one real paginated backend queue', () => {
  assert.match(api, /\/approvals\/mobile\/queue\?\$\{params\.join\('&'\)\}/)
  assert.match(api, /getApprovalQueue\('pending'/)
  assert.match(api, /getApprovalQueue\('done'/)
  assert.match(api, /getApprovalQueue\('mine'/)
  assert.match(api, /keyword=\$\{encodeURIComponent\(kw\)\}/)
  assert.match(api, /studentNo/)
  assert.match(api, /sourceBizId/)
})

test('Stage B B2 teacher approval page exposes real search and incremental pagination', () => {
  assert.match(page, /搜姓名、学号、任务号、业务单号/)
  assert.match(page, /const PAGE_SIZE = 20/)
  assert.match(page, /onReachBottom\(\)[\s\S]*this\.loadMore\(\)/)
  assert.match(page, /getApprovalQueue\(this\.sub, nextPage, this\.pageSize, this\.keyword\)/)
  assert.match(page, /this\.list = \[\.\.\.this\.list, \.\.\.next\]/)
  assert.doesNotMatch(page, /下一阶段开放|暂未开放|mock/i)
})

test('Stage B continuous approval queue refreshes server truth after actions', () => {
  assert.match(page, /await this\.load\(true\)/)
  assert.match(api, /allowedActions\.includes\(normalized\)/)
  assert.match(api, /version = Number\(fresh\?\.version\)/)
  assert.doesNotMatch(page, /task\.status\s*=|a\.status\s*=/)
})
