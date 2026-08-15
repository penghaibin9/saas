import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const list=fs.readFileSync(new URL('../src/views/ApplicantListView.vue',import.meta.url),'utf8')
const detail=fs.readFileSync(new URL('../src/views/ApplicantDetailView.vue',import.meta.url),'utf8')
const material=fs.readFileSync(new URL('../src/components/applicant/ApplicationMaterialView.vue',import.meta.url),'utf8')
const contact=fs.readFileSync(new URL('../src/components/applicant/ContactRevealButton.vue',import.meta.url),'utf8')
const decision=fs.readFileSync(new URL('../src/components/applicant/DecisionActions.vue',import.meta.url),'utf8')

test('applicant UI reads canonical snapshot material and never depends on the unfrozen detail facade',()=>{
  assert.match(detail,/applicationMaterial/)
  assert.match(detail,/summary:\{type:Object,default:null\}/)
  assert.match(list,/:summary="selectedApplicant"/)
  assert.doesNotMatch(detail,/enterpriseInternshipApi\.application\(/)
  for(const forbidden of ['身份证','家庭联系人','处分','困难认定','心理']) assert.doesNotMatch(detail,new RegExp(forbidden))
  assert.doesNotMatch(detail,/other[_A-Za-z]*volunteer|other[_A-Za-z]*decision/i)
  assert.match(material,/学生自填/)
  assert.match(material,/学校已核验/)
})

test('school verification badge requires explicit canonical evidence and never treats missing as true',()=>{
  assert.match(detail,/const schoolVerified=computed/)
  assert.match(detail,/material\.value\?\.schoolFacts\?\.realName/)
  assert.match(detail,/data\.value\?\.studentVerified===true/)
  assert.match(detail,/v-if="schoolVerified"/)
  assert.doesNotMatch(detail,/studentVerified!==false/)
})

test('contact reveal is fail-closed unless server explicitly returns allowed true',()=>{
  assert.match(contact,/props\.contactPolicy\?\.allowed===true/)
  assert.match(contact,/if\(!allowed\.value\)/)
  assert.match(contact,/:disabled="loading \|\| !allowed"/)
  assert.match(contact,/缺少 allowed=true 时保持禁用/)
  assert.doesNotMatch(contact,/contactPolicy\.allowed===false/)
  assert.doesNotMatch(contact,/student\.phone/)
})

test('enterprise decisions are limited and ACCEPT_INTENT wording keeps school authority',()=>{
  for(const label of ['感兴趣','安排面试','拟接收','不合适']) assert.match(decision,new RegExp(label))
  assert.doesNotMatch(decision,/已录用|APPROVED/)
  assert.match(detail,/等待学校最终确认/)
  assert.match(detail,/本次拟接收已释放/)
})

test('applicant workbench switches to single-detail navigation below 1000px',()=>{
  assert.match(list,/@media\(max-width:999px\)/)
  assert.match(list,/返回候选列表/)
  assert.match(list,/showDetail/)
})
