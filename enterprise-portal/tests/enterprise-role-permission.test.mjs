import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read=(path)=>fs.readFileSync(new URL(path,import.meta.url),'utf8')
const store=read('../src/stores/enterpriseContext.js')
const layout=read('../src/layouts/EnterprisePortalLayout.vue')
const applicants=read('../src/views/ApplicantListView.vue')

test('A02 mirrors A01 applicant role permission contract for UX without replacing server authority',()=>{
  assert.match(store,/APPLICATION_ROLES = new Set\(\['COMPANY_ADMIN','HR'\]\)/)
  assert.match(store,/applicationViewAllowed/)
  assert.match(store,/applicationReviewAllowed/)
  assert.match(store,/Every backend request still revalidates/i)
  assert.match(layout,/applicationPermission:true/)
  assert.match(layout,/aria-disabled="true"/)
  assert.match(layout,/仅企业管理员或 HR 可处理报名学生/)
})

test('MENTOR applicant UI fails closed before canonical applicant calls and no longer touches an unfrozen position facade',()=>{
  const guard=applicants.indexOf("if(!context.contextReady||!context.applicationViewAllowed)")
  const listCall=applicants.indexOf('enterpriseInternshipApi.applications')
  assert.ok(guard>=0,'applicant role guard is required')
  assert.ok(listCall>guard,'canonical applicant list call must be behind the role guard')
  assert.doesNotMatch(applicants,/enterpriseInternshipApi\.positions/)
  assert.match(applicants,/roleDenied=computed/)
  assert.match(applicants,/当前成员角色不能处理报名学生/)
  assert.match(applicants,/企业导师可参与后续实习协同，但不能查看学生投递材料/)
})
