import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
const contract=fs.readFileSync(new URL('../src/services/enterpriseContract.js',import.meta.url),'utf8')
const form=fs.readFileSync(new URL('../src/views/PositionFormView.vue',import.meta.url),'utf8')
const material=fs.readFileSync(new URL('../src/components/applicant/ApplicationMaterialView.vue',import.meta.url),'utf8')
const types=fs.readFileSync(new URL('../src/types/enterpriseInternship.d.ts',import.meta.url),'utf8')

test('A02 consumes frozen A01 applicant list, material, contact, decision and withdraw routes with campaign context',()=>{
  assert.match(api,/getSelectedCampaignId/)
  assert.match(api,/function recruitmentParams/)
  assert.match(api,/return \{campaignId\}/)
  assert.match(api,/request\(`\$\{AUTH_ROOT\}\/applications`/)
  assert.match(api,/request\(`\$\{AUTH_ROOT\}\/applications\/\$\{id\}`/)
  assert.match(api,/applications\/\$\{id\}\/contact-view/)
  assert.match(api,/applications\/\$\{id\}\/decision/)
  assert.match(api,/applications\/\$\{id\}\/withdraw-accept/)
  assert.match(api,/normalizeApplicantSummary/)
  assert.match(api,/normalizeMaterial/)
  assert.doesNotMatch(api,/studentNo|materialSnapshotId|studentId/)
  for(const type of ['SKILL_EVIDENCE','CERTIFICATE','PROJECT','PRACTICE','AWARD','PORTFOLIO'])assert.match(api,new RegExp(type))
})

test('remaining unfrozen enterprise facades fail closed locally and never call an invented compatibility root',()=>{
  assert.match(api,/ENTERPRISE_FACADE_UNFROZEN/)
  assert.match(api,/function unavailableFacade/)
  assert.match(api,/该企业协同能力尚未由学校端开放/)
  assert.doesNotMatch(api,/\/enterprise\/internship/)
  for(const facade of ['招聘季列表','企业资料','岗位列表','简历 PDF','实习学生列表','企业评价任务'])assert.match(api,new RegExp(facade))
})

test('canonical nested snapshot renders all public profile item families without exposing raw school identifiers',()=>{
  for(const group of ['skillEvidence','projects','practices','certificates','awards','portfolio'])assert.match(material,new RegExp(group))
  assert.match(material,/snapshotHash/)
  assert.match(material,/ApplicationMaterialSnapshot/)
  assert.doesNotMatch(material,/studentNo|身份证|idCard|phone|email/)
})

test('A01 contact sharing enum follows the current canonical four-mode contract',()=>{
  for(const mode of ['MASKED_ONLY','AFTER_INTERVIEW','AFTER_ACCEPT_INTENT','IMMEDIATE'])assert.match(types,new RegExp(`'${mode}'`))
  for(const legacy of ['NONE','AFTER_SCHOOL_APPROVAL','EXPLICIT'])assert.doesNotMatch(types,new RegExp(`'${legacy}'`))
  assert.match(types,/interface ContactSharingPolicy/)
  assert.match(types,/sharePhone:boolean/)
  assert.match(types,/shareEmail:boolean/)
})

test('position payload is whitelist-only and follows V3 editable field names',()=>{
  for(const field of ['title','majorRequirement','gradeRequirement','workLocation','workContent','dailyHours','weeklyHours','remunerationType','remunerationAmount','remunerationCycle','salaryRange','accommodationProvided','mealProvided','hazardousFlag','prohibitedReason']) assert.match(contract,new RegExp(`'${field}'`))
  for(const forbidden of ['companyId','allocatedCount','rightsStatus','rightsCheckedAt','rightsRuleVersion','riskFlag','riskNote']) assert.doesNotMatch(contract,new RegExp(`'${forbidden}'`))
  assert.match(form,/form\.title/)
  assert.match(form,/form\.remunerationAmount/)
})

test('typed frontend contract separates readable PENDING from enterprise write statuses and keeps effect state independent',()=>{
  for(const status of ['DRAFT','PENDING','PUBLISHED','OFFLINE','SUSPENDED','FULL','RISK','ARCHIVED']) assert.match(types,new RegExp(`'${status}'`))
  for(const role of ['COMPANY_ADMIN','HR','MENTOR']) assert.match(types,new RegExp(`'${role}'`))
  for(const decision of ['PENDING','INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED']) assert.match(types,new RegExp(`'${decision}'`))
  for(const effect of ['ACTIVE','EXPIRED','SUPERSEDED','CONSUMED']) assert.match(types,new RegExp(`'${effect}'`))
  assert.match(types,/EnterpriseDecisionWriteStatus/)
  assert.match(types,/EnterpriseDecisionEffectStatus/)
  assert.doesNotMatch(types,/placementAuthority/i)
})
