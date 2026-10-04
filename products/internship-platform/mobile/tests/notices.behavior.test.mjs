import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { checkinLocationPolicy } from '../src/services/checkinPresentation.mjs'

const batch = '9007199254740993001'
const notice = id => ({ id:String(id), batchId:batch, title:'合成重要通知', urgency:'IMPORTANT' })
function deferred() { let resolve,reject; const promise=new Promise((a,b)=>{resolve=a;reject=b}); return {promise,resolve,reject} }
function page(api={},teacher=false,pathOverride='',files={}) {
  const path=pathOverride || (teacher?'teacher-internship/activity/index.vue':'student-internship/index.vue')
  const source=fs.readFileSync(new URL('../src/pages/'+path,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let generation=0
  const memory=new Map(), messages=[]
  const context={batches:[],selectedBatchId:batch,restore(){},load:async()=>{},can:()=>false}
  const uni={getStorageSync:k=>memory.get(k),setStorageSync:(k,v)=>memory.set(k,v),removeStorageSync:k=>memory.delete(k)}
  const names=['studentApi','teacherApi','currentSessionGeneration','formatDateTime','openBusinessFile','toast','go','uni',
    'useInternshipContextStore','normalizeError','reportTypeLabel','reportPeriodLabel','localizedMakeupStatus','chooseSingleFile','uploadBusinessFile','ReportFilePreview','checkinLocationPolicy']
  const component=new Function(...names,script)(api,api,()=>generation,x=>x,async()=>{},x=>messages.push(x),()=>{},
    uni,()=>context,()=>({text:'操作未完成'}),()=>'',()=>'',()=>'',async()=>null,files.uploadBusinessFile || (async()=>null),{},checkinLocationPolicy)
  const vm={}
  for(const [name,method] of Object.entries(component.methods)) vm[name]=(...args)=>method.apply(vm,args)
  Object.assign(vm,component.data.call(vm))
  for(const [name,getter] of Object.entries(component.computed || {})) Object.defineProperty(vm,name,{get:()=>getter.call(vm)})
  vm.state='ready';vm.i={hasBatch:true,batchId:batch};vm.selectedBatchId=batch;vm.batchId=batch
  return {vm,component,messages,uni,switchAccount:()=>generation++}
}
function active(vm,teacher=false) {
  const rows=[notice('9007199254740993011'),notice('9007199254740993012')]
  if(teacher) {vm.pendingNotices=rows;vm.activeNotice=rows[0]}
  else {vm.pendingEmergencyNotices=rows;vm.activeEmergencyNotice=rows[0]}
  return rows
}

test('教师选择较早月份从服务端完整读取，今日记录仍保留且可读该月正式照片',async()=>{
  const requests=[],opened=[]
  const historic={id:'8000000000000000001',batchId:batch,localDate:'2024-02-29',note:'旧月备注',photoFileId:'8000000000000000002'}
  const p=page({getMyInternshipCheckins:async(...args)=>{requests.push(args);return [historic]}},true)
  p.vm.checkins=[{id:'today',batchId:batch,localDate:new Date().toISOString().slice(0,10)}]
  p.vm.$refs={checkinPreview:{open:async file=>opened.push(file),reset(){}}}
  await p.vm.onCalendarMonth({detail:{value:'2024-02'}})
  assert.deepEqual(requests,[[batch,31,'2024-02']]);assert.equal(p.vm.calendarState,'ready')
  assert.equal(p.vm.monthCheckins[0].id,historic.id);assert.equal(p.vm.checkins[0].id,'today')
  assert.equal(p.vm.calendarCells.find(cell=>cell.day===29).row.id,historic.id)
  await p.vm.openCheckinEvidence({...historic,photoFileId:'other'},true)
  assert.equal(opened[0].fileId,historic.photoFileId)
})

test('教师日历月份、批次和账号的迟到响应不覆盖当前日历',async()=>{
  const old=deferred(),p=page({getMyInternshipCheckins:async(_batch,_limit,month)=>month==='2024-01'?old.promise:[{id:'new',batchId:batch,localDate:'2024-02-01'}]},true)
  const pending=p.vm.onCalendarMonth({detail:{value:'2024-01'}})
  await p.vm.onCalendarMonth({detail:{value:'2024-02'}})
  old.resolve([{id:'old',batchId:batch,localDate:'2024-01-01'}]);await pending
  assert.equal(p.vm.monthCheckins[0].id,'new')
  const other=deferred(),q=page({getMyInternshipCheckins:()=>other.promise},true)
  const waiting=q.vm.onCalendarMonth({detail:{value:'2024-01'}})
  q.switchAccount();q.vm.clearAccountContext();other.resolve([{id:'old'}]);await waiting
  assert.deepEqual(q.vm.calendarCheckins,[]);assert.equal(q.vm.calendarState,'idle')
})

test('教师历史读取失败不冒充零记录，重试恢复同一所选月份',async()=>{
  let calls=0
  const p=page({getMyInternshipCheckins:async()=>{if(++calls===1)throw new Error('network');return [{id:'restored',localDate:'2024-01-01'}]}},true)
  p.vm.calendarCheckins=[{id:'old'}]
  await p.vm.onCalendarMonth({detail:{value:'2024-01'}})
  assert.equal(p.vm.calendarState,'error');assert.ok(p.vm.calendarError.includes('不代表没有签到'));assert.deepEqual(p.vm.calendarCheckins,[])
  await p.vm.loadCalendar();assert.equal(p.vm.calendarMonth,'2024-01');assert.equal(p.vm.calendarState,'ready');assert.equal(p.vm.calendarCheckins[0].id,'restored')
})

test('教师照片使用当前本人签到编号和批次，不能借旧行参数读取其他文件',async()=>{
  const p=page({},true),opened=[]
  p.vm.$refs={checkinPreview:{open:async file=>opened.push(file),reset(){}}}
  const row={id:'9007199254740993011',batchId:batch,localDate:'2026-10-04',photoFileId:'9007199254740993012',watermarkedFileId:'9007199254740993013'}
  p.vm.checkins=[row]
  await p.vm.openCheckinEvidence({...row,photoFileId:'foreign'},true)
  await p.vm.openCheckinEvidence({...row,watermarkedFileId:'foreign'})
  assert.deepEqual(opened.map(file=>file.fileId),[row.photoFileId,row.watermarkedFileId])
  await p.vm.openCheckinEvidence({...row,id:'other'})
  p.vm.batchId='other';await p.vm.openCheckinEvidence(row)
  assert.equal(opened.length,2)
})

test('教师境外定位采用国际坐标，提交保留国家和当前时区',async()=>{
  let position,body
  const p=page({createMyInternshipCheckin:async value=>{body=value;return {result:'LOCATION_UNCERTAIN'}}},true)
  p.vm.checkinOverseas=true;p.vm.checkinCountryRegion='日本';p.vm.checkinTimezoneName='Asia/Tokyo'
  p.uni.getLocation=value=>position=value;p.vm.load=async()=>{}
  p.vm.beginTeacherCheckin();assert.equal(position.type,'wgs84')
  await position.success({latitude:35.6762,longitude:139.6503,accuracy:1})
  assert.equal(body.coordinateSystem,'WGS84');assert.equal(body.countryRegion,'日本');assert.equal(body.timezoneName,'Asia/Tokyo')
  assert.ok(p.messages[0].includes('定位待核实'));assert.ok(!p.messages[0].includes('签到成功'))
})

test('教师状态分别显示范围外、设备风险和仅留痕，不把异常显示已完成',()=>{
  const p=page({},true)
  for(const state of ['OUT_OF_RANGE','MOCK_LOCATION','LOCATION_UNCERTAIN','NO_LOCATION','LOW_ACCURACY']) {
    assert.equal(p.vm.checkinTone(state),'warning');assert.equal(p.vm.checkinResultShort(state),'核')
    assert.notEqual(p.vm.checkinResultLabel(state),'已记录')
  }
  assert.equal(p.vm.checkinTone('RECORDED'),'default');assert.equal(p.vm.checkinResultLabel('RECORDED'),'仅作留痕')
  assert.equal(p.vm.coordinateLabel('WGS84'),'国际通用坐标')
})

test('教师切批次或账号清除旧地点范围和境外输入',()=>{
  const p=page({},true)
  p.vm.checkinRule={configured:true,locations:[{name:'旧地点'}]};p.vm.checkinOverseas=true;p.vm.checkinCountryRegion='旧地区'
  p.vm.clearAccountContext();assert.equal(p.vm.checkinRule,null);assert.equal(p.vm.checkinOverseas,false);assert.equal(p.vm.checkinCountryRegion,'')
})

test('教师批次未进行或后端拒绝登记时保留输入且不发起定位和签到',()=>{
  const p=page({},true);let calls=0
  p.vm.checkinRule={canCheckin:false,unavailableReason:'当前批次未在进行中'};p.vm.checkinNote='保留的本人备注'
  p.uni.showModal=()=>calls++;p.uni.getLocation=()=>calls++
  p.vm.checkin();p.vm.beginTeacherCheckin();assert.equal(calls,0);assert.equal(p.vm.checkinNote,'保留的本人备注')
})

test('教师照片离页和切账号关闭，隐藏或旧账号不能重新打开',async()=>{
  const p=page({},true);let opened=0,closed=0
  p.vm.$refs={checkinPreview:{open:async()=>opened++,reset:()=>closed++}}
  p.vm.checkins=[{id:'1',batchId:batch,watermarkedFileId:'2'}]
  p.component.onHide.call(p.vm);await p.vm.openCheckinEvidence({id:'1'});assert.equal(opened,0);assert.equal(closed,1)
  p.vm.hidden=false;p.switchAccount();await p.vm.openCheckinEvidence({id:'1'});assert.equal(opened,0)
  p.vm.clearAccountContext();assert.equal(closed,2);assert.deepEqual(p.vm.checkins,[])
  p.component.onUnload.call(p.vm);assert.equal(closed,3)
})

test('教师现场相机迟到返回和上传迟到结果不能带入新账号',async()=>{
  let options,uploads=0
  const p=page({},true,'',{uploadBusinessFile:async()=>{uploads++;return {fileId:'old'}}})
  p.uni.chooseImage=o=>options=o;p.vm.captureCheckinPhoto();p.switchAccount();p.vm.clearAccountContext()
  await options.success({tempFilePaths:['synthetic.jpg'],tempFiles:[{name:'合成照片.jpg'}]})
  assert.equal(uploads,0);assert.equal(p.vm.checkinPhotoFileId,'');assert.equal(p.vm.checkinPhotoUploading,false)
  const d=deferred(),q=page({},true,'',{uploadBusinessFile:()=>d.promise})
  q.uni.chooseImage=o=>options=o;q.vm.captureCheckinPhoto()
  const pending=options.success({tempFilePaths:['synthetic.jpg'],tempFiles:[]})
  q.switchAccount();q.vm.clearAccountContext();q.vm.checkinPhotoName='新账号输入'
  d.resolve({fileId:'old'});await pending
  assert.equal(q.vm.checkinPhotoFileId,'');assert.equal(q.vm.checkinPhotoName,'新账号输入');assert.equal(q.vm.checkinPhotoUploading,false)
})

test('教师旧确认框和迟到定位不能在切换账号后发起签到',async()=>{
  let modal,location,saves=0
  const p=page({createMyInternshipCheckin:async()=>saves++},true)
  p.uni.showModal=o=>modal=o;p.uni.getLocation=o=>location=o
  p.vm.checkin();p.switchAccount();p.vm.clearAccountContext();modal.success({confirm:true})
  assert.equal(location,undefined);assert.equal(saves,0)
  const q=page({createMyInternshipCheckin:async()=>saves++},true)
  q.uni.getLocation=o=>location=o;q.vm.beginTeacherCheckin();q.switchAccount();q.vm.clearAccountContext()
  await location.success({latitude:28,longitude:112,accuracy:1})
  assert.equal(saves,0);assert.equal(q.vm.checking,false)
})

test('教师当前相机上传和签到成功保留当前批次并正式回读',async()=>{
  let options,submitted,rereads=0
  const p=page({createMyInternshipCheckin:async body=>{submitted=body;return {evidenceAvailable:true}}},true,'',{uploadBusinessFile:async()=>({fileId:'9007199254740993012',fileName:'合成照片.jpg'})})
  p.uni.chooseImage=o=>options=o;p.vm.captureCheckinPhoto()
  await options.success({tempFilePaths:['synthetic.jpg'],tempFiles:[]})
  assert.equal(p.vm.checkinPhotoFileId,'9007199254740993012');assert.equal(p.vm.checkinPhotoUploading,false)
  p.uni.getLocation=o=>options=o;p.vm.load=async()=>rereads++;p.vm.beginTeacherCheckin()
  await options.success({latitude:28,longitude:112,accuracy:1})
  assert.equal(String(submitted.batchId),batch);assert.equal(submitted.photoFileId,'9007199254740993012')
  assert.equal(p.vm.checkinPhotoFileId,'');assert.equal(p.vm.checking,false);assert.equal(rereads,1)
})

test('教师本人报告切换账号后旧保存结果不能回填或通知',async()=>{
  const d=deferred();const p=page({saveMyInternshipPeriodReport:()=>d.promise},true);p.vm.periodForm.content='合成指导工作。'.repeat(10);p.vm.periodForm.periodKey='2026-W40';const pending=p.vm.savePeriodReport();p.switchAccount();p.vm.clearAccountContext();p.vm.periodForm.content='新账号输入';d.resolve({});await pending;assert.equal(p.vm.periodForm.content,'新账号输入');assert.equal(p.messages.length,0);assert.equal(p.vm.periodSaving,false)
})
test('教师本人报告成功后解除提交中状态并回读同一批次',async()=>{
  const p=page({saveMyInternshipPeriodReport:async()=>({})},true);let rereads=0;p.vm.load=async()=>rereads++;p.vm.periodForm.content='合成指导工作。'.repeat(10);p.vm.periodForm.periodKey='2026-W40';await p.vm.savePeriodReport();assert.equal(p.vm.periodSaving,false);assert.equal(rereads,1);assert.ok(p.messages.includes('教师周期报告已保存'))
})
test('教师移动报告使用当前批次字数上限阻断超长输入',async()=>{
  let saved=false;const p=page({saveMyInternshipPeriodReport:async()=>{saved=true}},true);p.vm.periodRules={weeklyMaxWords:40};p.vm.periodForm.content='合成指导工作。'.repeat(10);await p.vm.savePeriodReport();assert.equal(saved,false);assert.ok(p.messages[0].includes('40'))
})
test('跨端旧版本拒绝保留教师输入并明确提示重新读取',async()=>{
  const p=page({saveMyInternshipPeriodReport:async()=>{throw {code:1,biz:true,bizCode:'DATA_CONFLICT',httpStatus:400,message:'服务暂时不可用，请稍后重试'}}},true)
  const original='合成指导工作。'.repeat(10);p.vm.periodForm.content=original;p.vm.periodForm.periodKey='2026-W40';p.vm.periodForm.expectedVersion=0
  await p.vm.savePeriodReport()
  assert.equal(p.vm.periodForm.content,original);assert.equal(p.vm.periodForm.expectedVersion,0);assert.equal(p.vm.periodSaving,false)
  assert.match(p.vm.periodError,/已在其他页面更新/);assert.match(p.vm.periodError,/当前输入已保留/);assert.match(p.vm.periodError,/重新读取/)
  assert.equal(p.messages[0],p.vm.periodError)
  p.vm.editPeriodReport({reportType:'WEEKLY',periodKey:'2026-W40',content:'当前已保存内容',version:1,attachmentFileIds:[]})
  assert.equal(p.vm.periodError,'');assert.equal(p.vm.periodForm.expectedVersion,1)
})
test('服务异常不能冒充版本冲突或输出后端内部信息',async()=>{
  const p=page({saveMyInternshipPeriodReport:async()=>{throw {code:1,biz:true,bizCode:'DATA_CONFLICT',httpStatus:500,message:'SQL stack secret'}}},true)
  p.vm.periodForm.content='合成指导工作。'.repeat(10);await p.vm.savePeriodReport()
  assert.equal(p.vm.periodError,'操作未完成');assert.doesNotMatch(p.vm.periodError,/SQL|secret|版本冲突/)
})
test('教师报告手动重新读取不会把点击事件当作回调或覆盖旧草稿',async()=>{
  const p=page({getMyInternshipCheckins:async()=>[],getMyInternshipCheckinRule:async()=>({configured:false,locations:[]}),getMyInternshipMakeups:async()=>({items:[]}),getMyInternshipWorkReports:async()=>({items:[]}),getMyInternshipPeriodReports:async()=>({items:[{id:'1',version:2}],rules:{weeklyMaxWords:12000}}),getInternshipEmergencyNotices:async()=>[],getPendingInternshipEmergencyNotices:async()=>[]},true)
  p.vm.periodForm.content='保留当前输入';p.vm.periodForm.expectedVersion=1
  await p.vm.load({type:'click'})
  assert.equal(p.vm.state,'ready');assert.equal(p.vm.periodReports[0].version,2)
  assert.equal(p.vm.periodForm.content,'保留当前输入');assert.equal(p.vm.periodForm.expectedVersion,1)
})

test('reading a student popup never sends an acknowledgement',async()=>{
  let acknowledgements=0
  const {vm}=page({getPendingEmergencyNotices:async()=>[notice(1)],acknowledgeEmergencyNotice:async()=>acknowledgements++})
  await vm.loadEmergencyNotices();assert.equal(vm.activeEmergencyNotice.id,'1');assert.equal(acknowledgements,0)
})
test('successful student acknowledgement removes only the explicitly selected large ID',async()=>{
  let request
  const {vm}=page({acknowledgeEmergencyNotice:async(...args)=>{request=args}})
  const rows=active(vm);await vm.acknowledgeEmergencyNotice()
  assert.deepEqual(request,[rows[0].id,batch]);assert.equal(vm.activeEmergencyNotice.id,rows[1].id);assert.equal(vm.noticeAcking,false)
})
test('failed acknowledgement keeps the popup and its queue for retry',async()=>{
  const {vm}=page({acknowledgeEmergencyNotice:async()=>{throw Error('服务暂不可用')}})
  const rows=active(vm);await vm.acknowledgeEmergencyNotice()
  assert.equal(vm.activeEmergencyNotice,rows[0]);assert.equal(vm.pendingEmergencyNotices.length,2);assert.match(vm.noticeError,/暂不可用/);assert.equal(vm.noticeAcking,false)
})
test('an old batch response cannot remove the current batch notice or reset its busy state',async()=>{
  const wait=deferred();const {vm}=page({acknowledgeEmergencyNotice:()=>wait.promise});active(vm)
  const call=vm.acknowledgeEmergencyNotice();vm.selectedBatchId='2';vm.loadSequence++
  const current=notice('current');vm.pendingEmergencyNotices=[current];vm.activeEmergencyNotice=current;vm.noticeAcking=true
  wait.resolve({});await call;assert.equal(vm.activeEmergencyNotice,current);assert.equal(vm.noticeAcking,true)
})
test('old account acknowledgement is discarded and showing the page clears its private context',async()=>{
  const wait=deferred();const {vm,component,switchAccount}=page({acknowledgeEmergencyNotice:()=>wait.promise,
    getInternship:async()=>({hasBatch:false}),getInternshipCompliance:async()=>({})})
  const rows=active(vm);const call=vm.acknowledgeEmergencyNotice();switchAccount();wait.resolve({});await call
  assert.equal(vm.activeEmergencyNotice,rows[0]);component.onShow.call(vm)
  assert.equal(vm.activeEmergencyNotice,null);assert.deepEqual(vm.pendingEmergencyNotices,[]);assert.equal(vm.selectedBatchId,'')
})
test('failed old reads cannot clear a newer popup',async()=>{
  const old=deferred();const {vm}=page({getPendingEmergencyNotices:()=>old.promise})
  const call=vm.loadEmergencyNotices();vm.selectedBatchId='2';vm.loadSequence++
  const current=notice('current');vm.activeEmergencyNotice=current;vm.pendingEmergencyNotices=[current]
  old.reject(Error('旧请求失败'));await call;assert.equal(vm.activeEmergencyNotice,current);assert.equal(vm.noticeError,'')
})
test('latest retry wins when two reads finish out of order',async()=>{
  const old=deferred(),latest=deferred();let calls=0
  const {vm}=page({getPendingEmergencyNotices:()=>++calls===1?old.promise:latest.promise})
  const a=vm.loadEmergencyNotices(),b=vm.loadEmergencyNotices();latest.resolve([notice('latest')]);await b
  old.resolve([notice('old')]);await a;assert.equal(vm.activeEmergencyNotice.id,'latest');assert.equal(vm.noticeLoading,false)
})
test('notice read failure preserves an existing popup and retry rereads server authority',async()=>{
  let fail=true;const {vm}=page({getPendingEmergencyNotices:async()=>{if(fail)throw Error('network');return []}})
  const rows=active(vm);await vm.loadEmergencyNotices();assert.equal(vm.activeEmergencyNotice,rows[0]);assert.match(vm.noticeError,/读取失败/)
  fail=false;await vm.loadEmergencyNotices();assert.equal(vm.activeEmergencyNotice,null);assert.equal(vm.noticeError,'')
})
test('hide invalidates in-flight notice reads without recording a receipt',async()=>{
  const wait=deferred();const {vm,component}=page({getPendingEmergencyNotices:()=>wait.promise})
  const call=vm.loadEmergencyNotices();component.onHide.call(vm);wait.resolve([notice(1)]);await call
  assert.equal(vm.activeEmergencyNotice,null);assert.equal(vm.noticeLoading,false)
})
test('an old dashboard cannot populate a new account or start its notice read',async()=>{
  const wait=deferred();let reads=0
  const {vm,switchAccount}=page({getInternship:()=>wait.promise,getInternshipCompliance:async()=>({}),getPendingEmergencyNotices:async()=>{reads++;return []}})
  const original=vm.i,call=vm.load();switchAccount();wait.resolve({hasBatch:true,batchId:'old'});await call
  assert.equal(vm.i,original);assert.equal(reads,0)
})
test('teacher failure keeps the active notice and clears only its own busy state',async()=>{
  const {vm}=page({acknowledgeInternshipEmergencyNotice:async()=>{throw Error('network')}},true)
  const rows=active(vm,true);await vm.acknowledgeActiveNotice();assert.equal(vm.activeNotice,rows[0]);assert.equal(vm.acknowledgingNotice,false);assert.equal(vm.noticeError,'操作未完成')
})
test('teacher late acknowledgement cannot clear a different batch popup',async()=>{
  const wait=deferred();const {vm}=page({acknowledgeInternshipEmergencyNotice:()=>wait.promise},true);active(vm,true)
  const call=vm.acknowledgeActiveNotice();vm.batchId='2';vm.loadSequence++
  const current=notice('current');vm.activeNotice=current;vm.pendingNotices=[current];vm.acknowledgingNotice=true
  wait.resolve({});await call;assert.equal(vm.activeNotice,current);assert.equal(vm.acknowledgingNotice,true)
})
test('teacher hide invalidates an acknowledgement response and reopening starts a fresh read',async()=>{
  const wait=deferred();const {vm,component}=page({acknowledgeInternshipEmergencyNotice:()=>wait.promise},true);const rows=active(vm,true)
  const call=vm.acknowledgeActiveNotice();component.onHide.call(vm);wait.resolve({});await call
  assert.equal(vm.activeNotice,rows[0]);let reads=0;vm.load=()=>reads++;component.onShow.call(vm);assert.equal(reads,1)
})
test('teacher account change clears the old notice, report and unsent form',async()=>{
  const {vm,switchAccount}=page({},true);active(vm,true);vm.form.workContent='旧教师私有正文';vm.reports=[{id:'old'}]
  switchAccount();vm.clearAccountContext();assert.equal(vm.activeNotice,null);assert.deepEqual(vm.reports,[]);assert.equal(vm.form.workContent,'')
})
test('student notice list ignores an old-account response',async()=>{
  const wait=deferred();const {vm,switchAccount}=page({getInternship:async()=>({batchId:batch}),getInternshipNotices:()=>wait.promise},false,'student-internship/notices/index.vue')
  const call=vm.load();await Promise.resolve();switchAccount();wait.resolve([notice('old')]);await call
  assert.deepEqual(vm.notices,[])
})
test('student notice list clears old private data before loading the next account',async()=>{
  const wait=deferred();const {vm,switchAccount}=page({getInternship:()=>wait.promise},false,'student-internship/notices/index.vue')
  vm.notices=[notice('old')];vm.requestedBatchId='old-batch';switchAccount();const call=vm.load()
  assert.deepEqual(vm.notices,[]);assert.equal(vm.requestedBatchId,'');wait.reject(Error('network'));await call;assert.equal(vm.state,'error')
})
test('the student home back destination is a registered standalone page',()=>{
  const source=fs.readFileSync(new URL('../src/pages/student-internship/index.vue',import.meta.url),'utf8')
  const fallback=source.match(/fallback-url="([^"]+)"/)[1].replace(/^\//,'')
  const routes=JSON.parse(fs.readFileSync(new URL('../src/pages.json',import.meta.url),'utf8')).pages.map(x=>x.path)
  assert.ok(routes.includes(fallback))
})
test('actual teacher SDK and activity page load notices without an invalid empty makeup filter',async()=>{
  const source=fs.readFileSync(new URL('../src/services/teacherApi.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const teacherApi','const teacherApi').replace('export default teacherApi','return teacherApi')
  const api=new Function('realRequest','sequential',source)(async raw=>{
    const url=new URL(raw,'http://example.test')
    if(url.pathname.endsWith('/makeups') && url.searchParams.has('status') && !url.searchParams.get('status')) throw Error('invalid status filter')
    if(url.pathname.endsWith('/emergency-notices/pending')) return [notice(1)]
    if(url.pathname.endsWith('/work-reports') || url.pathname.endsWith('/period-reports') || url.pathname.endsWith('/makeups')) return {items:[]}
    return []
  },{})
  const {vm}=page(api,true);await vm.load();assert.equal(vm.state,'ready');assert.equal(vm.activeNotice.id,'1')
})
test('teacher home notification receipt is explicit and a failed read retains the visible notice',async()=>{
  let fail=false,acks=0
  const {vm}=page({getPendingInternshipEmergencyNotices:async()=>{if(fail)throw Error('network');return [notice(1)]},acknowledgeInternshipEmergencyNotice:async()=>acks++},true,'../components/TeacherNoticeInbox.vue')
  await vm.refresh();assert.equal(acks,0);fail=true;await vm.refresh();assert.equal(vm.active.id,'1');assert.match(vm.error,/重新读取/)
  await vm.acknowledge();assert.equal(acks,1);assert.equal(vm.active,null)
})
test('teacher home notification ignores old batch and account responses',async()=>{
  const wait=deferred();const {vm,switchAccount}=page({getPendingInternshipEmergencyNotices:()=>wait.promise},true,'../components/TeacherNoticeInbox.vue')
  const call=vm.refresh();switchAccount();vm.batchId='new';wait.resolve([notice('old')]);await call;assert.equal(vm.active,null)
})
test('teacher home hiding fences a late acknowledgement and refresh rereads the receipt',async()=>{
  const wait=deferred();let reads=0
  const {vm}=page({getPendingInternshipEmergencyNotices:async()=>++reads===1?[notice(1)]:[],acknowledgeInternshipEmergencyNotice:()=>wait.promise},true,'../components/TeacherNoticeInbox.vue')
  await vm.refresh();const call=vm.acknowledge();vm.pause();wait.resolve({});await call;assert.equal(vm.active.id,'1')
  await vm.refresh();assert.equal(vm.active,null);assert.equal(vm.acking,false)
})
