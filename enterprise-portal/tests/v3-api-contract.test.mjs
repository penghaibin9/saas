import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
const contract=fs.readFileSync(new URL('../src/services/enterpriseContract.js',import.meta.url),'utf8')
const form=fs.readFileSync(new URL('../src/views/PositionFormView.vue',import.meta.url),'utf8')
const material=fs.readFileSync(new URL('../src/components/applicant/ApplicationMaterialView.vue',import.meta.url),'utf8')
const types=fs.readFileSync(new URL('../src/types/enterpriseInternship.d.ts',import.meta.url),'utf8')

test('A02 consumes frozen A01 applicant material and decision routes with campaign context',()=>{
  assert.match(api,/getSelectedCampaignId/)
  assert.match(api,/function recruitmentParams/)
  assert.match(api,/return \{campaignId\}/)
  assert.match(api,/request\(`\$\{AUTH_ROOT\}\/applications\/\$\{id\}`/)
  assert.match(api,/request\(`\$\{AUTH_ROOT\}\/applications\/\$\{id\}\/decision`/)
  assert.doesNotMatch(api,/applications\/\$\{id\}\/material/)
  assert.match(api,/normalizeMaterial/)
  for(const type of ['SKILL_EVIDENCE','CERTIFICATE','PROJECT','PRACTICE','AWARD','PORTFOLIO'])assert.match(api,new RegExp(type))
})

test('unfrozen enterprise facades remain behind the compatibility root without inventing A01 routes',()=>{
  for(const route of ['/campaigns','/applications/${id}/resume-pdf','/evaluation-tasks','/evaluation-tasks/${id}/submit']) assert.match(api,new RegExp(route.replace(/[${}()]/g,'\\$&')))
  assert.doesNotMatch(api,/campaigns\/history/)
  assert.doesNotMatch(api,/\/evaluations/)
})

test('canonical nested snapshot renders all public profile item families without exposing raw school identifiers',()=>{
  for(const group of ['skillEvidence','projects','practices','certificates','awards','portfolio'])assert.match(material,new RegExp(group))
  assert.match(material,/material\.snapshotHash/)
  assert.match(material,/ApplicationMaterialSnapshot/)
  assert.doesNotMatch(material,/studentNo|身份证|idCard|phone|email/)
})

test('position payload is whitelist-only and follows V3 editable field names',()=>{
  for(const field of ['title','majorRequirement','gradeRequirement','workLocation','workContent','dailyHours','weeklyHours','remunerationType','remunerationAmount','remunerationCycle','salaryRange','accommodationProvided','mealProvided','hazardousFlag','prohibitedReason']) assert.match(contract,new RegExp(`'${field}'`))
  for(const forbidden of ['companyId','allocatedCount','rightsStatus','rightsCheckedAt','rightsRuleVersion','riskFlag','riskNote']) assert.doesNotMatch(contract,new RegExp(`'${forbidden}'`))
  assert.match(form,/form\.title/)
  assert.match(form,/form\.remunerationAmount/)
})

test('typed frontend contract includes canonical decision status and independent effect state without adding placement authority',()=>{
  for(const status of ['DRAFT','PENDING','PUBLISHED','OFFLINE','SUSPENDED','FULL','RISK','ARCHIVED']) assert.match(types,new RegExp(`'${status}'`))
  for(const role of ['COMPANY_ADMIN','HR','MENTOR']) assert.match(types,new RegExp(`'${role}'`))
  for(const decision of ['INTERESTED','INTERVIEW','ACCEPT_INTENT','REJECTED']) assert.match(types,new RegExp(`'${decision}'`))
  for(const effect of ['ACTIVE','EXPIRED','SUPERSEDED','CONSUMED']) assert.match(types,new RegExp(`'${effect}'`))
  assert.match(types,/EnterpriseDecisionEffectStatus/)
  assert.match(types,/decisionEffectStatus/)
  assert.match(types,/acceptIntentReleased/)
})
