import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const read = (path) => fs.readFileSync(new URL(`../../${path}`, import.meta.url), 'utf8')

test('teacher affairs page renders real todo rows before category cards', () => {
  const source = read('miniapp/src/pages/teacher/affairs/index.vue')
  assert.match(source, /待我处理/)
  assert.match(source, /v-for="item in todoItems"/)
  assert.match(source, /item\.studentName/)
  assert.match(source, /item\.recordId/)
  assert.match(source, /item\.overdue/)
  assert.match(source, /openTodo\(item\)/)
  assert.match(source, /recordId=\$\{encodeURIComponent\(params\.recordId\)\}/)
  assert.match(source, /todoId=\$\{encodeURIComponent\(params\.todoId\)\}/)
})

test('teacher affairs page keeps category navigation and no mock fallback', () => {
  const source = read('miniapp/src/pages/teacher/affairs/index.vue')
  assert.match(source, /按业务分类/)
  assert.match(source, /teacherApi\.getAffairs\(1,\s*20\)/)
  assert.match(source, /teacherApi\.getAffairs\(next,\s*20\)/)
  assert.match(source, /todoHasMore/)
  assert.match(source, /继续加载待办/)
  assert.doesNotMatch(source, /mockRequest/)
})
