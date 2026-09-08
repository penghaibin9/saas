import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const source=fs.readFileSync(new URL('../src/views/affairs/AffairsFourEndView.vue',import.meta.url),'utf8')
const fn=source.match(/async function submitDormRectification\(item\) \{[\s\S]*?\n\}/)[0]
test('rectification retry reuses its id and a changed payload starts a new request',async()=>{
 const notes={7:'宿舍卫生已经整改完成'},files={7:{fileId:'12'}},requests={},sent=[]
 let serial=0,success=false
 const submit=new Function('rectNotes','rectFiles','rectRequests','validReason','ui','clientRequestId','run','affairsFourEndApi',`${fn}; return submitDormRectification`)(notes,files,requests,()=>true,{notify(){}},()=>`req-${++serial}`,async task=>{await task();return {ok:success}},{submitDormRectification:async(id,payload)=>sent.push(payload)})
 await submit({rectificationId:7,version:2})
 await submit({rectificationId:7,version:2})
 assert.equal(sent[0].clientRequestId,sent[1].clientRequestId)
 assert.equal(files[7].fileId,'12')
 notes[7]='重新补充整改说明和证据'
 success=true
 await submit({rectificationId:7,version:2})
 assert.notEqual(sent[2].clientRequestId,sent[1].clientRequestId)
 assert.equal(requests[7],undefined)
 assert.equal(files[7],undefined)
})
