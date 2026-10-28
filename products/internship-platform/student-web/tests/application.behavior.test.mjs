import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, reactive, ref, watch } from 'vue'
import { INTERNSHIP_TABS as tabs } from '../src/platform/internshipNavigation.js'
import { scanState } from '../src/services/fileScanState.js'
import { internshipLeaveStage } from '../src/services/visibleEnumLocalization.js'
const ctx={hasData:true,batchId:'9007199254741001',recordId:'9007199254741002',status:'PREPARING'}
const base={id:'9007199254741003',version:3,applicationType:'SELF_ARRANGED',status:'REJECTED',reviewComment:'请补齐材料',companyName:'合成企业',companyCreditCode:'91310000MA1K000001',companyPrincipal:'负责人',companyScale:'小型',companyPhone:'13800138000',companyEmail:'test@example.invalid',companyNature:'民营企业',companyIndustry:'制造业',companyRegisteredAddress:'合成注册地址一号',companyProvince:'湖南省',companyCity:'益阳市',companyDistrict:'赫山区',companyPostalCode:'413000',contactName:'联系人',contactPhone:'13800138000',internshipDepartment:'技术部',positionName:'合成岗位',positionCategory:'信息技术',workContent:'真实合成工作内容',enterpriseMentorName:'带教老师',enterpriseMentorPhone:'13800138000',workCountry:'中国',workProvince:'湖南省',workCity:'益阳市',workDistrict:'赫山区',workAddress:'合成岗位地址一号',internshipStartDate:'2026-09-01',internshipEndDate:'2026-12-31',internshipMode:'自主实习',majorMatch:false,agreedSalary:0,evidenceFileId:'501',agreementFileIds:['502'],applicationNote:'合成自主实习申请说明'}
function page(t,overrides={},sdk={}){
  let generation=1;const scope=effectScope(),lifecycle={},session=reactive({user:{tenantId:'11',userId:'18'}}),document={hidden:false}
  const api={applications:async()=>[{...base}],positions:async context=>({items:[],total:0,page:1,hasMore:false,...context}),saveApplication:async body=>({...base,...body,version:4,status:'DRAFT'}),submitApplication:async()=>({...base,version:5,status:'PENDING_REVIEW'}),...overrides}
  const deps={tabs,computed,reactive,ref,watch,onMounted:fn=>lifecycle.mount=fn,onBeforeUnmount:fn=>lifecycle.unmount=fn,
    useUiStore:()=>({notify(){}}),useSessionStore:()=>session,sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},useRoute:()=>({query:{}}),useRouter:()=>({replace(){},push(){}}),currentSessionGeneration:()=>generation,
    portalApi:{},document,fileSdk:{metadata:async fileId=>({fileId,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,canDownload:true}),...sdk},scanState,scanFilesReady:files=>files.every(f=>f.readyForBusiness!==false),refreshScanFiles(){},fetchFileBlob(){},systemPrompt(){},systemConfirm:async()=>true,internshipCoreApi:api}
  const script=parse(fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const names=['sourceStates','appWritable','appPlaced','applicationHistoryOpen','insuranceMeta','insuranceProofBusy','insuranceProof','closeInsuranceProof','openInsuranceProof','my','tab','appForm','applications','openApplication','saveApplicationDraft','submitApplication','withdrawApplication','rereadApplication','adoptLatestApplication','appBase','appError','appConflict','appLatest','appFiles','appBusy','refreshApplicationFiles','uploadApplicationEvidence','resetSourceStates','applicationVisibilityChanged','appFields','downloadApplicationFile','loadApplications','loadMoreApplicationPositions','appPositions','appPositionsMore','appPositionsError','fetchTabSource','enterprises','enterpriseTotal']
  const vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {'+names.map(n=>`${n}:typeof ${n}==='undefined'?undefined:${n}`).join(',')+'}')(...Object.values(deps)))
  vm.my.value={...ctx};vm.tab.value='application';vm.sourceStates.application.status='data';t.after(()=>{lifecycle.unmount?.();scope.stop()})
  return {vm,document,logout:()=>generation++}
}
test('申请保存接口不重新读取或自动采纳最新版本',async()=>{
  const calls=[],source=fs.readFileSync(new URL('../src/services/internshipCoreApi.js',import.meta.url),'utf8').replace(/^import[^\n]*\n/gm,'').replace('export const internshipCoreApi','const internshipCoreApi').replace(/export default[^\n]*/g,'')
  const api=new Function('request','uploadFile',source+'\nreturn internshipCoreApi')(async(path,options)=>{calls.push({path,options});return options?{}:[{...base,version:9}]},()=>{})
  const body={batchId:ctx.batchId,internshipId:ctx.recordId,applicationType:'SELF_ARRANGED',content:'旧内容'}
  await api.saveApplication(body)
  assert.equal(calls.length,1);assert.equal(calls[0].options.method,'PUT');assert.equal(calls[0].options.body.expectedVersion,undefined)
})
test('申请源读取失败时保留输入但不开放写入，已落实学生仍能取得原申请历史',async t=>{
  let writes=0;const {vm}=page(t,{saveApplication:async()=>{writes++}});await vm.openApplication(base)
  vm.sourceStates.application.status='error';await vm.saveApplicationDraft();assert.equal(writes,0);assert.equal(vm.appForm.companyName,base.companyName);assert.equal(vm.appWritable.value,false)
  vm.my.value.status='ONBOARD';await vm.loadApplications();assert.equal(vm.appPlaced.value,true);assert.equal(vm.applications.value[0].id,base.id)
})
test('保险凭证读取中离开后可重试，旧请求不能释放或改写新操作',async t=>{
  let resolve,reads=0;const old=new Promise(r=>resolve=r),p=page(t,{}, {metadata:async()=>{reads++;return reads===1?old:{fileId:'proof',canDownload:false}}})
  p.vm.tab.value='insurance';p.vm.insuranceMeta.value={fileId:'proof',version:1};await Promise.resolve();const pending=p.vm.openInsuranceProof()
  p.vm.tab.value='overview';await Promise.resolve();assert.equal(p.vm.insuranceProofBusy.value,false)
  p.vm.tab.value='insurance';await Promise.resolve();await p.vm.openInsuranceProof();assert.equal(reads,2);resolve({fileId:'proof',canDownload:false});await pending;assert.equal(p.vm.insuranceProofBusy.value,false)
})
test('已办申请读取失败保持错误，重读成功后才可显示真实空状态',async t=>{
  let fail=true;const {vm}=page(t,{applications:async()=>{if(fail)throw Error('申请暂时读取失败');return []}});vm.my.value.status='ONBOARD'
  await assert.rejects(()=>vm.fetchTabSource('application'),/读取失败/);assert.match(vm.appError.value,/读取失败/)
  fail=false;await vm.fetchTabSource('application');assert.equal(vm.appError.value,'');assert.equal(vm.applications.value.length,0)
})
test('销假只在导师核实返岗后显示办结，不把学生登记当作终点',()=>{
  assert.equal(internshipLeaveStage({status:'RETURNED',returnAcknowledged:true}).label,'销假办结')
  assert.equal(internshipLeaveStage({status:'RETURNED',returnAcknowledged:false}).label,'待导师核实返岗')
  assert.equal(internshipLeaveStage({status:'RETURNED'}).label,'返岗确认待核对')
})
test('自主申请完整回填和原版保存保留零薪资、否对口与全部材料',async t=>{
  let sent;const {vm}=page(t,{saveApplication:async body=>{sent=body;return {...base,...body,version:4,status:'DRAFT'}}})
  await vm.openApplication(base);await vm.saveApplicationDraft()
  for(const key of ['companyCreditCode','companyEmail','companyProvince','workDistrict','enterpriseMentorPhone','internshipStartDate','internshipMode','workContent'])assert.equal(sent[key],base[key],key)
  assert.equal(sent.id,base.id);assert.equal(sent.expectedVersion,3);assert.equal(sent.agreedSalary,0);assert.equal(sent.majorMatch,false);assert.deepEqual(sent.agreementFileIds,['502'])
})
test('完整申请提交沿原编号和保存后的版本，退回意见保留并可按原版撤回',async t=>{
  const calls=[];const {vm}=page(t,{submitApplication:async(id,body)=>{calls.push({id,body});return {...base,status:'PENDING_REVIEW',version:5}},withdrawApplication:async(id,body)=>{calls.push({id,body});return {...base,status:'WITHDRAWN',version:6}}})
  await vm.openApplication(base);await vm.submitApplication()
  assert.equal(calls[0].id,base.id);assert.equal(calls[0].body.expectedVersion,4);assert.equal(vm.appBase.value.status,'PENDING_REVIEW')
  await vm.withdrawApplication();assert.equal(calls[1].body.expectedVersion,5);assert.equal(vm.appBase.value.status,'WITHDRAWN')
})
test('冲突保留全部旧输入和旧版本，回读不采用，明确确认后才换新版',async t=>{
  let sent;const newer={...base,version:9,companyName:'另一端更新企业',applicationNote:'另一端更新说明'}
  const {vm}=page(t,{saveApplication:async body=>{sent=body;throw {bizCode:'DATA_CONFLICT',status:409}},applications:async()=>[newer]})
  await vm.openApplication(base);vm.appForm.applicationNote='旧页面补正说明';await vm.saveApplicationDraft()
  assert.equal(sent.expectedVersion,3);assert.equal(vm.appBase.value.version,3);assert.equal(vm.appForm.applicationNote,'旧页面补正说明');assert.deepEqual(vm.appForm.agreementFileIds,['502']);assert.equal(vm.appConflict.value,true)
  await vm.rereadApplication();assert.equal(vm.appLatest.value.version,9);assert.equal(vm.appBase.value.version,3);assert.equal(vm.appForm.applicationNote,'旧页面补正说明')
  await vm.adoptLatestApplication();assert.equal(vm.appBase.value.version,9);assert.equal(vm.appForm.applicationNote,newer.applicationNote);assert.equal(vm.appConflict.value,false)
})
test('材料扫描未就绪及错编号都不保存，上传拒绝保留原材料',async t=>{
  let writes=0;const {vm}=page(t,{saveApplication:async()=>{writes++}}, {metadata:async fileId=>({fileId,status:'QUARANTINED',scanStatus:'PENDING',readyForBusiness:false}),upload:async()=>{throw {bizCode:'FILE_ZIP_REJECTED'}}})
  await vm.openApplication(base);await vm.saveApplicationDraft();assert.equal(writes,0);assert.equal(vm.appForm.evidenceFileId,'501');assert.equal(vm.appForm.applicationNote,base.applicationNote)
  await vm.uploadApplicationEvidence({target:{files:[{name:'拒绝.zip'}]}},'evidence');assert.equal(vm.appForm.evidenceFileId,'501');assert.match(vm.appError.value,/已拒绝/)
  const wrong=page(t,{saveApplication:async()=>{writes++}},{metadata:async()=>({fileId:'other',readyForBusiness:true})})
  await wrong.vm.openApplication(base);await wrong.vm.saveApplicationDraft();assert.equal(writes,0);assert.match(wrong.vm.appError.value,/编号不一致/)
})
test('离页后草稿保存迟到不能续发提交，会话变化不能回填新上下文',async t=>{
  let resolve,submits=0;const pending=new Promise(r=>resolve=r)
  const p=page(t,{saveApplication:()=>pending,submitApplication:async()=>{submits++}})
  await p.vm.openApplication(base);const writing=p.vm.submitApplication();await new Promise(r=>setImmediate(r));p.document.hidden=true;p.vm.applicationVisibilityChanged();resolve({...base,version:4,status:'DRAFT'});await writing
  assert.equal(submits,0);assert.equal(p.vm.appBase.value.version,3);assert.equal(p.vm.appConflict.value,true)
  let uploadResolve;const u=page(t,{}, {upload:()=>new Promise(r=>uploadResolve=r)})
  await u.vm.openApplication(base);const uploading=u.vm.uploadApplicationEvidence({target:{files:[{name:'旧材料.doc'}]}},'evidence');u.logout();u.vm.resetSourceStates();uploadResolve({fileId:'old',readyForBusiness:true});await uploading
  assert.equal(u.vm.appForm.evidenceFileId,'');assert.deepEqual(u.vm.appFiles.value,[])
})
test('申请材料下载逐次核对权限和编号，已提交及历史原单不会再次写入',async t=>{
  let writes=0,downloads=0,allowed=true
  const {vm}=page(t,{saveApplication:async()=>{writes++}}, {metadata:async fileId=>({fileId,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true,canDownload:allowed}),download:async()=>{downloads++}})
  await vm.openApplication({...base,status:'PENDING_REVIEW'});await vm.saveApplicationDraft();assert.equal(writes,0)
  await vm.downloadApplicationFile({fileId:'501'});assert.equal(downloads,1)
  allowed=false;await vm.downloadApplicationFile({fileId:'501'});assert.equal(downloads,1)
  vm.my.value.historyMode=true;await vm.submitApplication();assert.equal(writes,0)
})
test('完整提交前缺必填字段不会先保存破坏原草稿，回填审核意见不混入申请正文',async t=>{
  let writes=0;const {vm}=page(t,{saveApplication:async()=>{writes++}})
  await vm.openApplication(base);vm.appForm.companyCreditCode='';await vm.submitApplication()
  assert.equal(writes,0);assert.match(vm.appError.value,/信用代码/);assert.equal(vm.appBase.value.version,3)
  assert.equal(vm.appForm.applicationNote,base.applicationNote);assert.equal(vm.appBase.value.reviewComment,base.reviewComment)
  assert.deepEqual(vm.appForm.agreementFileIds,['502'])
})

test('电脑申请读取真实目录分页，刷新不覆盖未保存输入且失败不当空成功',async t=>{
  let fail=false;const calls=[];const {vm}=page(t,{positions:async(context,page=1)=>{calls.push({context,page});if(fail)throw new Error('真实岗位读取失败');return {...context,items:[{id:String(page),canSelect:true}],total:2,page,hasMore:page===1}}})
  vm.appForm.companyName='尚未保存的输入';await vm.loadApplications()
  assert.equal(vm.appForm.companyName,'尚未保存的输入');assert.equal(vm.appBase.value,null);assert.equal(vm.appPositionsMore.value,true)
  vm.appForm.positionId='1';fail=true;await vm.loadMoreApplicationPositions();assert.equal(vm.appPositions.value.length,1);assert.match(vm.appPositionsError.value,/真实岗位读取失败/)
  fail=false;await vm.loadMoreApplicationPositions();assert.deepEqual(vm.appPositions.value.map(row=>row.id),['1','2']);assert.equal(vm.appForm.positionId,'1');assert.equal(vm.appPositionsMore.value,false)
  assert.equal(calls[0].context.batchId,ctx.batchId);assert.equal(calls[0].context.internshipId,ctx.recordId)
  vm.tab.value='enterprises';await vm.fetchTabSource('enterprises');assert.equal(vm.enterprises.value[0].id,'1');assert.equal(vm.enterpriseTotal.value,2)
})

test('免实习原单回填专属字段、材料和退回版本，提交去学校审核',async t=>{
  const exemption={...base,applicationType:'EXEMPTION',exemptionType:'FURTHER_STUDY',exemptionDestination:'合成升学学校',exemptionReason:'已录取后按学校规则申请免实习',agreementFileIds:[],applicationNote:'原免实习原因'}
  const calls=[];const {vm}=page(t,{saveApplication:async body=>{calls.push(body);return {...exemption,...body,version:4,status:'DRAFT'}},submitApplication:async(id,body)=>{calls.push({id,...body});return {...exemption,version:5,status:'PENDING_REVIEW'}}})
  await vm.openApplication(exemption);assert.equal(vm.appForm.exemptionDestination,exemption.exemptionDestination)
  vm.appForm.exemptionReason='按学校退回意见补充录取和后续去向说明';await vm.submitApplication()
  assert.equal(calls[0].id,base.id);assert.equal(calls[0].expectedVersion,3);assert.equal(calls[0].applicationNote,vm.appForm.exemptionReason);assert.equal(calls[1].expectedVersion,4)
  assert.equal(vm.appBase.value.status,'PENDING_REVIEW')
})

test('免实习不完整及未扫描佐证均不得写，冲突保留专属原输入',async t=>{
  const exemption={...base,applicationType:'EXEMPTION',exemptionType:'HEALTH',exemptionDestination:'合成后续安排',exemptionReason:'合成申请原因不少于五字',agreementFileIds:[]}
  let writes=0;const {vm}=page(t,{saveApplication:async()=>{writes++;throw {status:409,bizCode:'DATA_CONFLICT'}}})
  await vm.openApplication(exemption);vm.appForm.exemptionDestination='';await vm.submitApplication();assert.equal(writes,0);assert.match(vm.appError.value,/去向/)
  vm.appForm.exemptionDestination='合成后续新去向';await vm.submitApplication();assert.equal(writes,1);assert.equal(vm.appForm.exemptionDestination,'合成后续新去向');assert.equal(vm.appBase.value.version,3);assert.equal(vm.appConflict.value,true)
  const pending=page(t,{saveApplication:async()=>{writes++}},{metadata:async fileId=>({fileId,readyForBusiness:false})})
  await pending.vm.openApplication(exemption);await pending.vm.submitApplication();assert.equal(writes,1);assert.equal(pending.vm.appForm.evidenceFileId,'501')
})

test('保险图片在页内显示，离开释放地址；错误凭证编号不得预览',async t=>{
  const p=page(t,{}, {metadata:async()=>({fileId:'proof',mimeType:'image/png',canPreview:true}),fetchPreviewBlob:async()=>new Blob(['synthetic'],{type:'image/png'})})
  p.vm.tab.value='insurance';await Promise.resolve();p.vm.insuranceMeta.value={fileId:'proof',version:1};await p.vm.openInsuranceProof()
  assert.equal(p.vm.insuranceProof.value.image,true);assert.match(p.vm.insuranceProof.value.url,/^blob:/)
  p.vm.tab.value='overview';await Promise.resolve();assert.equal(p.vm.insuranceProof.value,null)
  const wrong=page(t,{}, {metadata:async()=>({fileId:'foreign',mimeType:'image/png',canPreview:true}),fetchPreviewBlob:async()=>assert.fail('错编号不能读取文件')})
  wrong.vm.tab.value='insurance';await Promise.resolve();wrong.vm.insuranceMeta.value={fileId:'proof',version:1};await wrong.vm.openInsuranceProof();assert.equal(wrong.vm.insuranceProof.value,null)
})
