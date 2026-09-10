import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as results from '../src/modules/academicAffairs/components/parallel-a/resultState.js'
import * as tasks from '../src/modules/academicAffairs/components/parallel-a/taskFacts.js'
import * as status from '../src/modules/academicAffairs/constants/teaching.js'

function instance(file, deps = {}, options = {}) {
  const source = fs.readFileSync(new URL('../src/modules/academicAffairs/views/' + file + '.vue', import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const imports = [...script.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm)]
  const names = imports.flatMap(([,binding]) => binding.trim().startsWith('{') ? binding.replace(/[{}]/g,'').split(',').map(x=>x.trim()).filter(Boolean) : [binding.trim()])
  const defaults = { ...status, ...results, ...tasks, getPermissionPatterns:()=>['*'], matchPermission:(patterns,key)=>patterns.includes('*')||patterns.includes(key), toast:{success(){},error(){}}, ...deps }
  const clean = script.replace(/^import\s+[\s\S]*?\s+from\s+['"][^'"]+['"]\s*$/gm,'').replace('export default','return')
  const component = new Function(...names, clean)(...names.map(name=>defaults[name] ?? {}))
  const vm = { ...component.data(), selectedBatchId:'', ctx:{permissionPatterns:['*']}, $route:{params:{batchId:'a'},query:{teachingClassId:'a'},fullPath:'/admin/academic-affairs/teaching-tasks/a'}, $router:{push(){},replace:async()=>{}}, ...options }
  Object.entries(component.methods||{}).forEach(([name,method])=>vm[name]=method.bind(vm))
  Object.entries(component.computed||{}).forEach(([name,get])=>Object.defineProperty(vm,name,{get:()=>get.call(vm)}))
  return vm
}
const ok=data=>({code:0,data})
const page=list=>ok({list,total:list.length})
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}

test('T08 identity switch during batch precheck prevents command under the new identity',async()=>{
  const response=deferred();let writes=0
  const vm=instance('AaTaskDetailView',{teachingTaskWorkbenchApi:{getBatch:()=>response.promise},academicAffairsApi:{collegeConfirmTaskBatch:async()=>{writes++}}})
  vm.loading=false;vm.workbench={actions:{canCollegeConfirm:true}};const action=vm.collegeConfirm();vm.ctx={permissionPatterns:['*']};response.resolve(ok({actions:{canCollegeConfirm:true}}));await action;assert.equal(writes,0)
})

test('T08 old identity teacher response does not trigger a new identity read or receipt',async()=>{
  const response=deferred(), started=deferred();let reads=0
  const row={taskId:'x',status:'ASSIGNED'}
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{teacherActTask:()=>{started.resolve();return response.promise},listAllTasks:async()=>{reads++;return page([row])}}})
  vm.loading=false;vm.rows=[row];vm.openConfirm(row);const action=vm.doConfirm();await started.promise;vm.ctx={};response.resolve(ok({}));await action;assert.equal(reads,1);assert.equal(vm.receipt.pending,true)
})

test('T08 unknown college confirmation queries formal batch without replaying the command', async () => {
  let writes=0, reads=0
  const vm=instance('AaTaskDetailView', {teachingTaskWorkbenchApi:{getBatch:async()=>{reads++;return ok({batchId:'a',status:'DRAFT',actions:{canCollegeConfirm:true}})}},academicAffairsApi:{collegeConfirmTaskBatch:async()=>{writes++;return {code:503001,message:'response lost'}},getBatchTasks:async()=>page([{taskId:'x',status:'TEACHER_CONFIRMED'}])}})
  vm.loading=false;vm.workbench={batchId:'a',status:'DRAFT',actions:{canCollegeConfirm:true}}
  await vm.collegeConfirm();await vm.collegeConfirm()
  assert.equal(writes,1);assert.equal(reads,3);assert.ok(vm.pendingResult);assert.equal(vm.receipt.pending,true)
})

test('T08 lost batch response keeps a query-only lock even when current facts match', async () => {
  let writes=0
  const vm=instance('AaTaskDetailView', {teachingTaskWorkbenchApi:{getBatch:async()=>ok({batchId:'a',status:writes?'COLLEGE_CONFIRMED':'DRAFT',actions:{canCollegeConfirm:!writes}})},academicAffairsApi:{collegeConfirmTaskBatch:async()=>{writes++;throw new Error('network lost')},getBatchTasks:async()=>page([{taskId:'x',status:'TEACHER_CONFIRMED'}])}})
  vm.loading=false;vm.workbench={batchId:'a',status:'DRAFT',actions:{canCollegeConfirm:true}}
  await vm.collegeConfirm();await vm.collegeConfirm()
  assert.equal(writes,1);assert.ok(vm.pendingResult);assert.equal(vm.receipt.pending,true);assert.equal(vm.workbench.status,'COLLEGE_CONFIRMED');assert.match(vm.receipt.next,/不能认定是本次/)
})

test('T08 conflicting academic review retains reason and invalidates the original confirmation', async () => {
  let writes=0,reads=0
  const vm=instance('AaTaskDetailView', {teachingTaskWorkbenchApi:{getBatch:async()=>{reads++;return ok({batchId:'a',status:'COLLEGE_CONFIRMED',actions:{canAcademicReview:true}})}},academicAffairsApi:{reviewTaskBatch:async()=>{writes++;return {code:409001,message:'batch changed'}},getBatchTasks:async()=>page([{taskId:'x',status:'TEACHER_CONFIRMED'}])}})
  vm.loading=false;vm.workbench={batchId:'a',status:'COLLEGE_CONFIRMED',actions:{canAcademicReview:true}}
  vm.openReturn();vm.review.reason='需要重新核对授课范围';await vm.doReview();await vm.doReview()
  assert.equal(writes,1);assert.equal(reads,2);assert.equal(vm.review.reason,'需要重新核对授课范围');assert.equal(vm.review.invalid,true);assert.equal(vm.pendingResult,null)
  vm.openReturn();assert.equal(vm.review.reason,'需要重新核对授课范围');assert.equal(vm.review.invalid,false)
})

test('T08 denied batch command erases pending result, rows and review notes without fallback reads', async () => {
  let reads=0
  const vm=instance('AaTaskDetailView', {teachingTaskWorkbenchApi:{getBatch:async()=>{reads++;return ok({batchId:'a',actions:{canAcademicReview:true}})}},academicAffairsApi:{reviewTaskBatch:async()=>({status:403,message:'scope revoked'})}})
  vm.loading=false;vm.workbench={batchId:'a',actions:{canAcademicReview:true}};vm.rows=[{taskId:'x'}]
  vm.openReturn();vm.review.reason='请重新核对教师范围';await vm.doReview()
  assert.equal(reads,1);assert.equal(vm.pendingResult,null);assert.deepEqual(vm.rows,[]);assert.equal(vm.review.reason,'');assert.equal(vm.review.visible,false)
})

test('T08 a different formal batch never authorizes the displayed batch command', async () => {
  let writes=0
  const vm=instance('AaTaskDetailView', {teachingTaskWorkbenchApi:{getBatch:async()=>ok({batchId:'other',actions:{canCollegeConfirm:true}})},academicAffairsApi:{collegeConfirmTaskBatch:async()=>{writes++}}})
  vm.loading=false;vm.workbench={batchId:'a',actions:{canCollegeConfirm:true}};await vm.collegeConfirm()
  assert.equal(writes,0);assert.equal(vm.pendingResult,null);assert.match(vm.error,/不同对象/)
})

test('T08 thrown review conflict rereads facts and does not leave an unknown command lock', async () => {
  let writes=0
  const vm=instance('AaTaskDetailView', {teachingTaskWorkbenchApi:{getBatch:async()=>ok({batchId:'a',status:'COLLEGE_CONFIRMED',actions:{canAcademicReview:true}})},academicAffairsApi:{reviewTaskBatch:async()=>{writes++;throw {status:409,message:'scope changed'}},getBatchTasks:async()=>page([{taskId:'x'}])}})
  vm.loading=false;vm.workbench={batchId:'a',actions:{canAcademicReview:true}};vm.openReturn();vm.review.reason='保留原来的终审意见';await vm.doReview();await vm.doReview()
  assert.equal(writes,1);assert.equal(vm.pendingResult,null);assert.equal(vm.review.reason,'保留原来的终审意见');assert.equal(vm.review.invalid,true)
})

test('T08 all task pages are read before totals or readback decisions',async()=>{
  const calls=[]
  const result=await tasks.readTaskPages(async p=>{calls.push(p.page);return ok({list:[{taskId:String(p.page)}],total:3})})
  assert.deepEqual(calls,[1,2,3]);assert.equal(result.data.list.length,3)
})
test('T08 truncated or duplicate pages fail explicitly rather than becoming a complete list',async()=>{
  const result=await tasks.readTaskPages(async p=>ok({list:p.page===1?[{taskId:'1'}]:[],total:3}))
  assert.equal(result.code,409001)
  const duplicate=await tasks.readTaskPages(async()=>ok({list:[{taskId:'1'}],total:3}))
  assert.equal(duplicate.code,409001)
})
test('T08 teacher confirmation reads exact task state before confirming receipt',async()=>{
  const calls=[]
  const row={taskId:'x',status:'ASSIGNED',courseName:'课程'};let assigned=true
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{teacherActTask:async id=>{calls.push('POST:'+id);assigned=false;return ok({})},listAllTasks:async p=>{assert.equal(p.mine,true);calls.push('GET');return page([{...row,status:assigned?'ASSIGNED':'TEACHER_CONFIRMED'}])}}})
  vm.loading=false;vm.rows=[row];vm.openConfirm(row);await vm.doConfirm()
  assert.deepEqual(calls,['GET','POST:x','GET']);assert.equal(vm.receipt.status,'教师已确认');assert.equal(vm.receipt.pending,false)
})
test('T08 unchanged teacher task after successful command remains pending',async()=>{
  const row={taskId:'x',status:'ASSIGNED'}
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{teacherActTask:async()=>ok({}),listAllTasks:async()=>page([row])}})
  vm.loading=false;vm.rows=[row];vm.openConfirm(row);await vm.doConfirm();assert.equal(vm.receipt.pending,true)
})
test('T08 teacher denial clears dialogs and prior rows',async()=>{
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{listAllTasks:async()=>page([{taskId:'x',status:'ASSIGNED'}]),teacherActTask:async()=>({status:403,message:'归属已变化'})}})
  vm.loading=false;vm.rows=[{taskId:'x',status:'ASSIGNED'}];vm.openConfirm(vm.rows[0]);await vm.doConfirm()
  assert.deepEqual(vm.rows,[]);assert.equal(vm.confirmDialog.visible,false);assert.equal(vm.receipt,null)
})
test('T08 teacher conflict preserves rejection reason',async()=>{
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{listAllTasks:async()=>page([{taskId:'x',status:'ASSIGNED'}]),teacherActTask:async()=>({code:409001,message:'已改派'})}})
  vm.loading=false;vm.rows=[{taskId:'x',status:'ASSIGNED'}];vm.openReject(vm.rows[0]);vm.rejectDialog.reason='本周安排有冲突';await vm.doReject()
  assert.equal(vm.rejectDialog.reason,'本周安排有冲突');assert.equal(vm.rejectDialog.visible,true);assert.equal(vm.receipt.pending,true)
})
test('T08 old teacher list response never replaces current read',async()=>{
  const first=deferred();let n=0
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{listAllTasks:()=>++n===1?first.promise:Promise.resolve(page([{taskId:'new'}]))}})
  const request=vm.load();await vm.load();first.resolve(page([{taskId:'old'}]));await request;assert.equal(vm.rows[0].taskId,'new')
})

test('T08 frozen teacher evidence never submits changed hours from a later list',async()=>{
  const old={taskId:'x',status:'ASSIGNED',weeklyHours:2,teacherKey:'t1'};let writes=0
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{listAllTasks:async()=>page([{...old,weeklyHours:8}]),teacherActTask:async()=>{writes++;return ok({})}}})
  vm.loading=false;vm.rows=[old];vm.openConfirm(old);await vm.load();await vm.doConfirm()
  assert.equal(vm.confirmDialog.row.weeklyHours,2);assert.equal(vm.rows[0].weeklyHours,8);assert.equal(writes,0);assert.equal(vm.confirmDialog.invalid,true)
})

for(const code of [503001,409001]) test(`T08 ${code} cannot replay the original rejection and always rereads facts`,async()=>{
  let writes=0,reads=0;const row={taskId:'x',status:'ASSIGNED',weeklyHours:2}
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{teacherActTask:async()=>{writes++;return {code,message:'办理异常'}},listAllTasks:async()=>{reads++;return page([row])}}})
  vm.loading=false;vm.rows=[row];vm.openReject(row);vm.rejectDialog.reason='授课安排存在冲突';await vm.doReject();await vm.doReject()
  assert.equal(writes,1);assert.ok(reads>=2);assert.equal(vm.rejectDialog.reason,'授课安排存在冲突');assert.equal(vm.rejectDialog.invalid,true)
  assert.equal(Boolean(vm.pendingCommand),code===503001)
})

test('T08 after conflict only explicitly reopening fresh task can authorize a new decision',async()=>{
  let writes=0;const row={taskId:'x',status:'ASSIGNED',weeklyHours:2}
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{teacherActTask:async()=>{writes++;return {code:409001,message:'状态已变化'}},listAllTasks:async()=>page([row])}})
  vm.loading=false;vm.rows=[row];vm.openReject(row);vm.rejectDialog.reason='授课安排存在冲突';await vm.doReject();await vm.doReject();assert.equal(writes,1)
  vm.openReject(vm.rows[0]);assert.equal(vm.rejectDialog.reason,'授课安排存在冲突');assert.equal(vm.rejectDialog.invalid,false);await vm.doReject();assert.equal(writes,2)
})

test('T08 timeout with a formal rejection readback resolves without second command',async()=>{
  let writes=0;const row={taskId:'x',status:'ASSIGNED',weeklyHours:2}
  const vm=instance('AaTeacherTaskConfirmView',{academicAffairsApi:{teacherActTask:async()=>{writes++;return {code:503001,message:'响应超时'}},listAllTasks:async()=>page([{...row,status:writes?'REJECTED_BY_TEACHER':'ASSIGNED',rejectReason:writes?'授课安排存在冲突':''}])}})
  vm.loading=false;vm.rows=[row];vm.openReject(row);vm.rejectDialog.reason='授课安排存在冲突';await vm.doReject();await vm.doReject()
  assert.equal(writes,1);assert.equal(vm.pendingCommand,null);assert.equal(vm.receipt.pending,false)
})
test('T08 a teacher name without a stable key never submits assignment',async()=>{
  let writes=0
  const vm=instance('AaTeacherAssignConsoleView',{academicAffairsApi:{assignTeacher:async()=>{writes++}}})
  vm.assign={taskId:'x',batchId:'a',teacherName:'同名教师',teacherKey:''};await vm.doAssign();assert.equal(writes,0)
})
test('T08 closed batch precheck preserves assignment input without POST',async()=>{
  let writes=0
  const vm=instance('AaTeacherAssignConsoleView',{teachingTaskWorkbenchApi:{getBatch:async()=>ok({actions:{canAssign:false}})},academicAffairsApi:{assignTeacher:async()=>{writes++}}})
  vm.assign={taskId:'x',batchId:'a',teacherName:'教师',teacherKey:'stable'};await vm.doAssign()
  assert.equal(writes,0);assert.equal(vm.assign.teacherKey,'stable');assert.equal(vm.receipt.pending,true)
})
test('T08 assignment confirms against the same task and stable teacher in formal batch records',async()=>{
  const calls=[];const row={taskId:'x',teacherKey:'teacher2',status:'ASSIGNED'}
  const vm=instance('AaTeacherAssignConsoleView',{teachingTaskWorkbenchApi:{getBatch:async()=>{calls.push('CHECK');return ok({actions:{canAssign:true}})}},academicAffairsApi:{assignTeacher:async()=>{calls.push('POST');return ok({})},getBatchTasks:async()=>{calls.push('READ');return page([row])},listAllTasks:async()=>page([row])}})
  vm.assign={taskId:'x',batchId:'a',teacherName:'教师',teacherKey:'teacher2'};await vm.doAssign()
  assert.deepEqual(calls,['CHECK','POST','READ']);assert.equal(vm.receipt.pending,false)
})
test('T08 view permission never grants batch confirmation',async()=>{
  let writes=0
  const vm=instance('AaTaskDetailView',{academicAffairsApi:{collegeConfirmTaskBatch:async()=>{writes++}}},{ctx:{permissionPatterns:['academicAffairs.teachingTask.view']}})
  vm.loading=false;vm.workbench={actions:{canCollegeConfirm:true}};await vm.collegeConfirm();assert.equal(writes,0)
})
test('T08 switching batch ignores old workbench and task records',async()=>{
  const first=deferred()
  const vm=instance('AaTaskDetailView',{teachingTaskWorkbenchApi:{getBatch:id=>id==='a'?first.promise:Promise.resolve(ok({batchId:id}))},academicAffairsApi:{getBatchTasks:async id=>page([{taskId:id}])}})
  const request=vm.load();vm.$route.params.batchId='b';await vm.load();first.resolve(ok({batchId:'a'}));await request
  assert.equal(vm.workbench.batchId,'b');assert.equal(vm.rows[0].taskId,'b')
})
test('T08 statistics never combine terms or render a stale term response',async()=>{
  const first=deferred()
  const vm=instance('AaTaskStatsView',{academicAffairsApi:{getTeachingTaskStats:p=>p.termId==='a'?first.promise:Promise.resolve(ok({taskTotal:2,byTerm:[{termId:'b'}]}))}})
  vm.termId='a';const request=vm.load();vm.termId='b';await vm.load();first.resolve(ok({taskTotal:99,byTerm:[{termId:'a'}]}));await request
  assert.equal(vm.stats.taskTotal,2);vm.termId='';await vm.load();assert.equal(vm.stats,null)
})
test('T08 cross-term statistics returned by server are rejected',async()=>{
  const vm=instance('AaTaskStatsView',{academicAffairsApi:{getTeachingTaskStats:async()=>ok({byTerm:[{termId:'other'}]})}})
  vm.termId='current';await vm.load();assert.equal(vm.stats,null);assert.match(vm.error,/不一致/)
})
test('T08 changed roster or class version invalidates its preview',()=>{
  const vm=instance('AaTeachingClassDetailView')
  vm.loading=false;vm.teachingClass={status:'ACTIVE',currentRosterVersionId:'v1',rosterVersionNo:1};vm.rosterForm={studentIds:['1'],reason:'名单变更原因'};vm.rosterImpact={canCreate:true};vm.previewKey=vm.rosterKey
  assert.equal(vm.canCreateRosterVersion,true);vm.rosterForm.studentIds.push('2');assert.equal(vm.canCreateRosterVersion,false)
  vm.previewKey=vm.rosterKey;vm.teachingClass.currentRosterVersionId='v2';assert.equal(vm.canCreateRosterVersion,false)
})
test('T08 stale roster preview cannot authorize a changed student list',async()=>{
  const response=deferred();const vm=instance('AaTeachingClassDetailView',{teachingClassApi:{previewRosterChange:()=>response.promise}})
  vm.teachingClass={status:'ACTIVE'};vm.rosterForm.studentIds=['1'];const request=vm.previewRoster();vm.rosterForm.studentIds=['2'];response.resolve(ok({canCreate:true}));await request
  assert.equal(vm.rosterImpact,null);assert.equal(vm.previewKey,'')
})
test('T08 selection managed and read-only classes cannot create a roster',()=>{
  const vm=instance('AaTeachingClassDetailView',{getPermissionPatterns:()=>['academicAffairs.teachingTask.view']})
  vm.loading=false;vm.teachingClass={status:'ACTIVE'};vm.rosterImpact={canCreate:true};vm.rosterForm.reason='变更原因不少于五字';vm.previewKey=vm.rosterKey
  assert.equal(vm.canCreateRosterVersion,false)
})
test('T08 roster conflict preserves selected students and reason and clears prior preview',async()=>{
  const vm=instance('AaTeachingClassDetailView',{teachingClassApi:{previewRosterChange:async()=>({code:409001,message:'版本已变化'})}})
  vm.loading=false;vm.teachingClass={status:'ACTIVE'};vm.rosterForm={studentIds:['1'],reason:'保留名单和原因'};vm.previewKey=vm.rosterKey;vm.rosterImpact={canCreate:true};await vm.createRosterVersion()
  assert.deepEqual(vm.rosterForm.studentIds,['1']);assert.equal(vm.rosterForm.reason,'保留名单和原因');assert.equal(vm.rosterImpact,null)
})

test('T08 new roster receipt follows the currentRosterVersionId contract and exact members',async()=>{
  const calls=[]
  const vm=instance('AaTeachingClassDetailView',{teachingClassApi:{previewRosterChange:async()=>{calls.push('PREVIEW');return ok({canCreate:true})},createRosterVersion:async()=>{calls.push('POST');return ok({rosterVersionId:'v2'})},detail:async()=>{calls.push('GET');return ok({status:'ACTIVE',currentRosterVersionId:'v2',rosterVersionNo:2,rosterStatus:'LOCKED',currentMembers:[{studentId:'1'}],rosterVersions:[{rosterVersionId:'v1',lockedAt:'old-time'},{rosterVersionId:'v2',lockedAt:'2026-09-08T10:33:22Z'}]})}}})
  vm.loading=false;vm.teachingClass={status:'ACTIVE',currentRosterVersionId:'v1'};vm.rosterForm={studentIds:['1'],reason:'核对后新增版本'};vm.rosterImpact={canCreate:true};vm.previewKey=vm.rosterKey
  await vm.createRosterVersion();assert.deepEqual(calls,['PREVIEW','POST','GET']);assert.equal(vm.receipt.status,'第2版名单已生效');assert.equal(vm.receipt.pending,false);assert.equal(vm.receipt.time,'2026-09-08T10:33:22Z')
})
test('T08 old class load cannot reset another class roster draft',async()=>{
  const first=deferred()
  const vm=instance('AaTeachingClassDetailView',{teachingClassApi:{detail:id=>id==='a'?first.promise:Promise.resolve(ok({status:'ACTIVE',currentMembers:[{studentId:'b'}]}))}})
  const request=vm.load();vm.$route.query.teachingClassId='b';await vm.load();first.resolve(ok({currentMembers:[{studentId:'a'}]}));await request
  assert.deepEqual(vm.rosterForm.studentIds,['b'])
})
test('T08 a changed batch term cannot display an old task batch list',async()=>{
  const first=deferred()
  const vm=instance('AaTaskBatchListView',{academicAffairsApi:{getTaskBatches:p=>p.termId==='old'?first.promise:Promise.resolve(page([{batchId:'b'}]))}})
  vm.filters.termId='old';const request=vm.load();vm.filters.termId='new';await vm.load();first.resolve(page([{batchId:'a'}]));await request
  assert.equal(vm.rows[0].batchId,'b');assert.equal(vm.metrics[1].label,'待启动')
})
test('T08 differently versioned same-name courses cannot merge',()=>{
  const vm=instance('AaTaskMergeSplitView');vm.loading=false;vm.all=[{taskId:'1',batchId:'b',courseId:'v1',courseName:'同名课程',status:'ASSIGNED'},{taskId:'2',batchId:'b',courseId:'v2',courseName:'同名课程',status:'ASSIGNED'}];vm.selected=['1','2']
  assert.equal(vm.canMerge,false)
})
test('T08 selected tasks no longer eligible on fresh read never issue merge POST',async()=>{
  let writes=0
  const vm=instance('AaTaskMergeSplitView',{academicAffairsApi:{listAllTasks:async()=>page([{taskId:'1',batchId:'b',courseId:'v',status:'TEACHER_CONFIRMED'}]),mergeTasks:async()=>{writes++}}})
  vm.loading=false;vm.all=[{taskId:'1',batchId:'b',courseId:'v',status:'ASSIGNED'},{taskId:'2',batchId:'b',courseId:'v',status:'ASSIGNED'}];vm.selected=['1','2'];vm.mergeDialog.note='保留合班备注'
  await vm.doMerge();assert.equal(writes,0);assert.equal(vm.mergeDialog.note,'保留合班备注');assert.equal(vm.receipt.pending,true)
})
test('T08 adjustment readback must match submitted field values',async()=>{
  const vm=instance('AaTaskAdjustView',{academicAffairsApi:{adjustTask:async()=>ok({}),getBatchTasks:async()=>page([{taskId:'x',teacherKey:'old',status:'READY'}]),listAllTasks:async()=>page([])}})
  vm.adjust={taskId:'x',batchId:'b',teacherName:'新教师',teacherKey:'new',reason:'调整教师原因不少于五字'}
  await vm.doAdjust();assert.equal(vm.receipt.pending,true)
})
test('T08 read-only teaching class cannot run backfill',async()=>{
  let calls=0
  const vm=instance('AaTeachingClassListView',{teachingClassApi:{backfill:async()=>{calls++}}},{ctx:{permissionPatterns:['academicAffairs.teachingTask.view']}})
  vm.filters.termId='t';await vm.runBackfill();assert.equal(calls,0)
})

test('T08 class initialization remains loading until the term and formal list complete', async () => {
  const term=deferred();let listReads=0
  const vm=instance('AaTeachingClassListView',{academicAffairsApi:{getTerms:()=>term.promise,getCurrentTerm:async()=>ok({termId:'a'})},teachingClassApi:{list:async p=>{listReads++;assert.equal(p.termId,'a');return page([{teachingClassId:'class-a'}])}}})
  const init=vm.initialize();assert.equal(vm.loading,true);assert.equal(listReads,0)
  term.resolve(ok({list:[{termId:'a'}]}));await init
  assert.equal(vm.initialized,true);assert.equal(vm.loading,false);assert.equal(vm.rows[0].teachingClassId,'class-a')
})

for (const failure of [{status:403,message:'term scope denied'},new Error('term network failed')]) test(`T08 term initialization failure does not fall back to all-term class reads: ${failure.message}`, async () => {
  let listReads=0
  const vm=instance('AaTeachingClassListView',{academicAffairsApi:{getTerms:async()=>ok({list:[]}),getCurrentTerm:async()=>{throw failure}},teachingClassApi:{list:async()=>{listReads++;return page([])}}})
  await vm.initialize();assert.equal(listReads,0);assert.equal(vm.initialized,false);assert.equal(vm.loading,false);assert.match(vm.error,/term/)
  await vm.load();vm.onPageChange(2);vm.onTermChange();await vm.load()
  assert.equal(listReads,0);assert.match(vm.error,/term/)
})

test('T08 class query rejects empty and unlisted terms after initialization', async () => {
  let reads=0
  const vm=instance('AaTeachingClassListView',{teachingClassApi:{list:async()=>{reads++;return page([])}}})
  vm.initialized=true;vm.terms=[{termId:'a'}]
  await vm.load();vm.filters.termId='outside';await vm.load();assert.equal(reads,0)
  vm.filters.termId='a';await vm.load();assert.equal(reads,1)
})

for (const code of [0,503002]) test(`T08 assignment never accepts old hours for the same teacher: response ${code}`, async () => {
  let writes=0
  const row={taskId:'x',teacherKey:'stable',teacherName:'老师',weeklyHours:2,expectedStudents:30,status:'ASSIGNED'}
  const batch={batchId:'a',actions:{canAssign:true}}
  const vm=instance('AaTaskDetailView',{teachingTaskWorkbenchApi:{getBatch:async()=>ok(batch)},academicAffairsApi:{assignTeacher:async(id,body)=>{writes++;assert.equal(body.weeklyHours,8);return {code}},getBatchTasks:async()=>page([row])}})
  vm.loading=false;vm.workbench=batch;vm.rows=[row];vm.openAssign(row);vm.assign.weeklyHours=8
  await vm.doAssign();assert.ok(vm.pendingResult);assert.equal(vm.receipt.pending,true)
  await vm.doAssign();assert.equal(writes,1);assert.equal(vm.receipt.status,'结果待确认')
})

test('T08 late precheck from A cannot submit after A to B to A', async () => {
  const first=deferred();let reads=0,writes=0
  const vm=instance('AaTaskDetailView',{teachingTaskWorkbenchApi:{getBatch:async id=>++reads===1?first.promise:ok({batchId:id,actions:{canCollegeConfirm:true}})},academicAffairsApi:{collegeConfirmTaskBatch:async()=>{writes++;return ok({})},getBatchTasks:async()=>page([])}})
  vm.loading=false;vm.workbench={batchId:'a',actions:{canCollegeConfirm:true}}
  const old=vm.collegeConfirm()
  vm.selectedBatchId='b';await vm.changeBatch();vm.selectedBatchId='a';await vm.changeBatch()
  first.resolve(ok({batchId:'a',actions:{canCollegeConfirm:true}}));await old
  assert.equal(writes,0);assert.equal(vm.pendingResult,null)
})

test('T08 an unknown batch operation survives A to B to A without replay', async () => {
  let writes=0
  const vm=instance('AaTaskDetailView',{teachingTaskWorkbenchApi:{getBatch:async id=>ok({batchId:id,status:'DRAFT',actions:{canCollegeConfirm:true}})},academicAffairsApi:{collegeConfirmTaskBatch:async()=>{writes++;return {code:503002}},getBatchTasks:async()=>page([])}})
  vm.loading=false;vm.workbench={batchId:'a',actions:{canCollegeConfirm:true}}
  await vm.collegeConfirm();const pending=vm.pendingResult
  vm.selectedBatchId='b';await vm.changeBatch();assert.equal(vm.pendingResult,null)
  vm.selectedBatchId='a';await vm.changeBatch();assert.equal(vm.pendingResult,pending)
  await vm.collegeConfirm();assert.equal(writes,1);assert.equal(vm.receipt.pending,true)
})

test('T08 command response arriving after A to B to A cannot resolve the original lock', async () => {
  const response=deferred(),started=deferred();let writes=0
  const vm=instance('AaTaskDetailView',{teachingTaskWorkbenchApi:{getBatch:async id=>ok({batchId:id,status:'COLLEGE_CONFIRMED',actions:{canCollegeConfirm:true}})},academicAffairsApi:{collegeConfirmTaskBatch:()=>{writes++;started.resolve();return response.promise},getBatchTasks:async()=>page([])}})
  vm.loading=false;vm.workbench={batchId:'a',actions:{canCollegeConfirm:true}}
  const action=vm.collegeConfirm();await started.promise
  vm.selectedBatchId='b';await vm.changeBatch();vm.selectedBatchId='a';await vm.changeBatch()
  response.resolve(ok({}));await action;await vm.collegeConfirm()
  assert.equal(writes,1);assert.ok(vm.pendingResult);assert.equal(vm.receipt.pending,true)
})

test('T08 assignment freezes task identity and all requested values while precheck awaits', async () => {
  const response=deferred();let reads=0,posted
  const row={taskId:'x',teacherKey:'stable',teacherName:'老师',weeklyHours:8,expectedStudents:30,status:'ASSIGNED'}
  const batch={batchId:'a',actions:{canAssign:true}}
  const vm=instance('AaTaskDetailView',{teachingTaskWorkbenchApi:{getBatch:()=>++reads===1?response.promise:Promise.resolve(ok(batch))},academicAffairsApi:{assignTeacher:async(id,body)=>{posted={id,...body};return ok({})},getBatchTasks:async()=>page([row])}})
  vm.loading=false;vm.workbench=batch;vm.rows=[row];vm.openAssign(row);const action=vm.doAssign()
  vm.assign.taskId='other';vm.assign.weeklyHours=99;vm.assign.teacherKey='other'
  response.resolve(ok(batch));await action
  assert.deepEqual(posted,{id:'x',teacherKey:'stable',teacherName:'老师',weeklyHours:8,expectedStudents:30});assert.equal(vm.receipt.pending,false)
})

test('T08 an old term initialization cannot replace the new identity class query', async () => {
  const first=deferred();let n=0
  const vm=instance('AaTeachingClassListView',{academicAffairsApi:{getTerms:()=>++n===1?first.promise:Promise.resolve(ok({list:[{termId:'new'}]})),getCurrentTerm:async()=>ok({termId:'new'})},teachingClassApi:{list:async()=>page([{teachingClassId:'new-class'}])}})
  const old=vm.initialize();vm.ctx={permissionPatterns:['*']};await vm.initialize();first.resolve(ok({list:[{termId:'old'}]}));await old
  assert.equal(vm.terms[0].termId,'new');assert.equal(vm.rows[0].teachingClassId,'new-class');assert.equal(vm.loading,false)
})
test('T08 old term backfill preview cannot authorize another term',async()=>{
  const response=deferred();const vm=instance('AaTeachingClassListView',{teachingClassApi:{backfill:()=>response.promise}})
  vm.filters.termId='old';const request=vm.runBackfill();vm.filters.termId='new';response.resolve(ok({taskCount:1,readyCount:1}));await request
  assert.equal(vm.canExecuteBackfill,false);assert.equal(vm.backfillReport,null)
})
test('T08 workload conflict keeps rejection draft',async()=>{
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>page([{declarationId:'1',status:'SUBMITTED'}]),reviewWorkloadDeclaration:async()=>({code:409001,message:'已由他人审核'})}})
  vm.rejecting={declarationId:'1',status:'SUBMITTED'};vm.rejectNote='保留本次驳回意见';await vm.doReject()
  assert.equal(vm.rejectNote,'保留本次驳回意见');assert.equal(vm.rejecting.declarationId,'1');assert.equal(vm.receipt.pending,true)
})
test('T08 workload readback searches the original term without submitted-only status',async()=>{
  const calls=[];let written=false;const row={declarationId:'1',status:'SUBMITTED',termCode:'2026-2027-1'}
  const formal={...row,status:'APPROVED',reviewedAt:'2026-09-08T08:00:00Z',reviewedBy:'reviewer'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{reviewWorkloadDeclaration:async()=>{written=true;return ok(formal)},getWorkloadDeclarations:async params=>{calls.push(params);return page([written?formal:row])}}})
  vm.status='SUBMITTED';await vm.submitReview(row,'APPROVE','');assert.equal(calls[0].status,undefined);assert.equal(calls[0].termCode,row.termCode);assert.equal(vm.receipt.status,'已通过')
})

test('T08 workload without the existing stats permission cannot submit', async()=>{
  let writes=0
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{reviewWorkloadDeclaration:async()=>{writes++}}},{ctx:{permissionPatterns:['academicAffairs.teachingTask.view']}})
  await vm.submitReview({declarationId:'1',status:'SUBMITTED'},'APPROVE','');assert.equal(writes,0)
})

test('T08 changed workload hours invalidate the frozen confirmation before POST', async()=>{
  let writes=0
  const row={declarationId:'1',teacherKey:'teacher',termCode:'t',hours:2,status:'SUBMITTED'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>page([{...row,hours:8}]),reviewWorkloadDeclaration:async()=>{writes++}}})
  vm.openApprove(row);row.hours=99;assert.equal(vm.approveTarget.hours,2)
  await vm.submitReview(vm.approveTarget,'APPROVE','');assert.equal(writes,0);assert.equal(vm.invalid,true)
})

for(const response of [503002,0]) test(`T08 workload response ${response} cannot accept another teacher or old hours`,async()=>{
  let writes=0
  const row={declarationId:'1',teacherKey:'teacher',termCode:'t',hours:2,status:'SUBMITTED'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>page([writes?{...row,teacherKey:'other',hours:8,status:'APPROVED'}:row]),reviewWorkloadDeclaration:async()=>{writes++;return {code:response}}}})
  vm.loading=false;await vm.submitReview(row,'APPROVE','');await vm.submitReview(row,'APPROVE','')
  assert.equal(writes,1);assert.ok(vm.pending);assert.equal(vm.receipt.pending,true)
})

test('T08 unknown workload review matching current facts stays query-only after scope round trip',async()=>{
  let writes=0
  const row={declarationId:'1',teacherKey:'teacher',termCode:'a',hours:2,status:'SUBMITTED'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>page([writes?{...row,status:'APPROVED'}:row]),reviewWorkloadDeclaration:async()=>{writes++;throw new Error('lost')}}})
  vm.loading=false;await vm.submitReview(row,'APPROVE','')
  vm.termCode='b';vm.invalidateScope();vm.termCode='a';vm.invalidateScope();await vm.load();await vm.submitReview(row,'APPROVE','')
  assert.equal(writes,1);assert.ok(vm.pending);assert.equal(vm.receipt.pending,true)
})

test('T08 workload scope A to B to A during precheck prevents old POST',async()=>{
  const first=deferred();let writes=0
  const row={declarationId:'1',status:'SUBMITTED',termCode:'a'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:()=>first.promise,reviewWorkloadDeclaration:async()=>{writes++}}})
  const action=vm.submitReview(row,'APPROVE','');vm.termCode='b';vm.invalidateScope();vm.termCode='a';vm.invalidateScope()
  first.resolve(page([row]));await action;assert.equal(writes,0)
})

test('T08 workload identity changes reject late precheck and list responses',async()=>{
  const first=deferred();let writes=0
  const row={declarationId:'1',status:'SUBMITTED'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:()=>first.promise,reviewWorkloadDeclaration:async()=>{writes++}}})
  const action=vm.submitReview(row,'APPROVE',''),read=vm.load();vm.ctx={permissionPatterns:[]}
  first.resolve(page([row]));await Promise.all([action,read]);assert.equal(writes,0);assert.deepEqual(vm.rows,[])
})

test('T08 workload 403 erases original notes and rows without fallback reads',async()=>{
  let reads=0
  const row={declarationId:'1',status:'SUBMITTED'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>{reads++;return page([row])},reviewWorkloadDeclaration:async()=>({status:403,message:'scope denied'})}})
  vm.rows=[row];vm.openReject(row);vm.rejectNote='原审核意见需清除';await vm.doReject()
  assert.equal(reads,1);assert.deepEqual(vm.rows,[]);assert.equal(vm.rejectNote,'');assert.equal(vm.pending,null);assert.equal(vm.receipt,null)
})

test('T08 workload repeated pagination fails instead of issuing an unbounded search',async()=>{
  let reads=0
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>{reads++;return ok({list:[{declarationId:'other'}],total:3})}}})
  await assert.rejects(vm.readDeclaration({declarationId:'1'},()=>true),/分页重复/);assert.equal(reads,2)
})

test('T08 class source uses the formation batch snapshot and exact task with a safe return',async()=>{
  let destination
  const vm=instance('AaTeachingClassDetailView',{teachingTaskWorkbenchApi:{getBatch:async id=>{assert.equal(id,'72');return ok({batchId:'72'})}},academicAffairsApi:{getBatchTasks:async()=>page([{taskId:'18'}])}})
  vm.loading=false;vm.teachingClass={teachingTaskId:'18',sourceSnapshot:{batchId:'72',teachingTaskId:'18'}};vm.$router.push=route=>{destination=route}
  await vm.openSourceTask();assert.equal(destination.path,'/admin/academic-affairs/teaching-tasks/72');assert.equal(destination.query.teachingTaskId,'18');assert.equal(destination.query.returnTo,vm.$route.fullPath)
})

for(const snapshot of [undefined,{batchId:'72',teachingTaskId:'other'},{teachingTaskId:'18'}]) test(`T08 class source cannot guess a batch from missing or mismatched snapshot: ${JSON.stringify(snapshot)}`,async()=>{
  let calls=0
  const vm=instance('AaTeachingClassDetailView',{teachingTaskWorkbenchApi:{getBatch:async()=>{calls++}}})
  vm.loading=false;vm.teachingClass={teachingTaskId:'18',sourceSnapshot:snapshot};await vm.openSourceTask();assert.equal(calls,0);assert.equal(vm.sourceTask,null)
})

test('T08 no source navigation occurs when the formal task is absent from its snapshot batch',async()=>{
  let navigations=0
  const vm=instance('AaTeachingClassDetailView',{teachingTaskWorkbenchApi:{getBatch:async()=>ok({batchId:'72'})},academicAffairsApi:{getBatchTasks:async()=>page([{taskId:'other'}])}})
  vm.loading=false;vm.teachingClass={teachingTaskId:'18',sourceSnapshot:{batchId:'72',teachingTaskId:'18'}};vm.$router.push=()=>{navigations++}
  await vm.openSourceTask();assert.equal(navigations,0);assert.match(vm.error,/已不在该批次/)
})

test('T08 source task focus uses stable task ID and can be removed without losing return',async()=>{
  const vm=instance('AaTaskDetailView');vm.rows=[{taskId:'18'},{taskId:'19'}];vm.$route.query={teachingTaskId:'18',returnTo:'/admin/academic-affairs/teaching-tasks?view=classes&teachingClassId=1'}
  assert.deepEqual(vm.filteredRows.map(row=>row.taskId),['18']);let route;vm.$router.replace=value=>{route=value};vm.showWholeBatch();assert.equal(route.query.teachingTaskId,undefined);assert.equal(route.query.returnTo,vm.$route.query.returnTo)
})

test('T08 return to class list preserves original term filters and refuses external targets',async()=>{
  const vm=instance('AaTeachingClassDetailView');let destination;vm.$router.push=route=>{destination=route}
  vm.$route.query={returnTo:'/admin/academic-affairs/teaching-tasks?view=classes&termId=7&status=ACTIVE'};vm.backToClasses();assert.equal(destination,vm.$route.query.returnTo)
  vm.$route.query={returnTo:'https://example.org',termId:'7'};vm.backToClasses();assert.equal(destination.path,'/admin/academic-affairs/teaching-tasks');assert.equal(destination.query.termId,'7')
})

for(const commandResult of [503002,0]) test(`T08 a denied read after command ${commandResult} erases business payload but retains the original replay barrier`,async()=>{
  let writes=0,deny=false
  const row={declarationId:'11',status:'SUBMITTED',teacherKey:'private-key',teacherName:'private-name',termCode:'private-term',hours:2,description:'private-description'}
  const formal={...row,status:'APPROVED',reviewedAt:'2026-09-08T08:00:00Z',reviewedBy:'reviewer'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>deny?{status:403,message:'scope denied'}:page([row]),reviewWorkloadDeclaration:async()=>{writes++;deny=true;return {code:commandResult,data:formal}}}})
  vm.loading=false;vm.rows=[row];vm.openApprove(row);await vm.submitReview(vm.approveTarget,'APPROVE','')
  assert.deepEqual(vm.pending,{row:{declarationId:'11'},acknowledged:false,redacted:true})
  assert.deepEqual(vm.rows,[]);assert.equal(vm.approveTarget,null);assert.equal(vm.receipt,null)
  assert.equal(JSON.stringify(vm.pending).includes('private-'),false)
  deny=false;await vm.load();vm.openApprove(row);await vm.submitReview(row,'APPROVE','')
  assert.equal(writes,1);assert.equal(vm.receipt.pending,true);assert.ok(vm.pending)
})

test('T08 an explicitly thrown command 403 is a rejection, not an unknown read barrier',async()=>{
  let reads=0
  const row={declarationId:'11',status:'SUBMITTED'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>{reads++;return page([row])},reviewWorkloadDeclaration:async()=>{throw {status:403,message:'command denied'}}}})
  await vm.submitReview(row,'APPROVE','');assert.equal(reads,1);assert.equal(vm.pending,null);assert.equal(vm.receipt,null)
})

for(const change of [{declarationId:'99'},{teacherKey:'other'},{hours:99},{status:'REJECTED'},{reviewedAt:null},{reviewedBy:null},{}]) test(`T08 successful envelope without matching formal command evidence stays unknown: ${JSON.stringify(change)}`,async()=>{
  let writes=0
  const row={declarationId:'11',status:'SUBMITTED',teacherKey:'teacher',hours:2,termCode:'t'}
  const formal={...row,status:'APPROVED',reviewedAt:'2026-09-08T08:00:00Z',reviewedBy:'reviewer'}
  const evidence=Object.keys(change).length?{...formal,...change}:{}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>page([writes?formal:row]),reviewWorkloadDeclaration:async()=>{writes++;return ok(evidence)}}})
  vm.loading=false;await vm.submitReview(row,'APPROVE','');await vm.submitReview(row,'APPROVE','')
  assert.equal(writes,1);assert.equal(vm.pending.acknowledged,false);assert.equal(vm.receipt.pending,true)
})

for(const change of [{reviewedAt:'2026-09-08T08:01:00Z'},{reviewedBy:'someone-else'}]) test(`T08 formal readback must retain the exact command review evidence: ${JSON.stringify(change)}`,async()=>{
  let writes=0
  const row={declarationId:'11',status:'SUBMITTED',teacherKey:'teacher',hours:2,termCode:'t'}
  const formal={...row,status:'APPROVED',reviewedAt:'2026-09-08T08:00:00Z',reviewedBy:'reviewer'}
  const vm=instance('AaWorkloadReviewView',{academicAffairsApi:{getWorkloadDeclarations:async()=>page([writes?{...formal,...change}:row]),reviewWorkloadDeclaration:async()=>{writes++;return ok(formal)}}})
  vm.loading=false;await vm.submitReview(row,'APPROVE','');await vm.submitReview(row,'APPROVE','')
  assert.equal(writes,1);assert.ok(vm.pending);assert.equal(vm.receipt.pending,true)
})
