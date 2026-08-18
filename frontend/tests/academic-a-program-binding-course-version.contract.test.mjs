import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const editor = fs.readFileSync(
  path.join(root, 'src/modules/academicAffairs/views/AaProgramEditorView.vue'),
  'utf8'
)
const api = fs.readFileSync(
  path.join(root, 'src/modules/academicAffairs/api/academic-affairs.api.js'),
  'utf8'
)

test('A-W2 program binding UI exposes optional class override with exact scope query', () => {
  assert.match(editor, /AppClassPicker/)
  assert.match(editor, /majorId: program\.majorId/)
  assert.match(editor, /grade: bindForm\.gradeYear/)
  assert.match(editor, /classStatus: 'NORMAL'/)
  assert.match(editor, /班级特例（可选）/)
  assert.match(editor, /留空=专业年级通用；选择班级=仅该班覆盖/)
})

test('A-W2 program binding passes classId through the mature shared API contract', () => {
  assert.match(
    editor,
    /bindProgramGrade\(this\.programId, this\.bindForm\.gradeYear, classId\)/
  )
  assert.match(api, /bindProgramGrade\(programId, gradeYear, classId\)/)
  assert.match(api, /body: \{ gradeYear, classId \}/)
})

test('A-C2 program course picker makes exact course version visible before locking courseId', () => {
  assert.match(editor, /:remote-search="searchProgramCourses"/)
  assert.match(editor, /status: 'ENABLED'/)
  assert.match(editor, /`v\$\{course\.version\}`/)
  assert.match(editor, /value: String\(course\.courseId\)/)
  assert.match(editor, /course\.courseCode/)
})
