import test from 'node:test'
import assert from 'node:assert/strict'
import { sanitizeCompanyPatch, sanitizePositionPayload } from '../src/services/enterpriseContract.js'

test('company patch strips school-controlled authority fields',()=>{
  const result=sanitizeCompanyPatch({shortName:'中联',shortIntro:'智能制造',website:'https://corp.example',qualificationStatus:'PASSED',coopStatus:'ACTIVE',blacklist:false,accessValidUntil:'2099-01-01',schoolReview:'x'})
  assert.deepEqual(result,{shortName:'中联',shortIntro:'智能制造',website:'https://corp.example'})
})

test('position payload strips company scope, status and school-owned counters/rights',()=>{
  const result=sanitizePositionPayload({title:'机械装配技术实习生',headcount:20,workLocation:'长沙',weeklyHours:40,remunerationAmount:3500,companyId:999,status:'PUBLISHED',allocatedCount:19,rightsStatus:'COMPLIANT',riskFlag:false,schoolReview:'x'})
  assert.deepEqual(result,{title:'机械装配技术实习生',headcount:20,workLocation:'长沙',weeklyHours:40,remunerationAmount:3500})
})
