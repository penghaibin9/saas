import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import assert from 'node:assert/strict'

const root = path.resolve(import.meta.dirname, '..')
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8')

test('teacher MyStudents V3 uses dedicated strict real network client', () => {
  const api = read('src/services/teacherStudentV3Api.js')
  assert.match(api, /realRequest\(`\/teacher-mobile\/students\?\$\{buildQuery\(params\)\}`\)/)
  assert.match(api, /classId=/)
  assert.match(api, /keyword=/)
  assert.match(api, /cursor=/)
  assert.match(api, /pageSize=/)
  assert.doesNotMatch(api, /mockRequest|realFirst|allowMockFallback/)
})

test('teacher MyStudents V3 page consumes cursor and server search', () => {
  const page = read('src/pages/teacher/my-students/index.vue')
  assert.match(page, /teacherStudentV3Api/)
  assert.doesNotMatch(page, /teacherApi\.getMyStudents/)
  assert.match(page, /onReachBottom\(\)/)
  assert.match(page, /nextCursor/)
  assert.match(page, /hasMore/)
  assert.match(page, /keywordInput/)
  assert.match(page, /keyword:\s*this\.keyword/)
  assert.match(page, /cursor:\s*append \? this\.nextCursor : ''/)
  assert.match(page, /pageSize:\s*TEACHER_STUDENT_PAGE_SIZE/)
})

test('teacher MyStudents V3 retains rows when load-more network fails', () => {
  const page = read('src/pages/teacher/my-students/index.vue')
  const catchBlock = page.slice(page.indexOf('} catch (error) {'), page.indexOf('} finally {'))
  assert.match(catchBlock, /if \(append\)/)
  assert.match(catchBlock, /toastError\(error\)/)
  assert.match(catchBlock, /this\.state = 'error'/)
  assert.doesNotMatch(catchBlock, /this\.items = \[\]/)
})

test('teacher MyStudents V3 classId is only a narrowing request parameter', () => {
  const page = read('src/pages/teacher/my-students/index.vue')
  const api = read('src/services/teacherStudentV3Api.js')
  assert.match(page, /classId:\s*this\.classId/)
  assert.match(api, /encodeURIComponent\(normalizedClassId\)/)
  // Permission decisions stay server-side; the client does not carry a local class/student allow-list.
  assert.doesNotMatch(page, /allowedClass|allowedStudent|scopeMatch|studentIds/)
  assert.doesNotMatch(api, /allowedClass|allowedStudent|scopeMatch|studentIds/)
})
