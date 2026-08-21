import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('T8 workbench dueSoon executes the server typed action directly', () => {
  const page = read('src/pages/teacher/workbench/index.vue')
  assert.match(page, /import \{ runAction \} from '@\/services\/actionRouter'/)
  assert.match(page, /handleTodo\(t\) \{ return runAction\(t && t\.action, \{ side: 'teacher' \}\) \}/)
  assert.doesNotMatch(page, /handleTodo\(t\) \{ go\('\/pages\/teacher\/todos\/index'\) \}/)
})

test('T8 workbench projection keeps canonical action fields instead of rebuilding a route map', () => {
  const service = read('../backend/app/services/teacher_mobile_workbench_v3_service.py')
  assert.match(service, /client="teacherMini"/)
  assert.match(service, /\*\*item/)
  assert.doesNotMatch(service, /todoType.*path|group.*path/)
  assert.doesNotMatch(service, /get_one\(|get_todo\(/)
})
