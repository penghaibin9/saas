import test from 'node:test'
import assert from 'node:assert/strict'
import { assertEvaluationReturnScope,evaluationReturnPath,evaluationReturnTarget } from '../src/services/evaluationNavigation.js'

const path='/evaluations?tenantCode=synthetic-school&campaignId=9007199254740993&batchId=22&internshipId=33&entry=qr-evaluation'
test('login return target retains exact student, batch and large campaign id',()=>{
  const target=evaluationReturnTarget(path)
  assert.equal(target.query.campaignId,'9007199254740993')
  assert.deepEqual(evaluationReturnTarget(evaluationReturnPath(target)),target)
})
test('only the evaluation route and exact query fields can resume',()=>{
  for(const raw of ['https://other.invalid'+path,'//other.invalid'+path,'/\\other.invalid/evaluations',path+'&redirect=https://other.invalid',path+'&batchId=99',path.replace('/evaluations','/login'),path.replace('internshipId=33','internshipId=0'),path+'#anything',path.replace('entry=qr-evaluation','entry=other')])assert.equal(evaluationReturnTarget(raw),null,raw)
})
test('selected enterprise scope must match authoritative school, batch and capability',()=>{
  const target=evaluationReturnTarget(path),context={campaignId:'9007199254740993',batchId:'22',capabilities:{internshipCollab:true}}
  assert.doesNotThrow(()=>assertEvaluationReturnScope(target,context,'synthetic-school'))
  for(const value of [{...context,batchId:'23'},{...context,campaignId:'1'},{...context,capabilities:{internshipCollab:false}}])assert.throws(()=>assertEvaluationReturnScope(target,value,'synthetic-school'))
  assert.throws(()=>assertEvaluationReturnScope(target,context,'another-school'))
})
