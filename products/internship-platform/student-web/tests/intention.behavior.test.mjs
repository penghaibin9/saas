import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { compile, computed, createSSRApp, effectScope, h, reactive, ref, watch } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { INTERNSHIP_TABS as tabs } from '../src/platform/internshipNavigation.js'

const ctx={hasData:true,batchId:'9007199254741001',recordId:'9007199254741002',status:'READY'}
const record={id:'9007199254741003',recordId:ctx.recordId,batchId:ctx.batchId,version:0,status:'DRAFT',statusLabel:'草稿',preferredCity:'原城市',preferredIndustry:'原行业',intentionNote:'原意向说明',preferredPositionId:'9007199254741004',preferredPositionTitle:'原岗位',preferredCompanyName:'原企业'}
const response=(row=record,flags={canEdit:true,canSubmit:true,canWithdraw:false})=>({hasData:true,batchId:ctx.batchId,internshipId:ctx.recordId,intention:row?{...row}:null,readOnlyReason:'',...flags})
const later=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return {promise,resolve,reject}}
function page(t,overrides={}){
  let generation=1;const calls=[],route=reactive({query:{}}),document={hidden:false},session=reactive({user:{tenantId:'11',userId:'18',roleCode:'STUDENT'}})
  let current=response()
  const api={internshipIntentionMy:async()=>current,
    internshipIntentionSave:async body=>{calls.push(['save',body]);current=response({...record,...body,version:(body.expectedVersion??-1)+1});return current},
    internshipIntentionSubmit:async body=>{calls.push(['submit',body]);current=response({...current.intention,status:'SUBMITTED',statusLabel:'已提交',version:body.expectedVersion+1},{canEdit:true,canSubmit:false,canWithdraw:true});return current},
    internshipIntentionWithdraw:async body=>{calls.push(['withdraw',body]);current=response({...current.intention,status:'WITHDRAWN',statusLabel:'已撤回',version:body.expectedVersion+1},{canEdit:false,canSubmit:true,canWithdraw:false});return current},...overrides}
  const source=fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')
  const script=parse(source).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const deps={tabs,computed,reactive,ref,watch,onMounted(){},onBeforeUnmount(){},useUiStore:()=>({notify(){}}),useSessionStore:()=>session,useRoute:()=>route,useRouter:()=>({replace(){},push(){}}),currentSessionGeneration:()=>generation,sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},document,systemConfirm:async()=>true,fileSdk:{},internshipCoreApi:{},portalApi:api,...overrides.deps}
  const names=['my','tab','loading','sourceStates','intentionForm','intentionMeta','intentionFlags','intentionReason','intentionBusy','intentionError','intentionReceipt','intentionConflict','intentionLatest','intentionCommitted','intentionDirty','intentionCanEdit','intentionCanSubmit','intentionCanWithdraw','loadTab','resetSourceStates','saveIntention','submitIntention','withdrawIntention','continueIntentionAfterConflict','intentionVisibilityChanged']
  const scope=effectScope(),vm=scope.run(()=>new Function(...Object.keys(deps),script+'\nreturn {'+names.join(',')+'}')(...Object.values(deps)))
  vm.my.value={...ctx};vm.tab.value='intention';vm.loading.value=false
  const section=source.split('<!-- 岗位意向 -->')[1].split('<!-- 正式申请 -->')[0]
  const template=section.slice(section.indexOf('>')+1,section.lastIndexOf('</template>'))
  const Tag={props:['text'],setup:p=>()=>h('span',p.text)}
  const html=()=>renderToString(createSSRApp({components:{StatusTag:Tag},setup:()=>vm,render:compile(template)}))
  t.after(()=>scope.stop())
  return {vm,calls,html,document,session,logout:()=>generation++,setCurrent:value=>{current=value}}
}

test('意向读取失败不会显示未填写、可写表单或任何写动作',async t=>{
  const {vm,html,calls}=page(t,{internshipIntentionMy:async()=>{throw Error('暂时无法读取意向')}})
  await vm.loadTab('intention',true)
  assert.equal(vm.sourceStates.intention.status,'error');assert.equal(vm.intentionCanEdit.value,false)
  assert.doesNotMatch(await html(),/input|textarea|保存草稿|提交意向|尚未填写/)
  await vm.saveIntention();await vm.submitIntention();assert.deepEqual(calls,[])
})
test('意向原单保存保留岗位偏好，提交采用保存响应的新版本且保留字符串编号',async t=>{
  const {vm,calls,html}=page(t);await vm.loadTab('intention',true)
  vm.intentionForm.intentionNote='补充后的意向说明';await vm.submitIntention()
  assert.equal(calls[0][0],'save');assert.equal(calls[0][1].preferredPositionId,record.preferredPositionId)
  assert.equal(calls[0][1].expectedVersion,0);assert.equal(calls[0][1].internshipId,ctx.recordId)
  assert.deepEqual(calls[1],['submit',{batchId:ctx.batchId,internshipId:ctx.recordId,id:record.id,expectedVersion:1}])
  assert.equal(vm.intentionMeta.value.status,'SUBMITTED');assert.match(await html(),/保存更正/)
  assert.equal(vm.intentionCanEdit.value,true);assert.equal(vm.intentionCanSubmit.value,false)
})
test('新意向先保存，真实响应允许后再提交，不能把空状态推为可提交',async t=>{
  const p=page(t);p.setCurrent(response(null,{canEdit:true,canSubmit:false,canWithdraw:false}));await p.vm.loadTab('intention',true)
  assert.equal(p.vm.intentionCanEdit.value,true);assert.equal(p.vm.intentionCanSubmit.value,false)
  p.vm.intentionForm.preferredCity='新城市';await p.vm.saveIntention()
  assert.ok(!Object.hasOwn(p.calls[0][1],'id'));assert.equal(p.vm.intentionCanSubmit.value,true)
  await p.vm.submitIntention();assert.equal(p.calls[1][1].expectedVersion,0)
})
test('撤回后原单可重新提交，不能先保存覆盖撤回记录',async t=>{
  const p=page(t);p.setCurrent(response({...record,status:'WITHDRAWN',statusLabel:'已撤回',version:4},{canEdit:false,canSubmit:true,canWithdraw:false}));await p.vm.loadTab('intention',true)
  assert.match(await p.html(),/重新提交原意向/);assert.doesNotMatch(await p.html(),/<textarea/)
  await p.vm.submitIntention();assert.equal(p.calls.length,1);assert.equal(p.calls[0][0],'submit');assert.equal(p.calls[0][1].expectedVersion,4)
})
test('学校更正后的版本冲突保留输入，重读不采用，明确核对后才能用新版本',async t=>{
  let conflict=true
  const p=page(t,{internshipIntentionSave:async body=>{p.calls.push(['save',body]);if(conflict)throw {bizCode:'DATA_CONFLICT'};return response({...record,version:7,...body})}})
  await p.vm.loadTab('intention',true);p.vm.intentionForm.intentionNote='当前未提交文字';await p.vm.saveIntention()
  assert.equal(p.vm.intentionConflict.value,true);assert.equal(p.vm.intentionForm.intentionNote,'当前未提交文字')
  assert.equal(p.vm.intentionLatest.value,null);p.vm.continueIntentionAfterConflict()
  assert.equal(p.vm.intentionConflict.value,true);assert.equal(p.vm.intentionMeta.value.version,0);assert.equal(p.vm.intentionCanEdit.value,false)
  p.setCurrent(response({...record,version:6,intentionNote:'学校更正文字'}));await p.vm.loadTab('intention',true)
  assert.equal(p.vm.intentionMeta.value.version,0);assert.match(await p.html(),/学校更正文字/)
  p.vm.continueIntentionAfterConflict();assert.equal(p.vm.intentionMeta.value.version,6);assert.equal(p.vm.intentionForm.intentionNote,'当前未提交文字')
  conflict=false;await p.vm.saveIntention();assert.equal(p.calls.at(-1)[1].expectedVersion,6)
})
test('意向保存成功但回读失败时禁止重发，重新读到服务端后恢复允许动作',async t=>{
  let reads=0;const p=page(t,{internshipIntentionMy:async()=>{if(++reads===2)throw Error('回读失败');return response()}})
  await p.vm.loadTab('intention',true);await p.vm.saveIntention()
  assert.equal(p.vm.intentionCommitted.value,true);assert.match(p.vm.intentionError.value,/不必重复提交/)
  await p.vm.saveIntention();assert.equal(p.calls.length,1)
  await p.vm.loadTab('intention',true);assert.equal(p.vm.intentionCommitted.value,false)
})
test('缺失允许动作与历史实习不因空状态开放写入',async t=>{
  for(const flags of [{},{canEdit:false,canSubmit:false,canWithdraw:false}]){
    const p=page(t);p.setCurrent(response(null,flags));await p.vm.loadTab('intention',true)
    await p.vm.saveIntention();await p.vm.submitIntention();assert.deepEqual(p.calls,[])
  }
  const p=page(t);await p.vm.loadTab('intention',true);p.vm.my.value.historyMode=true
  await p.vm.saveIntention();assert.deepEqual(p.calls,[])
})
test('成功撤回和重新提交原单均保留尚未保存的输入，不能冒充已提交正文',async t=>{
  const p=page(t);p.setCurrent(response({...record,status:'SUBMITTED'},{canEdit:true,canSubmit:false,canWithdraw:true}));await p.vm.loadTab('intention',true)
  p.vm.intentionForm.intentionNote='保留的未提交补充';await p.vm.withdrawIntention()
  assert.equal(p.vm.intentionMeta.value.status,'WITHDRAWN');assert.equal(p.vm.intentionForm.intentionNote,'保留的未提交补充');assert.equal(p.vm.intentionDirty.value,true)
  await p.vm.submitIntention();assert.equal(p.vm.intentionMeta.value.status,'SUBMITTED');assert.equal(p.vm.intentionMeta.value.intentionNote,'原意向说明');assert.equal(p.vm.intentionForm.intentionNote,'保留的未提交补充')
  assert.deepEqual(p.calls.map(call=>call[0]),['withdraw','submit'])
})
test('切账号或批次后迟到意向不回填、不覆盖新读取状态',async t=>{
  const wait=later(),p=page(t,{internshipIntentionMy:()=>wait.promise});const pending=p.vm.loadTab('intention',true)
  p.logout();p.vm.resetSourceStates();p.vm.my.value={...ctx,batchId:'new',recordId:'new-record'};p.vm.intentionForm.preferredCity='新账号输入'
  wait.resolve(response());await pending
  assert.equal(p.vm.intentionMeta.value.id,undefined);assert.equal(p.vm.intentionForm.preferredCity,'新账号输入');assert.equal(p.vm.sourceStates.intention.status,'idle')
})
test('隐藏页面时旧确认失效，不发送撤回并保留未提交输入',async t=>{
  const confirm=later(),p=page(t,{deps:{systemConfirm:()=>confirm.promise}});p.setCurrent(response({...record,status:'SUBMITTED'},{canEdit:true,canSubmit:false,canWithdraw:true}));await p.vm.loadTab('intention',true)
  p.vm.intentionForm.intentionNote='未提交补充';const pending=p.vm.withdrawIntention();p.document.hidden=true;p.vm.intentionVisibilityChanged();confirm.resolve(true);await pending
  assert.deepEqual(p.calls,[]);assert.equal(p.vm.intentionForm.intentionNote,'未提交补充');assert.equal(p.vm.intentionBusy.value,false)
})

test('意向接口使用权威路径和上下文，未知状态/缺权限默认禁止，错误不显示内部英文',async()=>{
  const calls=[];let result=response();const source=fs.readFileSync(new URL('../src/services/portalApi.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const portalApi','const portalApi').replace('export default portalApi','return portalApi')
  const api=new Function('request',source)(async(path,options)=>{calls.push([path,options]);if(result instanceof Error)throw result;return result})
  await api.internshipIntentionMy({batchId:ctx.batchId,internshipId:ctx.recordId});await api.internshipIntentionSave({batchId:ctx.batchId,internshipId:ctx.recordId,id:record.id,expectedVersion:0})
  assert.match(calls[0][0],/^\/mobile\/internship\/context\/intention\?batchId=/);assert.equal(calls[1][1].method,'PUT');assert.equal(calls[1][1].body.expectedVersion,0)
  result=response({...record,status:'UNKNOWN_INTERNAL',intentionNote:'Keep customer English content'});const unknown=await api.internshipIntentionMy({batchId:ctx.batchId,internshipId:ctx.recordId})
  assert.equal(unknown.canEdit,false);assert.equal(unknown.intention.statusLabel,'状态待学校核对');assert.equal(unknown.intention.intentionNote,'Keep customer English content')
  result={...response(),batchId:'foreign'};await assert.rejects(()=>api.internshipIntentionMy({batchId:ctx.batchId,internshipId:ctx.recordId}),/意向暂时无法读取或保存/)
  result=Object.assign(Error('INTERNAL_PATH password'),{bizCode:'DATA_CONFLICT'});await assert.rejects(()=>api.internshipIntentionSubmit({batchId:ctx.batchId,internshipId:ctx.recordId,id:record.id,expectedVersion:0}),error=>error.bizCode==='DATA_CONFLICT' && /输入|内容/.test(error.message) && !/INTERNAL_PATH/.test(error.message))
})
