import assert from 'node:assert/strict'
import test from 'node:test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

test('teacher academic tasks page on the server and resolve a workbench taskId exactly', () => {
  const page = read('src/pages/teacher/academic-task/index.vue')
  const api = read('src/services/realApi.js')

  assert.match(page, /page: this\.targetTaskId \? 1 : requestedPage/)
  assert.match(page, /pageSize: this\.queuePageSize/)
  assert.match(page, /taskId: this\.targetTaskId \|\| undefined/)
  assert.match(page, /queueHasMore/)
  assert.doesNotMatch(page, /tasks\.slice\(this\.queuePage/)
  assert.match(api, /teacherAcademicMyTasks = \(params = \{\}\)/)
  assert.match(api, /typeof params === 'string' \? \{ status: params \} : \(params \|\| \{\}\)/)
})
