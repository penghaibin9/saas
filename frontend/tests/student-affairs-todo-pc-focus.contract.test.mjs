import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')

const cases = [
  ['src/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue', 'focusRecordFromRoute', 'leaveApi.detail(recordId)'],
  ['src/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue', 'focusRecordFromRoute', 'leaveApi.detail(recordId)'],
  ['src/modules/studentAffairs/views/AidWorkbenchView.vue', 'initRouteFocus', 'studentAffairsApi.getAidDetail(recordId)'],
  ['src/modules/studentAffairs/views/FundingWorkbenchView.vue', 'initRouteFocus', 'studentAffairsApi.getFundingDetail(recordId)'],
  ['src/modules/studentAffairs/views/DisciplineWorkbenchView.vue', 'initRouteFocus', 'studentAffairsApi.getDisciplineDetail(recordId)'],
]

test('PC 学工待办 exact 落点必须真实消费 recordId 并先查 detail', () => {
  for (const [file, focusFn, detailCall] of cases) {
    const src = read(file)
    assert.match(src, /\$route\.query\?\.recordId|\$route\.query\.recordId/, `${file} 必须消费 recordId`)
    assert.ok(src.includes(focusFn), `${file} 缺少对象聚焦函数`)
    assert.ok(src.includes(detailCall), `${file} 必须先调用既有详情 API`)
  }
})

test('困难认定与奖助不能用默认首批次/首项目覆盖 recordId 真值', () => {
  const aid = read('src/modules/studentAffairs/views/AidWorkbenchView.vue')
  assert.ok(aid.includes("this.batchId = String(res.data.batchId || '')"))
  assert.ok(aid.includes('已停止自动回退到其他批次'))

  const funding = read('src/modules/studentAffairs/views/FundingWorkbenchView.vue')
  assert.ok(funding.includes("this.batchId = String(res.data.batchId || '')"))
  assert.ok(funding.includes("const projectId = String(batch.projectId || '')"))
  assert.ok(funding.includes('已停止自动回退到其他项目'))
})

test('销假/续假/逾期待办使用动作真实状态，不接受 PENDING 混用', () => {
  const follow = read('src/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue')
  for (const status of ['EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE']) assert.ok(follow.includes(status))
  assert.match(follow, /valid = new Set\(\['EXTENSION_REVIEW', 'WAIT_CANCEL_LEAVE', 'OVERDUE', 'APPROVED'\]\)/)
})
