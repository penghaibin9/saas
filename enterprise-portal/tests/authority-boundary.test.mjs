import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
const layout=fs.readFileSync(new URL('../src/layouts/EnterprisePortalLayout.vue',import.meta.url),'utf8')
const form=fs.readFileSync(new URL('../src/views/PositionFormView.vue',import.meta.url),'utf8')

test('enterprise adapter cannot choose company scope or publish/approve/assign',()=>{
  assert.equal(/companyId\s*[,)]/.test(api),false)
  assert.equal(/\/publish/.test(api),false)
  assert.equal(/APPROVED/.test(api),false)
  assert.equal(/assign_position|assignPosition/.test(api),false)
  for(const status of ['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED']) assert.match(api,new RegExp(status))
})

test('portal navigation stays enterprise-only and fixed to six modules',()=>{
  for(const label of ['首页','企业资料','我的岗位','报名学生','实习学生','评价任务']) assert.match(layout,new RegExp(label))
  for(const forbidden of ['系统管理','学籍管理','学校管理后台']) assert.doesNotMatch(layout,new RegExp(forbidden))
})

test('position form exposes draft and school-review submission but no direct publish',()=>{
  assert.match(form,/保存草稿/)
  assert.match(form,/提交学校审核/)
  assert.doesNotMatch(form,/直接发布/)
})
