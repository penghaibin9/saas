import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'

const source = fs.readFileSync(
  new URL('../src/modules/system/views/SystemUserListView.vue', import.meta.url),
  'utf8'
).replace(/\r\n/g, '\n')

test('editing a staff account persists selected roles through the formal assignment endpoint', () => {
  const submit = source.match(/async submitForm\(\)[\s\S]*?\n[ ]{4}\},\n[ ]{4}async openDetail/)[0]
  assert.match(submit, /systemApi\.updateUser\(this\.form\.id, this\.form\.value\)/)
  assert.match(submit, /systemApi\.assignUserRoles\(this\.form\.id, this\.form\.value\.roles \|\| \[\]\)/)
  assert.match(submit, /角色身份保存失败/)
  assert.match(submit, /账号与角色身份已更新，重新登录后生效/)
})

test('role checkboxes are disabled without the dedicated role-assignment permission', () => {
  assert.match(source, /key: 'roles'[\s\S]*?disabled: !this\.can\('assignRole'\)/)
  assert.match(source, /originalRoles: \[\.\.\.\(row\.roles \|\| \[\]\)\]/)
})
