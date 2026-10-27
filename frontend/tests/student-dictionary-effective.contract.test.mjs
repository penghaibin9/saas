import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const api = fs.readFileSync(new URL('../src/modules/student/api/student.api.js', import.meta.url), 'utf8')

test('student center reads school display vocabulary and keeps a local fallback', () => {
  assert.match(api, /request\('\/school\/dictionaries\/effective',\s*\{ params: \{ consumer: 'studentCenter' \} \}\)\.catch\(\(\) => null\)/)
  assert.match(api, /statusOptions:\s*\{ \.\.\.STATUS_OPTIONS, \.\.\.\(dictionaryResult\?\.statusOptions \|\| \{\}\) \}/)
})

test('dictionary failure cannot block the student center permission context', () => {
  assert.match(api, /dictionaryResult\]\s*=\s*await Promise\.all/)
  assert.match(api, /request\('\/rbac\/current-context'\)/)
})

test('dictionary read failure explicitly marks fallback while keeping verified permission context', async () => {
  const env={request:async path=>{
    if(path==='/school/dictionaries/effective')throw Error('字典读取失败')
    if(path==='/rbac/current-context')return {permissionPatterns:['student.profile.view'],currentRole:{roleCode:'TEACHER'}}
    return {}
  }}
  vm.runInNewContext(api.replace(/^import .*$/gm,'').replace('export const studentApi =','globalThis.studentApi =').replace('export default studentApi',''),env)
  const result=await env.studentApi.getContext()
  assert.equal(result.code,0)
  assert.equal(result.data.dictionaryUnavailable,true)
  assert.equal(result.data.currentRole.roleCode,'TEACHER')
  assert.ok(result.data.statusOptions.studentStatus.length)
  const layout=fs.readFileSync(new URL('../src/views/admin/student/AdminStudentLayout.vue',import.meta.url),'utf8')
  assert.match(layout,/ctx\?\.dictionaryUnavailable/)
  assert.match(layout,/当前暂用业务内置名称/)
})
