import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
const form=fs.readFileSync(new URL('../src/views/PositionFormView.vue',import.meta.url),'utf8')

test('A02 adapter uses V3 frozen enterprise portal routes',()=>{
  for(const route of ['/campaigns','/applications/${id}/material','/applications/${id}/resume-pdf','/evaluation-tasks','/evaluation-tasks/${id}/submit']) assert.match(api,new RegExp(route.replace(/[${}()]/g,'\\$&')))
  assert.doesNotMatch(api,/campaigns\/history/)
  assert.doesNotMatch(api,/\/evaluations/)
})

test('position payload is whitelist-only and follows V3 editable field names',()=>{
  for(const field of ['title','majorRequirement','gradeRequirement','workLocation','workContent','dailyHours','weeklyHours','remunerationType','remunerationAmount','remunerationCycle','salaryRange','accommodationProvided','mealProvided','hazardousFlag','prohibitedReason']) assert.match(api,new RegExp(`'${field}'`))
  for(const forbidden of ['companyId','allocatedCount','rightsStatus','rightsCheckedAt','rightsRuleVersion','riskFlag','riskNote']) assert.doesNotMatch(api,new RegExp(`'${forbidden}'`))
  assert.match(form,/form\.title/)
  assert.match(form,/form\.remunerationAmount/)
})
