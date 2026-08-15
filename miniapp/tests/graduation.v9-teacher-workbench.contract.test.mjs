import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')
const adapter = read('src/services/graduationTeacherPagingApi.js')
const guide = read('src/pages/teacher/graduation-guide/index.vue')
const taskbook = read('src/pages/teacher/graduation-taskbook/index.vue')
const request = read('src/services/request.js')

test('U8 teacher graduation queues request explicit server pages of 20', () => {
  assert.match(adapter, /const PAGE_SIZE = 20/)
  for (const path of [
    '/mobile/teacher/graduation/midterm/queue',
    '/mobile/teacher/graduation/grade/queue',
    '/mobile/teacher/graduation/taskbooks'
  ]) assert.ok(adapter.includes(path), `missing explicit paged route ${path}`)
  assert.match(adapter, /pageSize=\$\{size\}/)
  assert.ok(!adapter.includes('5000'))
})

test('U8 graduation guide uses server totals and explicit load-more for midterm and grade', () => {
  assert.ok(guide.includes('graduationTeacherPagingApi.midtermQueue'))
  assert.ok(guide.includes('graduationTeacherPagingApi.gradeQueue'))
  assert.ok(guide.includes('rows._pageMeta'))
  assert.ok(guide.includes('midtermTotal'))
  assert.ok(guide.includes('gradeTotal'))
  assert.ok(guide.includes('loadMoreMidterm'))
  assert.ok(guide.includes('loadMoreGrade'))
  assert.ok(guide.includes('midtermHasMore'))
  assert.ok(guide.includes('gradeHasMore'))
  assert.ok(guide.includes('env(safe-area-inset-bottom)'))
})

test('U8 taskbook page exposes real total and append-only server paging', () => {
  assert.ok(taskbook.includes('graduationTeacherPagingApi.taskbooks'))
  assert.ok(taskbook.includes('GRADUATION_TEACHER_PAGE_SIZE'))
  assert.ok(taskbook.includes('this.total = Number'))
  assert.ok(taskbook.includes('this.hasMore = !!'))
  assert.ok(taskbook.includes('loadMore()'))
  assert.ok(taskbook.includes('已加载 {{ list.length }} / {{ total }} 条'))
  assert.ok(taskbook.includes('env(safe-area-inset-bottom)'))
})

test('shared request layer remains current-page only and never auto-collects teacher graduation queues', () => {
  assert.ok(request.includes('移动列表只返回当前服务端页'))
  assert.match(request, /async function collectTeacherGraduationPages[\s\S]*return normalizeTeacherGraduationData\(path, first\)/)
  assert.ok(!request.includes('pageSize=5000'))
})
