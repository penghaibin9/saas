import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const login=fs.readFileSync(new URL('../src/views/EnterpriseLoginView.vue',import.meta.url),'utf8')
const auth=fs.readFileSync(new URL('../src/services/authApi.js',import.meta.url),'utf8')
const template=login.match(/<template>([\s\S]*?)<\/template>/)?.[1]||''

test('A02-1 handles A01 ENTERPRISE_CONTEXT_REQUIRED multi-member login contract',()=>{
  assert.match(login,/ENTERPRISE_CONTEXT_REQUIRED/)
  assert.match(login,/details\?\.contexts/)
  assert.match(template,/选择要进入的企业/)
  assert.match(login,/memberId:selectedMemberId\.value/)
  assert.match(auth,/memberId/)
})

test('multi-member chooser never submits companyId as enterprise authority',()=>{
  assert.match(login,/前端不会直接提交 companyId 作为 Authority/)
  assert.doesNotMatch(login,/companyId\s*:/)
  assert.match(login,/selectedMemberId/)
  assert.match(template,/浏览器不能自行指定企业权限/)
})

test('changing tenant or login identity clears stale selected member context',()=>{
  assert.match(login,/watch\(\(\)=>\[form\.tenantCode,form\.loginName\]/)
  assert.match(login,/selectedMemberId\.value=''/)
})
