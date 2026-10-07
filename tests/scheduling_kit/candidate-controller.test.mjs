import test from 'node:test'
import assert from 'node:assert/strict'
import { createCandidateController } from '../../frontend/src/modules/academicAffairs/optimizer/candidateController.mjs'
const deferred = () => { let resolve,reject; const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject} }
function fixture(override={}) {
 let identity='school-A|teacher-1', writes=[], next=0; const data=new Map()
 const storage={getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)}
 const api={context:async()=>({canGenerate:true,sourceRevision:'x'}),
  enqueue:async(b,body)=>{writes.push(body);return {jobId:'10',batchId:b,version:0,state:'QUEUED'}},
  lookup:async()=>({found:false}),get:async b=>({jobId:'10',batchId:b,version:1,state:'SUCCEEDED'}),
  cancel:async b=>({jobId:'10',batchId:b,version:2,state:'CANCELLED'}),preview:async()=>({rows:[]}),...override}
 const controller=createCandidateController({api,readIdentity:()=>identity,storage,
   digest:async x=>x,randomId:()=>`request-key-${++next}`})
 controller.setScope('20')
 return {controller,storage,data,writes,api,setIdentity:v=>{identity=v},getIdentity:()=>identity}
}
const body={expectedSourceRevision:'x',plan:{version:1},reason:'confirmed input'}

test('apply double click writes once and keeps committed receipt',async()=>{
 const d=deferred();let writes=0
 const f=fixture({apply:()=>{writes++;return d.promise},get:async b=>({jobId:'10',batchId:b,version:3,state:'APPLIED'})})
 f.controller.state.job={jobId:'10',batchId:'20',version:2,state:'SUCCEEDED',canApply:true}
 const first=f.controller.apply(),second=f.controller.apply()
 d.resolve({batchId:'20',status:'DRAFT',writtenItems:4});await Promise.all([first,second])
 assert.equal(writes,1);assert.equal(f.controller.state.application.writtenItems,4)
 assert.equal(f.controller.state.job.state,'APPLIED')
})

test('late application receipt cannot cross school or batch',async()=>{
 const d=deferred(),f=fixture({apply:()=>d.promise})
 f.controller.state.job={jobId:'10',batchId:'20',version:2,state:'SUCCEEDED',canApply:true}
 const first=f.controller.apply();f.setIdentity('school-B');f.controller.setScope('21')
 d.resolve({status:'DRAFT'});await first
 assert.equal(f.controller.state.application,null);assert.equal(f.controller.state.job,null)
})

test('409 application preserves candidate and does not retry automatically',async()=>{
 let writes=0;const f=fixture({apply:async()=>{writes++;throw {httpStatus:409,message:'输入已变化'}}})
 f.controller.state.job={jobId:'10',batchId:'20',version:2,state:'SUCCEEDED',canApply:true}
 await f.controller.apply();assert.equal(writes,1);assert.equal(f.controller.state.job.version,2)
 assert.equal(f.controller.state.error,'输入已变化')
})
test('late context from another identity is discarded',async()=>{
 const d=deferred(),f=fixture({context:()=>d.promise});const pending=f.controller.load()
 f.setIdentity('school-B|teacher-2');f.controller.setScope('20');d.resolve({private:'old'})
 await pending;assert.equal(f.controller.state.context,null)
})
test('a late enqueue acknowledgement cannot populate another scope',async()=>{
 const d=deferred(),f=fixture({enqueue:()=>d.promise});await f.controller.load();const call=f.controller.submit(body)
 await new Promise(r=>setImmediate(r));f.setIdentity('school-B');f.controller.setScope('21')
 d.resolve({jobId:'10',batchId:'20',version:0,state:'QUEUED'});await call
 assert.equal(f.controller.state.job,null);assert.equal(f.controller.state.busy,false)
})
test('unknown result retry uses the SAME idempotency key',async()=>{
 const calls=[],f=fixture({enqueue:async(_b,v)=>{calls.push(v);throw new Error('NETWORK')}})
 await f.controller.load();await f.controller.submit(body);await f.controller.submit(body)
 assert.equal(calls.length,2);assert.equal(calls[0].idempotencyKey,calls[1].idempotencyKey)
 assert.equal(f.controller.state.unknown,true)
})
test('unknown write does not accept altered plan',async()=>{
 const f=fixture({enqueue:async()=>{throw new Error('NETWORK')}});await f.controller.load()
 await f.controller.submit(body);await f.controller.submit({...body,reason:'different'})
 assert.match(f.controller.state.error,/UNRESOLVED_COMMAND_CHANGED_INPUT/)
})
test('storage failure blocks request before network mutation',async()=>{
 const f=fixture();f.storage.setItem=()=>{throw new Error('quota')};await f.controller.load()
 await f.controller.submit(body);assert.equal(f.writes.length,0);assert.equal(f.controller.state.storageBlocked,true)
})
test('403 clears visible candidate data but not command identity',async()=>{
 const f=fixture({get:async()=>{throw {httpStatus:403,message:'denied'}}});await f.controller.load()
 await f.controller.submit(body);await f.controller.refresh()
 assert.equal(f.controller.state.context,null);assert.equal(f.controller.state.job,null)
 assert.equal(f.data.size,1)
})
test('lookup absence does not claim command was never committed',async()=>{
 const f=fixture({enqueue:async()=>{throw new Error('NETWORK')}});await f.controller.load()
 await f.controller.submit(body);await f.controller.recover()
 assert.equal(f.controller.state.unknown,true);assert.match(f.controller.state.error,/NOT_CONFIRMED/)
})
test('known command can be recovered after component reconstruction',async()=>{
 const f=fixture();await f.controller.load();await f.controller.submit(body)
 f.api.lookup=async()=>({found:true,job:{jobId:'10',batchId:'20',version:1,state:'RUNNING'}})
 const restored=createCandidateController({api:f.api,readIdentity:f.getIdentity,storage:f.storage})
 restored.setScope('20');await restored.recover();assert.equal(restored.state.job.jobId,'10')
})
test('double click submits once',async()=>{
 const d=deferred();let count=0;const f=fixture({enqueue:()=>{count++;return d.promise}})
 await f.controller.load();const a=f.controller.submit(body),b=f.controller.submit(body)
 await new Promise(r=>setImmediate(r));d.resolve({jobId:'10',batchId:'20',version:0,state:'QUEUED'})
 await Promise.all([a,b]);assert.equal(count,1)
})
test('preview is discarded after scope change and dispose clears data',async()=>{
 const d=deferred(),f=fixture({preview:()=>d.promise});await f.controller.load();await f.controller.submit(body)
 await f.controller.refresh();const call=f.controller.preview('101','W01');f.controller.setScope('21')
 d.resolve({rows:[{secret:'old'}]});await call;assert.deepEqual(f.controller.state.rows,[])
 f.controller.dispose();assert.equal(await f.controller.load(),null)
})
test('cancel sends exact server version',async()=>{
 let sent;const f=fixture({cancel:async(b,id,v)=>{sent=v;return {jobId:id,batchId:b,version:v+1,state:'CANCELLED'}}})
 await f.controller.load();await f.controller.submit(body);await f.controller.cancel();assert.equal(sent,0)
})
test('malformed or wrong-batch receipt never becomes a valid job',async()=>{
 const f=fixture({enqueue:async()=>({jobId:'10',batchId:'99',version:0,state:'SUCCEEDED'})})
 await f.controller.load();await f.controller.submit(body)
 assert.equal(f.controller.state.job,null);assert.equal(f.controller.state.unknown,true)
})
