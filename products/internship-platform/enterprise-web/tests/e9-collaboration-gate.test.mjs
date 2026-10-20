import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const store=fs.readFileSync(new URL('../src/stores/enterpriseContext.js',import.meta.url),'utf8')
const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
const students=fs.readFileSync(new URL('../src/views/InternshipStudentListView.vue',import.meta.url),'utf8')
const evaluations=fs.readFileSync(new URL('../src/views/EvaluationTaskListView.vue',import.meta.url),'utf8')

test('E9 collaboration context is batch-scoped and recruitment APIs fail locally in collaboration-only mode',()=>{
  assert.match(api,/collaborationContext:\(batchId\)=>request\(`\$\{AUTH_ROOT\}\/collaboration-context`/)
  assert.match(api,/function requireRecruitmentAccess/)
  assert.match(api,/activeContextMode!=='RECRUITMENT'/)
  assert.match(api,/ENTERPRISE_RECRUITMENT_CONTEXT_UNAVAILABLE/)
  assert.match(api,/dashboard:\(\)=>request\(`\$\{AUTH_ROOT\}\/dashboard`,\{params:requireRecruitmentAccess\(\)\}\)/)
  assert.match(api,/positions:[\s\S]*requireRecruitmentAccess\(\)/)
  assert.match(api,/applications:[\s\S]*requireRecruitmentAccess\(\)/)
})

test('context load uses campaign batch then falls back from recruitment to independent collaboration context',()=>{
  const campaignsAt=store.indexOf('const campaigns=await enterpriseInternshipApi.campaigns()')
  const recruitmentAt=store.indexOf('authContext=await enterpriseInternshipApi.context(campaignId)')
  const fallbackAt=store.indexOf('authContext=await enterpriseInternshipApi.collaborationContext(selectedBatchId)')
  assert.ok(campaignsAt>=0&&recruitmentAt>campaignsAt)
  assert.ok(fallbackAt>recruitmentAt)
  assert.match(store,/mode='RECRUITMENT'/)
  assert.match(store,/mode='COLLABORATION'/)
  assert.match(store,/recruitmentContextReady:\(state\)=>state\.contextReady&&state\.contextMode==='RECRUITMENT'/)
})

test('collaboration fallback can never restore recruitment write or applicant access',()=>{
  assert.match(store,/serverCapabilities=\{recruitmentWrite:authContext\?\.capabilities\?\.recruitmentWrite===true/)
  assert.match(store,/recruitmentWrite:mode==='RECRUITMENT'&&serverCapabilities\.recruitmentWrite/)
  assert.match(store,/applicationViewAllowed:\(state\)=>state\.contextReady&&state\.contextMode==='RECRUITMENT'/)
  assert.match(store,/Every backend request still revalidates/)
  assert.doesNotMatch(store,/internshipCollab\s*:\s*true/)
})

test('E9 pages remain 0-network when collaboration capability itself is unavailable',()=>{
  for(const page of [students,evaluations]){
    const guard=page.indexOf('if(!collabReady.value)')
    const call=page.indexOf('enterpriseInternshipApi.',guard)
    assert.ok(guard>=0)
    assert.ok(call>guard)
  }
})
