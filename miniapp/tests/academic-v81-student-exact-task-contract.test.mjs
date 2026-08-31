import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')

test('学生小程序首页把五类任务精确落到首个业务对象', () => {
  const home = read('../src/pages/student/academic-affairs/index.vue')
  for (const field of ['row.batchId', 'row.taskId', 'row.warningId', 'row.deferId', 'row.gradeId']) {
    assert.ok(home.includes(field), `缺少具体业务 ID：${field}`)
  }
  assert.ok(home.includes('?id=${encodeURIComponent(id)}'))
  assert.ok(home.includes('taskTargets'))
  assert.ok(home.includes('taskDetails'))
  assert.ok(home.includes('failedSources'))
})

test('学生小程序五个目标页消费 id 并显示精确落点', () => {
  for (const path of [
    '../src/pages/student/academic-affairs/registration.vue',
    '../src/pages/student/academic-affairs/evaluation.vue',
    '../src/pages/student/academic-affairs/warning.vue',
    '../src/pages/student/academic-affairs/exam.vue',
    '../src/pages/student/academic-affairs/makeup.vue'
  ]) {
    const source = read(path)
    assert.ok(source.includes("options.id || ''"), `${path} 未消费首页 id`)
    assert.ok(source.includes('is-target'), `${path} 未显示精确落点`)
  }
})

test('学生小程序学期注册把已完成结果作为持久回执展示', () => {
  const registration = read('../src/pages/student/academic-affairs/registration.vue')
  assert.ok(registration.includes("b.registrationStatus === 'REGISTERED'"))
  assert.ok(registration.includes('role="status"'))
  assert.ok(registration.includes('✓ 本学期注册已完成'))
  assert.ok(registration.includes("'已完成注册'"))
})
