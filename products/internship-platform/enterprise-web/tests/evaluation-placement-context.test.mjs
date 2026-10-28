import test from 'node:test'
import assert from 'node:assert/strict'
import { requireDecimalId, freezeEvaluationTarget, assertEvaluationContext, createRequestFence } from '../src/services/evaluationContext.js'

const context=()=>({contextReady:true,contextMode:'COLLABORATION',scopeKey:'tenant/company/member/grant',contextEpoch:1,memberRole:'HR',campaign:{batchId:'9007199254740993'},internshipCollabReady:true})
const item=()=>({internshipId:'9007199254740995',placementSnapshotId:'9007199254740997',evaluationVersion:4})

test('Snowflake IDs stay exact decimal strings and unsafe Numbers fail closed',()=>{
  assert.equal(requireDecimalId('9007199254740993'),'9007199254740993')
  for(const value of [Number('9007199254740993'),'',null,undefined,'0','01','1.1',' 12','1e3','-1','１',true,'12345678901234567890'])assert.throws(()=>requireDecimalId(value))
})
test('form freezes placement, record, batch and RETURNED version',()=>{
  const c=context(),i=item(),target=freezeEvaluationTarget(i,c)
  i.placementSnapshotId='7';i.evaluationVersion=99;c.campaign.batchId='8'
  assert.equal(target.expectedPlacementSnapshotId,'9007199254740997')
  assert.equal(target.expectedVersion,4)
  assert.equal(target.batchId,'9007199254740993')
  assert.ok(Object.isFrozen(target))
  assert.throws(()=>assertEvaluationContext(target,c))
})
test('a new evaluation never invents expectedVersion zero',()=>{
  const i=item();delete i.evaluationVersion
  assert.equal(freezeEvaluationTarget(i,context()).expectedVersion,undefined)
})
for(const [name,change] of [
  ['member',c=>{c.scopeKey='other-member'}],['role',c=>{c.memberRole='MENTOR'}],
  ['reload',c=>{c.contextEpoch=2}],['logout',c=>{c.internshipCollabReady=false}],
  ['batch',c=>{c.campaign.batchId='4'}],['loading',c=>{c.contextReady=false}],
])test(`changed ${name} cannot submit an earlier form`,()=>{
  const c=context(),target=freezeEvaluationTarget(item(),c);change(c)
  assert.throws(()=>assertEvaluationContext(target,c))
})
test('matching context and returned version remain usable',()=>{
  const c=context(),target=freezeEvaluationTarget(item(),c)
  assert.equal(assertEvaluationContext(target,c),target)
})
test('invalid or missing placement/version cannot open a submittable form',()=>{
  for(const value of [undefined,null,'',Number.MAX_SAFE_INTEGER+1]){
    assert.throws(()=>freezeEvaluationTarget({...item(),placementSnapshotId:value},context()))
  }
  for(const version of ['4',-1,1.5,NaN])assert.throws(()=>freezeEvaluationTarget({...item(),evaluationVersion:version},context()))
})
test('late success, rejection and finally cannot replace the latest state',async()=>{
  const fence=createRequestFence();let resolveOld
  const old=new Promise(r=>{resolveOld=r});const currentOld=fence.start()
  let state={items:[],error:'',loading:true}
  const oldTask=(async()=>{try{const data=await old;if(currentOld())state.items=data}catch(e){if(currentOld())state.error=e.message}finally{if(currentOld())state.loading=false}})()
  const currentNew=fence.start();assert.equal(currentNew(),true)
  state={items:['new'],error:'new context error',loading:true};resolveOld(['old']);await oldTask
  assert.deepEqual(state,{items:['new'],error:'new context error',loading:true})
})
test('late rejected request preserves current error and spinner',async()=>{
  const fence=createRequestFence();let rejectOld
  const old=new Promise((_r,j)=>{rejectOld=j});const oldCurrent=fence.start()
  let error='current',loading=true
  const task=old.catch(e=>{if(oldCurrent())error=e.message}).finally(()=>{if(oldCurrent())loading=false})
  fence.start();rejectOld(new Error('stale'));await task
  assert.equal(error,'current');assert.equal(loading,true)
})
test('invalidation and unmount dispose outstanding work',()=>{
  const fence=createRequestFence(),a=fence.start();fence.invalidate();assert.equal(a(),false)
  const b=fence.start();fence.dispose();assert.equal(b(),false);assert.equal(fence.start()(),false)
})
