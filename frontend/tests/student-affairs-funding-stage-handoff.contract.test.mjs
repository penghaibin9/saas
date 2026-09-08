import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')

test('资助工作台进入公示必须携带同一 projectId/batchId', () => {
  const src = read('src/modules/studentAffairs/views/FundingWorkbenchView.vue')
  assert.ok(src.includes("path: '/admin/student-affairs/funding/publicity'"))
  assert.ok(src.includes("batchId: String(this.batchId)"))
  assert.ok(src.includes("projectId: String(this.projectId)"))
  assert.ok(src.includes("source: 'funding-workbench'"))
})

test('公示页保留当前批次且仅对已获资助对象提供人工发放入口', () => {
  const src = read('src/modules/studentAffairs/views/funding/FundingPublicityView.vue')
  assert.ok(src.includes("batchId: this.batchId || undefined"))
  assert.ok(src.includes('this.grantedCount > 0'))
  assert.ok(!src.includes('本批次公示已完成')); assert.ok(src.includes('查看本批次发放台账'))
  assert.ok(src.includes("path: '/admin/student-affairs/funding/disbursements'"))
  assert.ok(src.includes("source: 'publicity'"))
  assert.ok(!src.includes("toast.success('已确认获资助')\n        this.goDisbursement"), '逐条确认后不得强制跳页')
})

test('发放页的记录、生成上下文和 Excel 导出使用同一 batchId', () => {
  const src = read('src/modules/studentAffairs/views/funding/FundingDisbursementView.vue')
  assert.ok(src.includes("this.genBatchId = batchId"))
  assert.ok(src.includes('batchId: this.genBatchId || undefined'))
  assert.ok(src.includes('fundingExportApi.create({'))
  assert.ok(src.includes('汇总、记录与导出使用同一批次'))
  assert.ok(src.includes('已停止自动回退到其他批次'))
})
