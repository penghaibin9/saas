import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { parse, compileScript, compileTemplate } from '@vue/compiler-sfc'
import { computed, reactive, ref, watch, effectScope, nextTick } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import * as profileModel from '../src/modules/internshipRecruitment/profileModel.js'
import * as materialModel from '../src/modules/internshipRecruitment/materialPreviewModel.js'
import * as volunteerModel from '../src/modules/internshipRecruitment/volunteerModel.js'
import * as submissionModel from '../src/modules/internshipRecruitment/submissionModel.js'
import * as selectionContract from '../src/modules/internshipRecruitment/selectionContract.js'
import * as contextModel from '../src/modules/internshipRecruitment/contextModel.js'
import { normalizePosition, conditionRows } from '../src/modules/internshipRecruitment/positionModel.js'
import { refreshScanFiles } from '../src/services/fileScanState.js'
import * as scopeModel from '../../shared/internshipSelectionScope.mjs'
const root=new URL('../src/',import.meta.url)
const source=file=>fs.readFileSync(new URL(file,root),'utf8')
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
const flush=async()=>{for(let i=0;i<8;i++){await Promise.resolve();await nextTick()}}
test('岗位劳动条件展示中文班次、明确不加班及零休息日',()=>{
  for (const days of [0,2]) {
    const rows=Object.fromEntries(conditionRows(normalizePosition({shiftType:'DAY',overtime:false,restDaysPerWeek:days})))
    assert.equal(rows['班次'],'白班');assert.equal(rows['加班安排'],'不安排加班');assert.equal(rows['休息日'],`每周 ${days} 天`)
  }
})
const profile=version=>({profile:{profileVersion:version,selfIntro:'本人专业实践介绍',strengths:'本人操作与协作优势'},schoolFacts:{realName:'合成学生'},items:[]})
function page(t,file,exposed,overrides={}){
  let generation=1;const unmount=[],events=[],scope=effectScope(),session=reactive({user:{tenantId:'1',userId:'2',roleCode:'STUDENT'}}),route=reactive({query:{batchId:'11'},params:{},path:'/internship/profile'}),routes=[]
  const api={profile:async()=>profile(4),profileCompleteness:async()=>({percent:100,readyToSubmit:true}),profilePreview:async()=>({previewHash:'hash',profileVersion:4,consentPolicyVersion:'school-policy'}),...overrides.api}
  const deps={computed,reactive,ref,watch,onMounted(){},onBeforeUnmount:fn=>unmount.push(fn),useRoute:()=>route,useRouter:()=>({push:value=>routes.push(value),replace:value=>{routes.push(value);route.query=value.query;route.path=value.path}}),useSessionStore:()=>session,currentSessionGeneration:()=>generation,sessionStorage:{getItem:()=>'',setItem(){}},systemConfirm:async()=>true,
    ...profileModel,...materialModel,...volunteerModel,...submissionModel,...selectionContract,...contextModel,normalizePosition,refreshScanFiles,
    internshipSelectionApi:{forScope:()=>api},api,portalApi:{internshipMy:async batch=>({hasData:true,batchId:batch||'11',recordId:'22',batchName:'合成批次'})},internshipCoreApi:{materialRequirements:async()=>[]},fileSdk:{},...overrides.deps}
  const script=parse(source(file)).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {'+exposed.join(',')+'}')(...Object.values(deps)))
  const close=()=>{unmount.splice(0).forEach(fn=>fn());scope.stop()};t.after(close)
  return {vm,session,route,routes,api,events,close,logout:()=>generation++}
}
test('正式路由保留招聘季与原单，大编号不经兜底或转换',async()=>{
  const script=source('router/index.js').replace(/^import[^\n]+\n/gm,'').replace('import.meta.env.BASE_URL',"'/'").replace('export default router','return router')
  const router=new Function('createRouter','createWebHistory','pinia','useSessionStore',script)(options=>createRouter({...options,routes:options.routes.map(row=>({...row,component:row.component?{render:()=>null}:undefined}))}),createMemoryHistory,{},()=>({restore:async()=>{},isLoggedIn:true,user:{}}))
  const query='?batchId=9007199254740993&campaignId=44&recordId=55'
  for(const target of ['/internship/selection','/internship/profile','/internship/selection/company/77','/internship/volunteer-result','/internship/compliance','/internship/materials']){
    await router.push(target+query);assert.equal(router.currentRoute.value.fullPath,target+query);assert.notEqual(router.currentRoute.value.matched[0].path,'/:pathMatch(.*)*')
  }
  const payload=selectionContract.buildVolunteerDraftPayload({batchId:'11',internshipId:'22',expectedGroupVersion:0,expectedRecordVersion:0,expectedApplicationVersions:{1:0,2:0,3:0},items:[{volunteerNo:1,positionId:'9007199254740993',applicationStatement:'申请这个岗位'}]})
  assert.equal(payload.items[0].positionId,'9007199254740993');assert.equal(payload.expectedGroupVersion,0)
  assert.throws(()=>selectionContract.buildVolunteerDraftPayload({...payload,items:[{volunteerNo:1,positionId:'1e3'}]}),/无效岗位/)
})
test('新接入页面及八个展示组件的真实导入均存在且可编译',()=>{
  const pages=['InternshipSelectionView','InternshipProfileView','EnterprisePublicView','InternshipVolunteerResultView','InternshipComplianceView','InternshipMaterialsView'].map(name=>'views/internship/'+name+'.vue')
  const components=['RecruitmentContextBar','PositionSearchFilters','PositionCard','PositionDetail','VolunteerBoard','VolunteerSubmissionPanel','MaterialSharePreview','EnterprisePublicProfile','InternshipProfileEditor'].map(name=>'components/recruitment/'+name+'.vue')
  for(const file of [...pages,...components]){
    const text=source(file),descriptor=parse(text,{filename:file});assert.deepEqual(descriptor.errors,[]);compileScript(descriptor.descriptor,{id:file});assert.deepEqual(compileTemplate({source:descriptor.descriptor.template.content,filename:file,id:file}).errors,[])
    for(const match of text.matchAll(/import[\s\S]*?from\s+['"]([^'"]+)['"]/g)){if(!match[1].startsWith('.'))continue;const target=new URL(match[1],new URL(file,root));assert.ok(['','.js','.vue','.mjs'].some(ext=>fs.existsSync(path.normalize(decodeURIComponent(target.pathname).replace(/^\/([A-Za-z]:)/,'$1'))+ext)),file+' 缺少 '+match[1])}
  }
})
test('选岗请求沿原批次招聘季记录，不写全局上下文',async()=>{
  const calls=[],scope={batchId:'11',campaignId:'33',recordId:'22'}
  const script=source('services/internshipSelectionApi.js').replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace(/export default internshipSelectionApi/g,'').replace(/export /g,'')
  const deps={...scopeModel,normalizeCatalogQuery:selectionContract.normalizeCatalogQuery,baseRequest:async(path,options)=>{calls.push({path,options});return {}}}
  const api=new Function(...Object.keys(deps),script+'\nreturn internshipSelectionApi')(...Object.values(deps)).forScope(scope)
  await api.context();await api.positions({page:2,keyword:'设备'});await api.profileCompleteness();await api.submitVolunteers({expectedGroupVersion:0})
  for(const call of calls){const url=new URL(call.path,'https://example.invalid');for(const key of Object.keys(scope))assert.equal(url.searchParams.get(key),scope[key])}
  assert.deepEqual(calls.at(-1).options.body,{...scope,expectedGroupVersion:0});assert.throws(()=>api.saveVolunteers({campaignId:'99'}),/不一致/)
})
const selectionNames=['loadContext','persistVolunteerSlots','prepareFinalSubmit','volunteerSlots','volunteerGroup','volunteerEditable','volunteerDraftDirty','volunteerError','submissionBusy','openResult','loadPositions','viewCompany','query','displayContext']

test('联系方式共享选项只采用当前招聘季的服务端策略',()=>{
  const preview=materialModel.normalizeMaterialPreview({materialPolicySnapshot:{allowedContactSharingModes:['MASKED_ONLY','AFTER_INTERVIEW']}})
  assert.deepEqual(preview.allowedContactSharingModes,['MASKED_ONLY','AFTER_INTERVIEW'])
  assert.ok(!preview.allowedContactSharingModes.includes('IMMEDIATE'))
  assert.deepEqual(materialModel.normalizeMaterialPreview().allowedContactSharingModes,['MASKED_ONLY'])
  assert.deepEqual(materialModel.normalizeMaterialPreview({allowedContactSharingModes:['UNKNOWN_INTERNAL']}).allowedContactSharingModes,[])
})
function selectionPage(t,api={}){const group={id:'31',version:0,recordVersion:0,batchId:'11',recordId:'22',status:'DRAFT',items:[{volunteerNo:1,positionId:'9007199254740993',positionName:'合成岗位',version:0}]};return page(t,'views/internship/InternshipSelectionView.vue',selectionNames,{api:{context:async()=>({catalogState:'AVAILABLE',campaignId:'33',campaignStatus:'OPEN',canSelect:true}),positions:async()=>({items:[],total:0}),volunteers:async()=>group,...api}})}
test('选岗摘要随本人志愿回读和保存更新，未提供的匹配统计不冒充零',async t=>{
  const p=selectionPage(t,{saveVolunteers:async body=>({id:'31',version:1,recordVersion:0,batchId:'11',recordId:'22',status:'DRAFT',items:body.items.map(item=>({...item,version:1,workLocation:'已保存的岗位地址'}))})})
  await p.vm.loadContext();assert.equal(p.vm.displayContext.value.selectedVolunteers,1)
  assert.equal(p.vm.displayContext.value.matchedPositions,null)
  const slots=volunteerModel.addVolunteer(p.vm.volunteerSlots.value,{id:'9007199254740994',title:'另一岗位',workLocation:'另一地址'})
  await p.vm.persistVolunteerSlots(slots)
  assert.equal(p.vm.displayContext.value.selectedVolunteers,2)
  assert.equal(p.vm.volunteerSlots.value[1].position.workLocation,'已保存的岗位地址')
  assert.equal(contextModel.normalizeRecruitmentContext({stats:{matchedPositions:0}}).matchedPositions,0)
})

test('志愿保存失败保留说明并禁止带未保存草稿投递，旧批次回执不回填',async t=>{
  const p=selectionPage(t,{saveVolunteers:async()=>{throw Error('保存暂不可用')}});await p.vm.loadContext();const proposed=p.vm.volunteerSlots.value.map(row=>({...row,applicationStatement:'失败时仍须保留的申请说明'}));await p.vm.persistVolunteerSlots(proposed)
  assert.equal(p.vm.volunteerSlots.value[0].applicationStatement,'失败时仍须保留的申请说明');assert.equal(p.vm.volunteerDraftDirty.value,true);await p.vm.prepareFinalSubmit();assert.equal(p.vm.submissionBusy.value,false)
  const pending=deferred(),q=selectionPage(t,{saveVolunteers:()=>pending.promise});await q.vm.loadContext();const saving=q.vm.persistVolunteerSlots(q.vm.volunteerSlots.value);q.route.query={batchId:'12'};await flush();pending.resolve({id:'old',version:1,items:[]});await saving;assert.notEqual(q.vm.volunteerGroup.value.id,'old')
  p.vm.openResult();assert.deepEqual(p.routes.at(-1),{path:'/internship/volunteer-result',query:{groupId:'31',groupVersion:'0'}})
})
const editorNames=['newItem','pendingFiles','fileError','addItem','refreshEvidence','uploadEvidence','filesReady','draft','profileDirty','save']
function editor(t,meta){const props=reactive({profile:profileModel.normalizeInternshipProfile(profile(4)),completeness:{percent:100,blockers:[],ready:true},items:[],busy:false,savedItemVersion:0}),events=[];const p=page(t,'components/recruitment/InternshipProfileEditor.vue',editorNames,{deps:{defineProps:()=>props,defineEmits:()=>((...args)=>events.push(args)),fileSdk:meta}});return {...p,props,events}}
test('档案附件待扫描不绑定，错编号不采纳，失败保留草稿，成功回执才清空',async t=>{
  let wrong=true;const p=editor(t,{metadata:async id=>({fileId:wrong?'999':id,status:'AVAILABLE',scanStatus:'CLEAN',readyForBusiness:true})})
  p.vm.newItem.title='本人实践';p.vm.newItem.description='失败仍保留';p.vm.pendingFiles.value=[{fileId:'9007199254740993',fileName:'证明.png',readyForBusiness:false}]
  p.vm.addItem();assert.equal(p.events.length,0);await p.vm.refreshEvidence();assert.match(p.vm.fileError.value,/不一致/);assert.equal(p.vm.pendingFiles.value[0].readyForBusiness,false)
  wrong=false;await p.vm.refreshEvidence();p.vm.addItem();assert.equal(p.events.length,1);assert.deepEqual(p.events[0][1].fileIds,['9007199254740993']);assert.equal(p.vm.newItem.title,'本人实践');assert.equal(p.vm.pendingFiles.value.length,1)
  p.props.savedItemVersion++;await nextTick();assert.equal(p.vm.newItem.title,'');assert.deepEqual(p.vm.pendingFiles.value,[])
})
const profileNames=['load','saveProfile','addItem','readLatest','acceptLatest','openEvidence','profile','items','error','actionError','conflict','committed','latestProfile']
test('档案写失败不隐藏编辑器，版本冲突只在本人明确核对后更新基线',async t=>{
  let version=4;const p=page(t,'views/internship/InternshipProfileView.vue',profileNames,{api:{profile:async()=>profile(version),updateProfile:async()=>{throw {bizCode:'DATA_CONFLICT',message:'学校档案已更新'}}}});await flush();await p.vm.saveProfile({expectedProfileVersion:4,selfIntro:'本次输入'})
  assert.equal(p.vm.error.value,'');assert.match(p.vm.actionError.value,/已更新/);assert.equal(p.vm.conflict.value,true);version=5;await p.vm.readLatest();assert.equal(p.vm.profile.value.version,4);p.vm.acceptLatest();assert.equal(p.vm.profile.value.version,5);assert.equal(p.vm.conflict.value,false)
})
test('档案证明查看逐次校验归属扫描权限，旧账号响应不触发下载',async t=>{
  const pending=deferred();let downloads=0;const p=page(t,'views/internship/InternshipProfileView.vue',profileNames,{deps:{fileSdk:{metadata:()=>pending.promise,download:()=>downloads++}}});await flush();p.vm.items.value=[{id:'1',fileIds:['51']}]
  await p.vm.openEvidence('999');assert.equal(downloads,0);const viewing=p.vm.openEvidence('51');p.logout();pending.resolve({fileId:'51',readyForBusiness:true,canDownload:true});await viewing;assert.equal(downloads,0)
})
const safetyNames=['load','selectCourse','startSafety','commitSafety','submitSafety','selectedBatchId','safetyCourses','courseDetail','loading','actionBlocked','canSubmitSafety','error','courseError']
function safetyPage(t,overrides={}){let completion=null;const writes=[];const course={id:'41',title:'合成安全课程',contentSnapshot:'识别风险，报告导师',contentHash:'school-hash',requiredMinutes:0,requireCommitment:true,remainingAttempts:3}
  const api={compliance:async(_op,batch)=>({hasData:true,batchId:batch,recordId:'22',passed:false,items:[]}),safetyCourses:async()=>[course],safetyCompletions:async()=>[],safetyDetail:async()=>({...course,completion:completion?{...completion}:null}),safetyStart:async id=>{writes.push(['start',id]);completion={id:'61',version:0,status:'IN_PROGRESS',studiedMinutes:0,startedAt:new Date().toISOString(),commitmentConfirmed:false}},safetyCommit:async(id,body)=>{writes.push(['commit',id,body]);completion={...completion,version:1,commitmentConfirmed:true}},safetySubmit:async(id,body)=>{writes.push(['submit',id,body]);completion={...completion,version:2,status:'PENDING_REVIEW'}},...overrides}
  return {...page(t,'views/internship/InternshipComplianceView.vue',safetyNames,{api}),writes,course}}
test('安全课程沿本人批次读取，零分钟仍先开始承诺再按原版提交并回读',async t=>{
  const p=safetyPage(t);await flush();await p.vm.selectCourse(p.course);assert.equal(p.vm.canSubmitSafety.value,false);await p.vm.startSafety();assert.equal(p.vm.canSubmitSafety.value,false);await p.vm.commitSafety();assert.equal(p.vm.canSubmitSafety.value,true);await p.vm.submitSafety()
  assert.deepEqual(p.writes.map(row=>row[0]),['start','commit','submit']);assert.equal(p.writes[1][2].expectedVersion,0);assert.equal(p.writes[1][2].contentHash,'school-hash');assert.equal(p.writes[2][2].expectedVersion,1);assert.equal(p.writes[2][2].studiedMinutes,0);assert.equal(p.vm.courseDetail.value.completion.status,'PENDING_REVIEW');assert.equal(p.vm.safetyCourses.value[0].completionStatus,'PENDING_REVIEW')
})
test('安全教育切批次拒绝旧课程与错编号正文，失效承诺弹框不写新身份',async t=>{
  const old=deferred(),p=safetyPage(t,{safetyDetail:()=>old.promise});await flush();const read=p.vm.selectCourse(p.course);p.route.query={batchId:'12'};await flush();old.resolve({...p.course,completion:null});await read;assert.equal(p.vm.selectedBatchId.value,'12');assert.equal(p.vm.courseDetail.value,null)
  const q=safetyPage(t,{safetyDetail:async()=>({id:'999'})});await flush();await q.vm.selectCourse(q.course);assert.equal(q.vm.courseDetail.value,null);assert.match(q.vm.courseError.value,/不一致/)
})
const materialNames=['load','items','draft','submit','readLatest','acceptLatest','upload','refreshFiles','ready','error','context']
function materialPage(t,overrides={}){const row={id:'71',batchId:'11',materialName:'盖章企业鉴定表',minFiles:1,maxFiles:2,allowedExtensions:['png'],version:1,submission:{id:'81',requirementId:'71',batchId:'11',internshipId:'22',version:3,status:'RETURNED',files:[],reviewComment:'请上传完整盖章页'}};const core={materialRequirements:async()=>[structuredClone(row)],...overrides};return {...page(t,'views/internship/InternshipMaterialsView.vue',materialNames,{deps:{internshipCoreApi:core}}),row,core}}
test('盖章鉴定表原单重交保留字符串文件和原版本，回读后转待审核',async t=>{
  const calls=[],p=materialPage(t,{submitMaterial:async(id,body)=>{calls.push({id,body});p.row.submission={...p.row.submission,version:4,status:'SUBMITTED',files:[{fileId:'9007199254740993'}]};return structuredClone(p.row.submission)}});await flush();const item=p.vm.items.value[0];p.vm.draft(item).files=[{fileId:'9007199254740993',readyForBusiness:true}];await p.vm.submit(item)
  assert.equal(calls.length,1);assert.equal(calls[0].body.expectedVersion,3);assert.deepEqual(calls[0].body.fileIds,['9007199254740993']);assert.equal(p.vm.items.value[0].submission.status,'SUBMITTED');assert.deepEqual(p.vm.draft(item).files,[])
})
test('材料冲突保留文件与旧版本，回读不自动采用；未扫描不提交',async t=>{
  let calls=0;const p=materialPage(t,{submitMaterial:async()=>{calls++;throw {bizCode:'DATA_CONFLICT',message:'原单版本变化'}}});await flush();const item=p.vm.items.value[0],d=p.vm.draft(item);d.files=[{fileId:'91',readyForBusiness:false}];await p.vm.submit(item);assert.equal(calls,0);d.files[0].readyForBusiness=true;await p.vm.submit(item);assert.equal(d.conflict,true);assert.equal(d.expectedVersion,3);p.row.submission.version=4;await p.vm.readLatest(item);assert.equal(d.expectedVersion,3);p.vm.acceptLatest(item);assert.equal(d.expectedVersion,4);assert.equal(d.files[0].fileId,'91')
})


test('安全承诺确认框待决时切换账号，旧确认不得发写请求',async t=>{
  const confirm=deferred();let writes=0;const course={id:'41',contentSnapshot:'安全学习正文',contentHash:'same',requiredMinutes:0,requireCommitment:true,completion:{id:'61',version:0,status:'IN_PROGRESS',commitmentConfirmed:false}}
  const p=page(t,'views/internship/InternshipComplianceView.vue',safetyNames,{api:{compliance:async()=>({hasData:true,batchId:'11',items:[]}),safetyCourses:async()=>[course],safetyCompletions:async()=>[],safetyDetail:async()=>course,safetyCommit:async()=>writes++},deps:{systemConfirm:()=>confirm.promise}})
  await flush();await p.vm.selectCourse(course);const committing=p.vm.commitSafety();p.logout();confirm.resolve(true);await committing;assert.equal(writes,0)
})


test('从岗位详情返回保留原查询页和关键词，档案缺项只显示中文业务要求',async t=>{
  const p=selectionPage(t);await p.vm.loadContext();await p.vm.loadPositions({page:2,pageSize:20,keyword:'设备',sort:'LATEST'});p.vm.viewCompany('77');const route=p.routes.at(-1);assert.equal(route.path,'/internship/selection/company/77');assert.equal(route.query.page,2);assert.equal(route.query.keyword,'设备');assert.equal(route.query.batchId,'11')
  const value=profileModel.normalizeProfileCompleteness({percent:40,blockers:['PROFILE_NOT_READY','profile.selfIntro','itemType.CERTIFICATE','minItemCount.2','UNKNOWN_INTERNAL']})
  assert.deepEqual(value.blockers,['请先保存实习档案','请填写自我介绍','请添加技能证书','请至少添加2项实践或证明材料','请按本次招聘季要求补充材料后重新核对'])
})
test('介绍未保存时不保存材料以免写后回读覆盖，先保存介绍保留原版本',async t=>{
  const p=editor(t,{});p.vm.newItem.title='本人实践证明';p.vm.draft.selfIntroduction='本次尚未保存的新介绍';assert.equal(p.vm.profileDirty.value,true);p.vm.addItem();assert.equal(p.events.length,0);p.vm.save();assert.equal(p.events[0][0],'save');assert.equal(p.events[0][1].expectedProfileVersion,4);assert.equal(p.events[0][1].selfIntro,'本次尚未保存的新介绍');assert.equal(p.vm.newItem.title,'本人实践证明')
})


test('企业公开资料只打开网页地址，内部脚本协议不得成为可点击入口',t=>{
  const props=reactive({company:{website:'javascript:alert(1)'}}),p=page(t,'components/recruitment/EnterprisePublicProfile.vue',['website'],{deps:{defineProps:()=>props}})
  assert.equal(p.vm.website.value,'');props.company.website='https://example.invalid/company';assert.equal(p.vm.website.value,'https://example.invalid/company');props.company.website='data:text/html,example';assert.equal(p.vm.website.value,'')
})
