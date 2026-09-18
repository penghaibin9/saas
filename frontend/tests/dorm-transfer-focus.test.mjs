import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

function mount(path, values, id) {
  const source=fs.readFileSync(new URL(path,import.meta.url),'utf8'), imports=[]
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g,(_,names)=>{imports.push(...names.split(',').map(s=>s.trim()));return ''})
    .replace(/import\s+(\w+)\s+from\s+['"][^'"]+['"]/g,(_,name)=>{imports.push(name);return ''}).replace('export default','return')
  const defaults={ currentSessionGeneration:()=>1 }
  const c=new Function(...imports,script)(...imports.map(name=>values[name] ?? defaults[name] ?? {}))
  const vm={...c.data(),...c.methods,$route:{query:{recordId:id}}}
  for(const [key,get] of Object.entries(c.computed||{}))Object.defineProperty(vm,key,{get:()=>get.call(vm)})
  if(!c.computed?.recordId)vm.recordId=id
  return vm
}
const pc='../src/modules/studentAffairs/views/dorm/DormTransferView.vue'
const mobile='../../miniapp/src/pages/teacher/dorm-review/index.vue'

test('mobile completed rectification history is paged and cannot be reviewed again',async()=>{
 let query
 const row={rectificationId:'7',status:'CLOSED',allowedActions:[],rectifyNote:'学生补交说明',recheckNote:'已通过'}
 const vm=mount(mobile,{realRequest:async(path,o)=>{query={path,...o};return {items:[row],total:21}},normalizeError:e=>({text:e.message}),toast:()=>{}},'')
 vm.tab='recheck';vm.recheckStatus='CLOSED';vm.recheckPage=2
 await vm.load()
 assert.deepEqual(query.data,{status:'CLOSED',page:2,pageSize:20})
 assert.equal(vm.rectifications[0].rectifyNote,'学生补交说明');assert.equal(vm.recheckTotal,21)
 await vm.submitRecheck(row,'PASS')
 assert.equal(vm.acting,false)
})

test('PC completed checkout focus bypasses pending and student filters',async()=>{
 let query
 const vm=mount(pc,{readStudentFilter:()=>({}),studentAffairsApi:{listDormCheckouts:async q=>{query=q;return {data:{items:[{requestId:q.recordId,status:'CONFIRMED'}],total:1}}}}},'9007199254740993')
 vm.$route.query.tab='checkout';vm.applyRouteFilters();assert.equal(vm.activeTab,'checkout')
 await vm.load()
 assert.equal(query.recordId,'9007199254740993');assert.equal(query.status,undefined);assert.equal(query.studentId,undefined)
 assert.equal(vm.checkoutItems[0].status,'CONFIRMED')
})

test('mobile same identifier switches between transfer and checkout without stale actions',async()=>{
 const calls=[]
 const vm=mount(mobile,{realRequest:async(path,o)=>{calls.push({path,...o});return {items:[{requestId:o.data.recordId,status:'CONFIRMED'}],total:1}},normalizeError:e=>({text:e.message}),toast:()=>{}},'1')
 vm.actionDlg={visible:true,submit:()=>assert.fail('old transfer approval')}
 await vm.syncFocusHash('#/pages/teacher/dorm-review/index?tab=checkout&recordId=1')
 assert.equal(calls[0].path,'/student-affairs/dorm/checkout-requests')
 assert.deepEqual(calls[0].data,{recordId:'1',page:1,pageSize:1})
 assert.equal(vm.checkouts[0].status,'CONFIRMED');assert.equal(vm.actionDlg.visible,false)
 await vm.syncFocusHash('#/pages/teacher/dorm-review/index?tab=checkout')
 assert.equal(vm.recordId,'');assert.equal(calls[1].data.status,'PENDING')
})

test('mobile checkout loads a bounded queue and confirms the exact version before readback',async()=>{
 const requests=[]
 const row={requestId:'9007199254740993',version:4,studentName:'测试学生',studentNo:'A001',bedLabel:'1栋/101/4床',allowedActions:['CONFIRM'],blockers:[]}
 const vm=mount(mobile,{realRequest:async(path,options)=>{requests.push({path,...options});return options.method==='POST'?{...row,status:'CONFIRMED'}:{items:[],total:0}},normalizeError:e=>({text:e.message}),toast:()=>{}},'')
 vm.tab='checkout';vm.checkoutPage=2
 await vm.load()
 assert.deepEqual(requests[0].data,{status:'PENDING',page:2,pageSize:20})
 vm.confirmCheckout(row)
 assert.equal(requests.length,1)
 await vm.actionDlg.submit()
 assert.equal(requests[1].path,'/student-affairs/dorm/checkout-requests/9007199254740993/confirm')
 assert.deepEqual(requests[1].data,{version:4})
 assert.equal(requests.length,3);assert.match(vm.checkoutReceipt,/已退宿/)
 assert.equal(vm.acting,false)
})

test('mobile checkout blocks missing authority, blockers and repeated actions',()=>{
 const vm=mount(mobile,{toast:()=>{}},'')
 const row={version:1,bedLabel:'101/4床',allowedActions:['CONFIRM'],blockers:[]}
 vm.confirmCheckout({...row,allowedActions:[]});assert.equal(vm.actionDlg.visible,false)
 vm.confirmCheckout({...row,blockers:[{code:'TRANSFER_IN_PROGRESS'}]});assert.equal(vm.actionDlg.visible,false)
 vm.acting=true;vm.confirmCheckout(row);assert.equal(vm.actionDlg.visible,false)
})

test('PC original transfer ignores pending/student filters and preserves bigint ID',async()=>{
 let query
 const vm=mount(pc,{studentAffairsApi:{listDormTransfers:async q=>{query=q;return {data:{items:[{transferId:q.recordId,status:'EXECUTED'}],total:1}}}}},'9007199254740993')
 await vm.load()
 assert.equal(query.recordId,'9007199254740993');assert.equal(query.status,undefined);assert.equal(query.studentId,undefined)
 assert.equal(vm.items[0].status,'EXECUTED')
})
test('PC missing transfer is an explicit error, not another queue',async()=>{
 const vm=mount(pc,{studentAffairsApi:{listDormTransfers:async()=>({data:{items:[],total:0}})}},'999')
 await vm.load();assert.match(vm.errorMessage,/不存在或不在当前权限/)
})
test('mobile focuses completed transfer without loading unrelated inspections',async()=>{
 let request
 const vm=mount(mobile,{realRequest:async(path,options)=>{request={path,...options};return {items:[{transferId:'8',status:'EXECUTED',allowedActions:[]}]}},normalizeError:e=>({text:e.message}),toast:()=>{}},'8')
 await vm.load();assert.equal(request.data.recordId,'8');assert.equal(request.data.status,undefined)
 assert.equal(vm.transfers[0].status,'EXECUTED');assert.equal(vm.can(vm.transfers[0],'APPROVE'),false)
})
test('mobile invalid identifier makes no request and explains the broken link',async()=>{
 const vm=mount(mobile,{realRequest:()=>assert.fail('invalid request'),normalizeError:e=>({text:e.message}),toast:()=>{}},'bad')
 await vm.load();assert.equal(vm.state,'error');assert.match(vm.loadError,/编号无效/)
})
test('mobile discards late original record after switching focus',async()=>{
 let resolve
 const vm=mount(mobile,{realRequest:(_,o)=>o.data.recordId==='1'?new Promise(r=>resolve=r):Promise.resolve({items:[{transferId:'2'}]}),normalizeError:e=>({text:e.message}),toast:()=>{}},'1')
 const old=vm.load();vm.recordId='2';await vm.load();resolve({items:[{transferId:'1'}]});await old
 assert.equal(vm.transfers[0].transferId,'2')
})

test('mobile hash-only navigation replaces the record and drops the previous confirmation',async()=>{
 const ids=[]
 const vm=mount(mobile,{realRequest:async(_,o)=>{ids.push(o.data.recordId);return {items:[{transferId:o.data.recordId}]}},normalizeError:e=>({text:e.message}),toast:()=>{}},'1')
 vm.actionDlg={visible:true,submit:()=>assert.fail('stale approval')}
 vm.transfers=[{transferId:'1'}]
 await vm.syncFocusHash('#/pages/teacher/dorm-review/index?recordId=9007199254740993')
 assert.deepEqual(ids,['9007199254740993'])
 assert.equal(vm.transfers[0].transferId,'9007199254740993')
 assert.equal(vm.actionDlg.visible,false);assert.equal(vm.actionDlg.submit,null)
 await vm.syncFocusHash('#/pages/teacher/dorm-review/index?recordId=9007199254740993')
 await vm.syncFocusHash('#/pages/teacher/workbench/index?recordId=5')
 assert.equal(ids.length,1)
 await vm.syncFocusHash('#/pages/teacher/dorm-review/index?recordId=invalid')
 assert.equal(vm.state,'error');assert.deepEqual(vm.transfers,[]);assert.equal(ids.length,1)
})

test('teacher rectification deep link reads the original inspection instead of overlapping transfer', async()=>{
 const calls=[]
 const vm=mount(mobile,{realRequest:async path=>{calls.push(path);return {rectificationId:'9007199254740993',status:'CLOSED',allowedActions:[]}},normalizeError:e=>({text:e.message}),toast:()=>{}},'1')
 vm.recheckNotes={'1':'old draft'};vm.recheckFiles={'1':{fileId:'1'}}
 await vm.syncFocusHash('#/pages/teacher/dorm-review/index?tab=recheck&recordId=9007199254740993')
 assert.deepEqual(calls,['/mobile/teacher/affairs/dorm/rectifications/9007199254740993'])
 assert.equal(vm.rectifications[0].status,'CLOSED');assert.deepEqual(vm.recheckNotes,{});assert.deepEqual(vm.recheckFiles,{})
 assert.equal(vm.can(vm.rectifications[0],'PASS'),false)
})

test('student rectification focus avoids room picking and rejects mismatched records',async()=>{
 const student='../../miniapp/src/pages/student/affairs/dorm.vue'
 let id
 const vm=mount(student,{createSubmitLock:()=>({}),affairsContractApi:{getMyDormRectification:async value=>{id=value;return {rectificationId:value,status:'RECTIFYING',recheckNote:'补充照片'}}},normalizeError:e=>({text:e.message}),safeToast:()=>{}},'')
 await vm.syncRectificationHash('#/pages/student/affairs/dorm?rectificationId=9007199254740993')
 assert.equal(id,'9007199254740993');assert.equal(vm.state,'ready');assert.equal(vm.rectifications[0].recheckNote,'补充照片');assert.equal(vm.cfg,null)
 await vm.syncRectificationHash('#/pages/student/affairs/dorm?rectificationId=invalid')
 assert.equal(vm.state,'error');assert.deepEqual(vm.rectifications,[]);assert.equal(id,'9007199254740993')
})

test('student focus discards late responses after switching original records',async()=>{
 let finish
 const student='../../miniapp/src/pages/student/affairs/dorm.vue'
 const vm=mount(student,{createSubmitLock:()=>({}),affairsContractApi:{getMyDormRectification:id=>id==='1'?new Promise(r=>finish=r):Promise.resolve({rectificationId:id,status:'CLOSED'})},normalizeError:e=>({text:e.message}),safeToast:()=>{}},'')
 vm.rectificationId='1';const old=vm.load();vm.rectificationId='2';await vm.load();finish({rectificationId:'1'});await old
 assert.equal(vm.rectifications[0].rectificationId,'2')
})

test('room rectification preserves evidence on failure and reuses the submission key',async()=>{
 const requests=[];let fail=true,keys=0
 const vm=mount(mobile,{createClientRequestId:()=>`request-${++keys}`,realRequest:async(path,o)=>{requests.push({path,...o});if(fail)throw new Error('network unavailable');return {status:'WAITING_RECHECK'}},normalizeError:e=>({text:e.message}),toast:()=>{}},'8')
 vm.load=async()=>{};vm.roomRectNotes['8']='宿管清理公共区域完成';vm.roomRectFiles['8']={fileId:'9007199254740993'}
 const row={rectificationId:'8',version:2,allowedActions:['SUBMIT']}
 await vm.submitRoomRectification(row)
 assert.equal(vm.roomRectNotes['8'],'宿管清理公共区域完成');assert.equal(vm.acting,false)
 fail=false;await vm.submitRoomRectification(row)
 assert.equal(requests[0].data.clientRequestId,requests[1].data.clientRequestId)
 assert.deepEqual(requests[1].data.fileIds,['9007199254740993']);assert.equal(requests[1].data.expectedVersion,2)
 assert.equal(vm.roomRectNotes['8'],undefined);assert.equal(vm.roomRectFiles['8'],undefined)
})

test('room rectification only starts and submits with server actions',async()=>{
 const requests=[]
 const vm=mount(mobile,{realRequest:async(path,o)=>{requests.push({path,...o})},normalizeError:e=>({text:e.message}),toast:()=>{}},'8')
 vm.load=async()=>{}
 await vm.startRoomRectification({rectificationId:'8',version:3,allowedActions:['START']})
 assert.equal(requests[0].data.expectedVersion,3)
 await vm.startRoomRectification({rectificationId:'8',version:4,allowedActions:[]})
 await vm.submitRoomRectification({rectificationId:'8',version:4,allowedActions:[]})
 assert.equal(requests.length,1)
})

test('inspection room exposes an identified occupant for high-risk association',async()=>{
 const vm=mount(mobile,{
  createClientRequestId:()=> 'dorm-record-1',
  affairsContractApi:{getDormInspectionBeds:async()=>({items:[
   {bedId:'4',studentId:'9007199254740993',occupantName:'甲一',studentNo:'A001'},
   {bedId:'5',studentId:''}
  ]})},normalizeError:e=>({text:e.message}),toast:()=>{}
 },'')
 await vm.selectRoom({roomId:'1'})
 assert.deepEqual(vm.occupants,[{studentId:'9007199254740993',realName:'甲一',studentNo:'A001'}])
 assert.equal(vm.inspection.clientRequestId,'dorm-record-1')
})
