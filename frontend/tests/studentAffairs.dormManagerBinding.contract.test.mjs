import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const source = readFileSync(
  new URL('../src/modules/studentAffairs/views/dorm/DormResourceView.vue', import.meta.url),
  'utf8'
)

test('SA-009 resource creation binds a real DORM_MANAGER from Staff PC', () => {
  assert.match(source, /<AppTeacherPicker[\s\S]*v-model="buildDlg\.managerTeacherKey"/)
  assert.match(source, /:query="\{ roleCode: 'DORM_MANAGER' \}"/)
  assert.match(source, /if \(!d\.managerTeacherKey\) \{ d\.error = '请选择负责宿管'; return \}/)
  assert.match(source, /managerTeacherKey: String\(d\.managerTeacherKey\)/)
})

test('SA-009 manager picker is registered on the resource page', () => {
  assert.match(source, /AppTeacherPicker, AppTextInput/)
  assert.match(source, /AppSelect, AppTeacherPicker, AppTextInput, DataTable/)
})
