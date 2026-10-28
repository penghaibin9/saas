import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'
import { parse } from '@vue/compiler-sfc'
import { computed,effectScope,ref,reactive,watch } from 'vue'
import { INTERNSHIP_TABS as tabs } from '../src/platform/internshipNavigation.js'
const ctx={hasData:true,batchId:'9007199254741001',recordId:'9007199254741002',status:'ONBOARD'}
function page(t,overrides={}){
  let generation=1;const document={hidden:false},calls=[],rows=[]
  const api={internshipHelpMy:async()=>({items:rows.map(row=>({...row}))}),internshipHelp:async body=>{calls.push(body);const row={id:'9007199254741003',status:'PENDING_HANDLE',title:body.title,latestFeedback:body.content};rows.push(row);return row},...overrides}
  const deps={tabs,computed,ref,reactive,watch,onMounted(){},onBeforeUnmount(){},useRoute:()=>({query:{}}),useRouter:()=>({replace(){},push(){}}),useSessionStore:()=>({user:{tenantId:'1',userId:'2',roleCode:'STUDENT'}}),useUiStore:()=>({notify(){}}),currentSessionGeneration:()=>generation,sessionStorage:{getItem:()=>null,setItem(){},removeItem(){}},document,portalApi:api,internshipCoreApi:{},fileSdk:{}}
  const source=parse(fs.readFileSync(new URL('../src/views/internship/InternshipView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'')
  const names=['my','tab','loading','sourceStates','helpForm','helpRows','helpBusy','helpError','helpReceipt','helpCommitted','helpCanSubmit','submitHelp','loadTab','resetSourceStates','helpVisibilityChanged']
  const scope=effectScope(),vm=scope.run(()=>new Function(...Object.keys(deps),source+'\nreturn {'+names.map(n=>n+':typeof '+n+'==="undefined"?undefined:'+n).join(',')+'}')(...Object.values(deps)))
  vm.my.value={...ctx};vm.tab.value='help';vm.loading.value=false;t.after(()=>scope.stop());return {vm,calls,document,logout:()=>generation++}
}
test('电脑人工求助复用当前实习权威接口，并携带明确批次和实习原单',async()=>{
  const calls=[],source=fs.readFileSync(new URL('../src/services/portalApi.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const portalApi','const portalApi').replace('export default portalApi','return portalApi')
  const api=new Function('request',source)(async(path,options)=>{calls.push({path,options});return {items:[]}})
  await api.internshipHelp({batchId:ctx.batchId,internshipId:ctx.recordId,content:'合成求助说明'})
  assert.equal(calls[0].path,'/mobile/internship/context/help');assert.equal(calls[0].options.body.internshipId,ctx.recordId)
  await api.internshipHelpMy({batchId:ctx.batchId,internshipId:ctx.recordId});assert.match(calls[1].path,/batchId=.*&internshipId=/)
})
test('人工求助提交后回读同一原单，未办结时不能重复创建',async t=>{
  const {vm,calls}=page(t);await vm.loadTab('help',true);vm.helpForm.content='仅用于虚构学校核心流程走查';await vm.submitHelp()
  assert.equal(calls.length,1);assert.equal(calls[0].batchId,ctx.batchId);assert.equal(calls[0].internshipId,ctx.recordId)
  assert.equal(vm.helpRows.value[0].id,'9007199254741003');assert.equal(vm.helpReceipt.value.id,'9007199254741003');assert.equal(vm.helpCanSubmit.value,false)
  vm.helpForm.content='重复求助不应创建';await vm.submitHelp();assert.equal(calls.length,1)
})
test('读取失败或历史模式不开放求助写入，已提交回读失败不冒充失败重发',async t=>{
  const p=page(t,{internshipHelpMy:async()=>{throw Error('读取失败')}});await p.vm.loadTab('help',true);p.vm.helpForm.content='已有输入不能清空';await p.vm.submitHelp();assert.equal(p.calls.length,0);assert.equal(p.vm.helpForm.content,'已有输入不能清空')
  let reads=0;const q=page(t,{internshipHelpMy:async()=>{if(++reads>1)throw Error('回读失败');return {items:[]}}});await q.vm.loadTab('help',true);q.vm.helpForm.content='保存后回读失败测试';await q.vm.submitHelp();assert.equal(q.vm.helpCommitted.value,true);await q.vm.submitHelp();assert.equal(q.calls.length,1)
  const h=page(t);await h.vm.loadTab('help',true);h.vm.my.value.historyMode=true;h.vm.helpForm.content='历史仅可查看';await h.vm.submitHelp();assert.equal(h.calls.length,0)
})
test('旧账号或隐藏页面的迟到求助结果不清空新输入、不显示旧回执',async t=>{
  let resolve;const p=page(t,{internshipHelp:()=>new Promise(r=>resolve=r)});await p.vm.loadTab('help',true);p.vm.helpForm.content='旧账号待发送说明';const pending=p.vm.submitHelp();p.logout();p.vm.resetSourceStates();p.vm.helpForm.content='新账号未提交输入';resolve({id:'old',status:'PENDING_HANDLE'});await pending
  assert.equal(p.vm.helpForm.content,'新账号未提交输入');assert.equal(p.vm.helpReceipt.value,null)
})
