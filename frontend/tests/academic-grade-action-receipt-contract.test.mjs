import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('成绩录入提交后展示业务对象、当前状态和下一责任角色', () => {
  const entry = read('../src/modules/academicAffairs/views/AaGradeEntryView.vue')

  for (const contract of [
    'submitReceipt', 'role="status"', 'submitReceipt.courseName', 'submitReceipt.taskId',
    'statusLabel(submitReceipt.status)', '学院成绩审核人', '继续下一门'
  ]) assert.ok(entry.includes(contract), `成绩录入回执缺少：${contract}`)

  assert.ok(entry.includes('this.submitReceipt = { taskId: this.task.gradeTaskId'))
})

test('学院复核与教务发布均保留可核验动作回执', () => {
  const review = read('../src/modules/academicAffairs/views/AaGradeCollegeReviewView.vue')
  const publish = read('../src/modules/academicAffairs/views/AaGradePublishView.vue')

  for (const contract of ['receipt.taskId', 'receipt.courseName', 'statusLabel(receipt.status)', 'role="status"']) {
    assert.ok(review.includes(contract), `学院复核回执缺少：${contract}`)
    assert.ok(publish.includes(contract), `教务发布回执缺少：${contract}`)
  }
  assert.ok(review.includes('教务处终审发布'))
  assert.ok(review.includes('任课教师修改后重新提交'))
  assert.ok(publish.includes('成绩已正式发布'))
  assert.ok(publish.includes('未产生新的正式成绩投影'))
  assert.ok(publish.includes('res.data.projected'))
  assert.ok(publish.includes('res.data.failCount'))
})

test('动作回执在窄屏降为单列', () => {
  const files = [
    read('../src/modules/academicAffairs/views/AaGradeEntryView.vue'),
    read('../src/modules/academicAffairs/views/AaGradeCollegeReviewView.vue'),
    read('../src/modules/academicAffairs/views/AaGradePublishView.vue')
  ]
  for (const source of files) {
    assert.ok(source.includes('@media (max-width: 760px)'))
    assert.ok(source.includes('grid-template-columns: 1fr'))
  }
})
