import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('学生 PC 首页用具体业务 ID 生成五类任务落点', () => {
  const home = read('../src/views/academic/StudentAcademicHomeView.vue')

  for (const field of ['batchId', 'taskId', 'warningId', 'deferId', 'optionId']) {
    assert.ok(home.includes(field), `首页缺少业务 ID：${field}`)
  }
  for (const target of [
    "withQuery('/academic/registration'", "withQuery('/academic/evaluation'",
    "withQuery('/academic/warning'", "withQuery('/academic/exam'", "withQuery('/academic/makeup'"
  ]) assert.ok(home.includes(target), `首页缺少精确目标：${target}`)
  assert.ok(home.includes('failedSources'))
  assert.ok(home.includes('已保留其他真实任务'))
})

test('学生 PC 目标页面消费首页传入的业务 ID', () => {
  const contracts = [
    ['../src/views/academic/StudentRegistrationView.vue', 'route.query.batchId'],
    ['../src/views/academic/StudentEvaluationView.vue', 'route.query.taskId'],
    ['../src/views/academic/StudentAcademicReadOnlyView.vue', 'route.query.warningId'],
    ['../src/views/academic/StudentExamView.vue', 'route.query.deferId'],
    ['../src/views/academic/StudentMakeupView.vue', 'route.query.optionId']
  ]
  for (const [path, marker] of contracts) {
    const source = read(path)
    assert.ok(source.includes(marker), `${path} 未消费 ${marker}`)
    assert.ok(source.includes('is-target'), `${path} 未显示精确落点`)
  }
})

test('学生注册使用非阻塞确认并在成功后保留动作回执', () => {
  const source = read('../src/views/academic/StudentRegistrationView.vue')

  assert.equal(source.includes('window.confirm'), false)
  for (const marker of [
    'role="dialog"', 'aria-modal="true"', '确认并提交注册',
    'actionReceipt', '本学期注册已完成', '查看本学期课表'
  ]) assert.ok(source.includes(marker), `学生注册缺少非阻塞确认/回执契约：${marker}`)
})
