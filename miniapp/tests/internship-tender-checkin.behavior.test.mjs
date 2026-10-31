import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import * as display from '../src/services/checkinPresentation.mjs'

const batch='9007199254740993101', record='9007199254740993102'
const dashboard={hasBatch:true,batchId:batch,recordId:record,checkin:{done:false}}
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve}}
function page(overrides={}) {
  let generation=1
  const messages=[],modals=[],calls=[]
  const api={getInternship:async requested=>{calls.push(['dashboard',requested]);return dashboard},
    getCheckinCalendar:async()=>({days:[]}),getCheckinExemptions:async()=>[],
    getCheckinPreflight:async(...args)=>{calls.push(['preflight',...args]);return {token:'synthetic-preflight',rule:{configured:false}}},
    submitCheckin:async body=>{calls.push(['save',body]);return {id:record,date:'2026-10-04',result:'RECORDED',message:'raw_private_error'}},...overrides}
  const uni={getLocation:options=>options.fail({errMsg:'location unavailable'}),showModal:options=>modals.push(options)}
  const source=fs.readFileSync(new URL('../src/pages/student-internship/checkin/index.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  const names=['studentApi','chooseSingleFile','uploadBusinessFile','toast','normalizeError','currentSessionGeneration','uni','ReportFilePreview','fileSdk',...Object.keys(display)]
  const presentation={...display,checkinLocationPolicy:overrides.locationPolicy || display.checkinLocationPolicy}
  const component=new Function(...names,script)(api,overrides.chooseSingleFile || (async()=>null),overrides.uploadBusinessFile || (async()=>null),x=>messages.push(x),e=>({kind:e?.bizCode==='DATA_CONFLICT'?'conflict':'unknown',text:'操作未完成，请重试'}),()=>generation,uni,{},overrides.fileSdk || {metadata:async fileId=>({fileId,readyForBusiness:true})},...Object.values(presentation))
  const vm={}
  for(const [name,method] of Object.entries(component.methods))vm[name]=(...args)=>method.apply(vm,args)
  Object.assign(vm,component.data.call(vm));vm.requestedBatch=batch;vm.i=dashboard;vm.state='ready'
  return {vm,component,api,uni,messages,modals,calls,switchAccount:()=>generation++}
}
const settle=()=>new Promise(resolve=>setImmediate(resolve))

const exemption={id:'9007199254740993211',version:3,status:'REJECTED',statusLabel:'已驳回',startDate:'2026-10-14',endDate:'2026-10-14',reason:'虚构原免签理由不少于五字',evidenceFileId:'',reviewComment:'请沿原申请补正'}
test('免签补正沿原编号与版本提交，原教师意见不混入正文',async()=>{
 let sent;const p=page({applyCheckinExemption:async body=>{sent=body;return {...exemption,status:'PENDING',version:4}}})
 p.vm.editExemption(exemption);p.vm.exemptionForm.reason='按教师意见补充原免签安排说明';await p.vm.submitExemption()
 assert.equal(sent.id,exemption.id);assert.equal(sent.expectedVersion,3);assert.equal(sent.batchId,batch);assert.equal(sent.internshipId,record);assert.equal(sent.reason,'按教师意见补充原免签安排说明');assert.equal(p.vm.exemptionBase,null)
})
test('免签扫描未就绪不写，失败保留原理由、原版本及材料',async()=>{
 let writes=0;const p=page({applyCheckinExemption:async()=>{writes++},fileSdk:{metadata:async fileId=>({fileId,readyForBusiness:false})}})
 p.vm.editExemption({...exemption,evidenceFileId:'proof'});await p.vm.submitExemption()
 assert.equal(writes,0);assert.equal(p.vm.exemptionForm.evidenceFileId,'proof');assert.equal(p.vm.exemptionBase.version,3);assert.match(p.vm.exemptionError,/安全检查/)
})
test('免签冲突回读不自动换版本，明确采用原单后才恢复修改',async()=>{
 const p=page({applyCheckinExemption:async()=>{throw {bizCode:'DATA_CONFLICT'}},getCheckinExemptions:async()=>[{...exemption,version:9,reason:'另一端最新补正理由'}]})
 p.vm.editExemption(exemption);p.vm.exemptionForm.reason='本端未保存的补正理由';await p.vm.submitExemption();await p.vm.rereadExemption()
 assert.equal(p.vm.exemptionConflict,true);assert.equal(p.vm.exemptionBase.version,3);assert.equal(p.vm.exemptionForm.reason,'本端未保存的补正理由');assert.equal(p.vm.exemptionLatest.version,9)
 p.vm.adoptExemption();assert.equal(p.vm.exemptionBase.version,9);assert.equal(p.vm.exemptionForm.reason,'另一端最新补正理由')
})
test('免签上传中离页及旧会话迟到保存，不回填原材料或清新输入',async()=>{
 const upload=deferred(),p=page({chooseSingleFile:async()=>({name:'proof.png'}),uploadBusinessFile:()=>upload.promise})
 p.vm.editExemption(exemption);const work=p.vm.pickExemptionEvidence();await settle();p.vm.pause();upload.resolve({fileId:'late',readyForBusiness:true});await work
 assert.equal(p.vm.exemptionForm.evidenceFileId,'');assert.equal(p.vm.exemptionConflict,true)
 const save=deferred(),q=page({applyCheckinExemption:()=>save.promise});q.vm.editExemption(exemption);const writing=q.vm.submitExemption();await settle();q.switchAccount();save.resolve({id:exemption.id,version:4});await writing
 assert.equal(q.vm.exemptionForm.reason,exemption.reason);assert.equal(q.vm.exemptionBase.version,3)
})

test('日历照片使用当前日期的正式编号，不能借按钮参数换成其他文件',async()=>{
  const p=page(),opened=[]
  p.vm.$refs={checkinPreview:{open:async file=>opened.push(file),reset(){}}}
  p.vm.calendarDays=[{date:'2026-10-04',photoFileId:batch,watermarkedFileId:record}]
  await p.vm.openPhoto({date:'2026-10-04',photoFileId:'foreign'},true)
  await p.vm.openPhoto({date:'2026-10-04'},false)
  assert.deepEqual(opened.map(file=>file.fileId),[batch,record])
  await p.vm.openPhoto({date:'2026-10-05',photoFileId:'foreign'},true)
  assert.equal(opened.length,2)
})

test('隐藏、旧账号和未就绪的日历不能打开照片，离开页面关闭已有预览',async()=>{
  const p=page();let opened=0,closed=0
  p.vm.$refs={checkinPreview:{open:async()=>opened++,reset:()=>closed++}}
  const day={date:'2026-10-04',photoFileId:batch};p.vm.calendarDays=[day]
  p.vm.pause();await p.vm.openPhoto(day,true);assert.equal(opened,0);assert.equal(closed,1)
  p.vm.hidden=false;p.switchAccount();await p.vm.openPhoto(day,true);assert.equal(opened,0)
})

test('重新读取日历会清除上一次照片预览',async()=>{
  const p=page();let closed=0
  p.vm.$refs={checkinPreview:{reset:()=>closed++}}
  await p.vm.load();assert.equal(closed,1)
})

test('真实签到回执才显示励志弹窗，无围栏留痕不能冒充围栏验证通过',async()=>{
  const p=page();p.vm.checkinNote='合成测试备注';await p.vm.beginCheckin();await settle()
  assert.equal(p.modals.length,1);assert.match(p.modals[0].content,/积累/);assert.match(p.modals[0].content,/未配置围栏/)
  assert.equal(p.modals[0].showCancel,false);assert.ok(!p.modals[0].content.includes('raw_private_error'))
  const body=p.calls.find(c=>c[0]==='save')[1];assert.equal(body.batchId,batch);assert.equal(body.note,'合成测试备注');assert.equal(p.vm.checkinNote,'')
})
test('定位异常回执显示已记录待核验，不把接口成功当正常签到',async()=>{
  const p=page({submitCheckin:async()=>({id:record,date:'2026-10-04',result:'NO_LOCATION'})});await p.vm.beginCheckin();await settle()
  assert.match(p.modals[0].title,/待核验/);assert.match(p.modals[0].content,/无定位/)
})
test('写请求失败或缺少正式回执不弹励志语句，保留备注和照片',async()=>{
  for(const response of [()=>Promise.reject(Error('raw_private_error')),async()=>({result:'NORMAL'}),async()=>({id:record,date:'2026-10-04',result:'FUTURE_INTERNAL_STATUS'})]) {
    const p=page({submitCheckin:response});p.vm.checkinNote='仍需提交';await p.vm.beginCheckin();await settle()
    assert.equal(p.modals.length,0);assert.equal(p.vm.checkinNote,'仍需提交');assert.equal(p.vm.checkingIn,false);assert.ok(p.messages.every(m=>!m.includes('raw_private_error')))
  }
})
test('重新读取失败不抹掉已经成功保存的签到回执',async()=>{
  const p=page({getInternship:async()=>{throw Error('raw_private_error')}});await p.vm.beginCheckin();await settle()
  assert.equal(p.modals.length,1);assert.equal(p.vm.state,'error');assert.ok(p.messages.every(m=>!m.includes('raw_private_error')))
})
test('指定批次加载和预检使用同一批次，其他批次返回不能覆盖上下文',async()=>{
  const p=page();await p.vm.load();assert.deepEqual(p.calls[0],['dashboard',batch]);
  p.api.getInternship=async()=>({...dashboard,batchId:'another-batch'});await p.vm.load();assert.equal(p.vm.i,null);assert.equal(p.vm.state,'error')
})
test('切换账号后的迟到预检及定位结果不能发起旧学生签到',async()=>{
  const wait=deferred(),p=page({getCheckinPreflight:()=>wait.promise});const pending=p.vm.beginCheckin();p.switchAccount();wait.resolve({token:'old',rule:{}});await pending;await settle();assert.equal(p.calls.filter(c=>c[0]==='save').length,0)
  const q=page();let locate;q.uni.getLocation=options=>locate=options;await q.vm.beginCheckin();q.switchAccount();locate.success({latitude:30,longitude:110,accuracy:10});await settle();assert.equal(q.calls.filter(c=>c[0]==='save').length,0)
})
test('隐藏页面后的迟到保存不回填旧资料、不弹成功、不清掉新备注',async()=>{
  const wait=deferred(),p=page({submitCheckin:()=>wait.promise});await p.vm.beginCheckin();p.component.onHide.call(p.vm);p.vm.checkinNote='新草稿';wait.resolve({id:record,date:'2026-10-04',result:'NORMAL'});await settle()
  assert.equal(p.modals.length,0);assert.equal(p.vm.checkinNote,'新草稿')
})
test('重复点击正在签到时只发送一次预检和提交',async()=>{
  const wait=deferred(),p=page({submitCheckin:()=>{p.calls.push(['save']);return wait.promise}});await p.vm.beginCheckin();await p.vm.beginCheckin();assert.equal(p.calls.filter(c=>c[0]==='preflight').length,1);assert.equal(p.calls.filter(c=>c[0]==='save').length,1);wait.resolve({id:record,date:'2026-10-04',result:'NORMAL'});await settle()
})
test('日历未知状态用中文，异常状态明确待核验，原始数据不透传',()=>{
  assert.equal(display.checkinCalendarLabel('NEW_INTERNAL_STATUS'),'状态待确认');assert.equal(display.checkinCalendarLabel('MOCK_LOCATION'),'待核验')
  assert.equal(display.checkinCalendarLabel('FUTURE'),'');assert.equal(display.checkinCalendarLabel('MAKEUP'),'补卡')
})
test('签到确认用中文业务按钮，取消时不请求定位或写入',()=>{
  const p=page();p.vm.checkin();assert.equal(p.modals.length,1);assert.equal(p.modals[0].confirmText,'确认签到');assert.equal(p.modals[0].cancelText,'暂不签到');p.modals[0].success({confirm:false});assert.equal(p.calls.length,0)
})

test('网页原生坐标如实提交国际坐标，微信国内坐标和海外选择保持准确标识',async()=>{
  for(const [overseas,browser,type,coordinateSystem,provider] of [
    [false,true,'wgs84','WGS84','BROWSER_WGS84'],[false,false,'gcj02','GCJ02','UNI_GCJ02'],[true,false,'wgs84','WGS84','UNI_WGS84']
  ]) {
    const p=page({locationPolicy:value=>display.checkinLocationPolicy(value,browser)});p.vm.overseas=overseas
    p.uni.getLocation=options=>{assert.equal(options.type,type);options.success({latitude:28.2282,longitude:112.9388,accuracy:15})}
    await p.vm.beginCheckin();await settle()
    const body=p.calls.find(c=>c[0]==='save')[1]
    assert.equal(body.coordinateSystem,coordinateSystem);assert.equal(body.locationProvider,provider);assert.equal(body.lat,28.2282);assert.equal(body.gpsAccuracy,15)
  }
})

test('拍照或上传后切换账号、离开页面，迟到照片不能回填或开始上传',async()=>{
  for(const unload of [false,true]) {
    let choice,uploads=0
    const p=page({uploadBusinessFile:async()=>{uploads++;return {fileId:'old-photo'}}});p.uni.chooseImage=options=>choice=options
    p.vm.capturePhoto();unload?p.component.onUnload.call(p.vm):p.switchAccount()
    await choice.success({tempFilePaths:['synthetic.jpg']});assert.equal(uploads,0);assert.equal(p.vm.photoFileId,'')
  }
  const wait=deferred(),p=page({uploadBusinessFile:()=>wait.promise});let choice;p.uni.chooseImage=options=>choice=options
  p.vm.capturePhoto();const pending=choice.success({tempFilePaths:['synthetic.jpg']});p.switchAccount();p.vm.resetAccount();p.vm.photoFileId='new-photo'
  wait.resolve({fileId:'old-photo'});await pending;assert.equal(p.vm.photoFileId,'new-photo')
})

test('打开相机导致暂时隐藏页面，不误判为更换账号',async()=>{
  const p=page({uploadBusinessFile:async()=>({fileId:'synthetic-photo',fileName:'合成测试照片'})});let choice;p.uni.chooseImage=options=>choice=options
  p.vm.capturePhoto();p.component.onHide.call(p.vm);await choice.success({tempFilePaths:['synthetic.jpg']})
  assert.equal(p.vm.photoFileId,'synthetic-photo');assert.equal(p.vm.photoUploading,false)
})

test('异常页返回使用统一学生系统师生入口，自定义返回仍优先',()=>{
  const source=fs.readFileSync(new URL('../src/components/MobileGlobalState.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let route,destination,emitted
  const component=new Function('back','relaunch','getCurrentPages',script)(url=>destination=url,()=>{},()=>[{route}])
  for(const [current,expected] of [['pages/student-internship/checkin/index','/pages/student/home/index'],['pages/teacher-internship/internship-students/index','/pages/teacher/workbench/index'],['pages/login/index','/pages/login/index']]) {
    route=current;component.methods.goBack.call({});assert.equal(destination,expected)
  }
  component.methods.goBack.call({$:{vnode:{props:{onBack:()=>{}}}},$emit:event=>emitted=event});assert.equal(emitted,'back')
})
