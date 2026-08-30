import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (relative) => fs.readFileSync(new URL(`../${relative}`, import.meta.url), 'utf8')

test('student topic library exposes search, filters, capacity, visible error and cursor continuation', () => {
  const page = read('src/pages/student/graduation/topics/index.vue')
  const api = read('src/services/realApi.js')
  for (const token of ['topicKeyword', 'topicCategory', 'topicsNextCursor', 'topicsHasMore', 'topicError']) {
    assert.ok(page.includes(token), `missing ${token}`)
  }
  assert.match(page, /余量 \{\{ t\.remaining \}\}\/\{\{ t\.capacity \}\}/)
  assert.match(page, /loadMoreTopics/)
  assert.match(api, /gdTopics = \(batchOrParams/)
  assert.match(api, /URLSearchParams/)
  assert.doesNotMatch(api, /pageSize:\s*500/)
})

test('teacher taskbook never silently converts the issue-student error into an empty form', () => {
  const page = read('src/pages/teacher/graduation-taskbook/index.vue')
  assert.doesNotMatch(page, /getGraduationMyStudents\(\)[\s\S]*?\.catch\(\(\) => \{\}\)/)
  assert.match(page, /指导学生加载失败，请稍后重试/)
})

test('all graduation specialist backend roles survive mobile context mapping with one focused queue', () => {
  const roles = read('src/config/roles.config.js')
  const workbench = read('src/pages/teacher/workbench/index.vue')
  for (const role of [
    'GRADUATION_ADMIN', 'GD_COLLEGE_ADMIN', 'GD_MAJOR_ADMIN', 'GD_MENTOR',
    'GD_REVIEWER', 'GD_DEFENSE_SECRETARY', 'GD_DEFENSE_EXPERT', 'GD_GRADE_ADMIN'
  ]) {
    assert.match(roles, new RegExp(`${role}: ROLE\\.${role === 'GD_MENTOR' ? 'MENTOR' : role}`), `missing backend role mapping ${role}`)
  }
  for (const queue of ['gd-overview', 'gd-peer-review', 'gd-defense', 'gd-grade']) {
    assert.ok(workbench.includes(`${queue}':`) || workbench.includes(`${queue}:`), `missing mobile queue route ${queue}`)
  }
})

test('mobile defense scoring confirms the write by server readback and offers the next student', () => {
  const page = read('src/pages/teacher/defense-score/index.vue')
  for (const token of ['actionReceipt', 'return this.load().then', '服务器最新状态', 'continueNext', 'nextId']) {
    assert.ok(page.includes(token), `missing durable scoring receipt token ${token}`)
  }
})

test('student mobile material center is human-first and topic catalog has truthful retryable empty states', () => {
  const graduation = read('src/pages/student/graduation/index.vue')
  const topics = read('src/pages/student/graduation/topics/index.vue')
  for (const token of ['materialStatusLabel(m)', 'materialScanLabel', '结果待核对', '尚未上传版本']) {
    assert.ok(graduation.includes(token), `missing human material token ${token}`)
  }
  assert.doesNotMatch(graduation, /\{\{\s*m\.materialCode\s*\}\}/)
  assert.doesNotMatch(graduation, /:label="m\.reviewStatus\s*\|\|\s*m\.businessStatus"/)
  for (const token of ['当前没有其他可更换题目', '没有符合搜索条件的可更换题目', 'clearTopicFilters', '清空搜索并刷新']) {
    assert.ok(topics.includes(token), `missing truthful empty-state token ${token}`)
  }
})

test('teacher graduation pages reliably reload when the first batch context becomes ready', () => {
  const context = read('src/components/MobileGraduationBatchContext.vue')
  assert.match(context, /uni\.\$emit\('graduation:teacher-batch-ready'\)/)
  for (const page of [
    'src/pages/teacher/graduation-guide/index.vue',
    'src/pages/teacher/graduation-topics/index.vue',
    'src/pages/teacher/graduation-taskbook/index.vue',
    'src/pages/teacher/defense-score/index.vue'
  ]) {
    const source = read(page)
    assert.match(source, /uni\.\$on\('graduation:teacher-batch-ready'/, `${page} must subscribe`)
    assert.match(source, /uni\.\$off\('graduation:teacher-batch-ready'/, `${page} must clean up`)
  }
})
