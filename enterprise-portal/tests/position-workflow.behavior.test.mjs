import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { computed, effectScope, nextTick, reactive, ref, watch } from 'vue'
import { positionListQuery } from '../src/services/positionNavigation.js'

const deferred=()=>{let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no});return {promise,resolve,reject}}
const complete={title:'虚构设备调试岗位',headcount:3,workLocation:'虚构地区',workAddress:'虚构地址',workContent:'导师指导下协助调试',weeklyHours:40,salaryRange:'3000元/月'}
function mount(t,api={},routeId='',query={}) {
  const scope=effectScope(),route=reactive({params:routeId?{id:routeId}:{},query}),context=reactive({campaign:{id:'2'},recruitmentContextReady:true,recruitmentWritable:true})
  const handlers={},navigations=[]
  const router={
    async replace(target){
      if(target.path){const match=target.path.match(/\/positions\/([^/]+)\/edit$/);const to={params:match?{id:match[1]}:{}};if(handlers.update&&!(await handlers.update(to,route)))return;navigations.push(target);route.params=to.params}
      if(target.query)route.query=target.query
    },
    async push(target){assert.equal(await handlers.leave(),true,'successful save must be allowed to navigate');navigations.push(target)},
  }
  const script=parse(fs.readFileSync(new URL('../src/views/PositionFormView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+'\nreturn {id,form,load,save,withdraw,reload,canEdit,canWithdraw,needsReload,createUncertain,notice,error,dirty,positionVersion,positionStatus,returnLocation,leaveDialog,finishLeave,schoolReturn}'
  const vm=scope.run(()=>new Function('computed','nextTick','onBeforeUnmount','onMounted','reactive','ref','watch','onBeforeRouteLeave','onBeforeRouteUpdate','useRoute','useRouter','enterpriseInternshipApi','useEnterpriseContextStore','positionListQuery','document','window',script)(computed,nextTick,fn=>{handlers.unmount=fn},()=>{},reactive,ref,watch,fn=>{handlers.leave=fn},fn=>{handlers.update=fn},()=>route,()=>router,api,()=>context,positionListQuery,{getElementById:()=>null},{addEventListener(){},removeEventListener(){}}))
  vm.leaveDialog.value={showModal(){},close(){}}
  t.after(()=>{handlers.unmount();scope.stop()})
  return {vm,route,context,navigations,handlers}
}

test('new draft identity survives submit failure; retry updates and submits the same record',async t=>{
  const calls=[];let submits=0
  const {vm,route,navigations}=mount(t,{
    createPosition:async body=>{calls.push(['create',body]);return {id:'901',version:1,status:'DRAFT'}},
    updatePosition:async(id,body)=>{calls.push(['update',id,body.expectedVersion]);return {id,version:2,status:'DRAFT'}},
    submitPosition:async(id,version)=>{calls.push(['submit',id,version]);if(++submits===1)throw Object.assign(new Error('当前不可提交'),{status:400});return {id,version:3,status:'PENDING'}},
  },'',{page:'3',status:'DRAFT',q:'设备',section:'pay'})
  await vm.load();Object.assign(vm.form,complete);await vm.save(true)
  assert.equal(vm.id.value,'901');assert.equal(route.params.id,'901');assert.equal(vm.dirty.value,false);assert.equal(vm.canEdit.value,true)
  assert.match(vm.notice.value,/草稿已保存/);assert.equal(calls.filter(c=>c[0]==='create').length,1)
  await vm.save(true)
  assert.deepEqual(calls.map(c=>c.slice(0,3)),[['create',calls[0][1]],['submit','901',1],['update','901',1],['submit','901',2]])
  assert.deepEqual(navigations.at(-1),{path:'/positions',query:{status:'DRAFT',q:'设备',page:'3',campaignId:'2'}})
})

test('ambiguous create response stops another create until the user checks the list',async t=>{
  let creates=0
  const {vm}=mount(t,{createPosition:async()=>{creates++;throw Object.assign(new Error('网络不可达'),{network:true})}})
  await vm.load();Object.assign(vm.form,complete);await vm.save();await vm.save();await vm.load()
  assert.equal(creates,1);assert.equal(vm.createUncertain.value,true);assert.equal(vm.canEdit.value,false)
})

test('known creation with missing version retains its ID and recovers through detail instead of recreating',async t=>{
  let creates=0,reads=0
  const {vm,route}=mount(t,{createPosition:async()=>{creates++;return {id:'902'}},position:async id=>{reads++;return {...complete,id,version:1,status:'DRAFT'}}})
  await vm.load();Object.assign(vm.form,complete);await vm.save()
  assert.equal(vm.id.value,'902');assert.equal(vm.needsReload.value,true)
  await vm.load()
  assert.equal(creates,1);assert.equal(reads,1);assert.equal(route.params.id,'902');assert.equal(vm.canEdit.value,true)
})

test('duplicate save is ignored and a late creation cannot navigate another object',async t=>{
  const pending=deferred();let creates=0
  const {vm,route,navigations}=mount(t,{createPosition:()=>{creates++;return pending.promise},position:async id=>({...complete,id,title:'另一岗位',version:5,status:'PUBLISHED'})})
  await vm.load();Object.assign(vm.form,complete)
  const first=vm.save();await vm.save();route.params={id:'777'};await nextTick();await nextTick()
  pending.resolve({id:'901',version:1,status:'DRAFT'});await first
  assert.equal(creates,1);assert.equal(vm.form.title,'另一岗位');assert.equal(vm.id.value,'777');assert.deepEqual(navigations,[])
})

test('late detail errors cannot overwrite a new route',async t=>{
  const pending=deferred()
  const {vm,route}=mount(t,{position:id=>id==='101'?pending.promise:Promise.resolve({...complete,id,version:3,status:'PENDING'})},'101')
  const first=vm.load();route.params={id:'102'};await nextTick();await nextTick();pending.reject(new Error('旧失败'));await first
  assert.equal(vm.id.value,'102');assert.equal(vm.positionStatus.value,'PENDING');assert.equal(vm.error.value,'')
})

test('wrong campaign and historical records cannot issue writes',async t=>{
  let reads=0,writes=0
  const {vm,route,context}=mount(t,{position:async id=>{reads++;return {...complete,id,version:1,status:'DRAFT'}},updatePosition:()=>writes++},'101',{campaignId:'999'})
  await vm.load();assert.equal(reads,0);assert.equal(vm.canEdit.value,false)
  route.query={campaignId:'2'};await vm.load();context.recruitmentWritable=false
  await vm.save();assert.equal(writes,0);assert.equal(vm.canEdit.value,false)
})

test('conflict preserves input and prevents blind version retries',async t=>{
  let writes=0
  const {vm}=mount(t,{position:async id=>({...complete,id,version:3,status:'DRAFT'}),updatePosition:async()=>{writes++;throw Object.assign(new Error('版本已变化'),{status:409})}},'101')
  await vm.load();vm.form.title='保留我的修改';await vm.save();await vm.save()
  assert.equal(vm.form.title,'保留我的修改');assert.equal(vm.positionVersion.value,3);assert.equal(vm.needsReload.value,true);assert.equal(writes,1)
})

test('dirty form asks before leaving; cancel retains edits and discard permits navigation',async t=>{
  const {vm,handlers}=mount(t)
  await vm.load();vm.form.title='尚未保存'
  const cancel=handlers.leave();vm.finishLeave(false);assert.equal(await cancel,false);assert.equal(vm.form.title,'尚未保存')
  const discard=handlers.leave();vm.finishLeave(true);assert.equal(await discard,true)
})

test('draft count validation prevents invalid writes without requiring all submission materials',async t=>{
  let writes=0
  const {vm}=mount(t,{createPosition:async()=>{writes++;return {id:'901',status:'DRAFT',version:1}}})
  await vm.load();vm.form.title='虚构草稿'
  for(const count of [null,0,-1,1.5,100001]){vm.form.headcount=count;await vm.save();assert.equal(writes,0)}
  vm.form.headcount=1;await vm.save();assert.equal(writes,1)
})

test('changing campaign in the URL cannot silently discard unsaved form input',async t=>{
  const {vm,handlers,route}=mount(t,{},'',{campaignId:'2'})
  await vm.load();vm.form.title='保留修改'
  const leaving=handlers.update({params:{},query:{campaignId:'3'}},route)
  vm.finishLeave(false);assert.equal(await leaving,false);assert.equal(vm.form.title,'保留修改')
})

test('list query keeps usable return filters and drops detail and invalid scope values',()=>{
  assert.deepEqual(positionListQuery({status:'PENDING',q:'  设备  ',page:'3',campaignId:'23',section:'pay',companyId:'99'}),{status:'PENDING',q:'设备',page:'3',campaignId:'23'})
  assert.deepEqual(positionListQuery({status:'NOPE',page:'-1',campaignId:['23']}),{})
})

function list(t,api={},query={}) {
  const scope=effectScope(),route=reactive({query}),context=reactive({campaign:{id:'2'},recruitmentContextReady:true,recruitmentWritable:true})
  const routes=[],handlers={}
  const router={replace:async target=>{route.query=target.query},push:async target=>routes.push(target)}
  const script=parse(fs.readFileSync(new URL('../src/views/PositionListView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+'\nreturn {load,positionLocation,withdrawAndEdit,items,active,keyword,page,error}'
  const vm=scope.run(()=>new Function('computed','ref','watch','onMounted','onBeforeUnmount','useRoute','useRouter','useEnterpriseContextStore','enterpriseInternshipApi','positionListQuery',script)(computed,ref,watch,()=>{},fn=>{handlers.unmount=fn},()=>route,()=>router,()=>context,api,positionListQuery))
  t.after(()=>{handlers.unmount();scope.stop()})
  return {vm,route,context,routes,handlers}
}

test('position list restores filters and gives historical readers a scoped detail destination',async t=>{
  let received
  const {vm,context}=list(t,{positions:async params=>{received=params;return {items:[{id:'101'}],total:65}}},{status:'PUBLISHED',q:'设备',page:'3',campaignId:'2'})
  context.recruitmentWritable=false
  await vm.load()
  assert.deepEqual(received,{page:3,pageSize:20,status:'PUBLISHED',keyword:'设备'})
  assert.deepEqual(vm.positionLocation({id:'101'}),{path:'/positions/101/edit',query:{status:'PUBLISHED',q:'设备',page:'3',campaignId:'2'}})
})

test('position list restores browser navigation and ignores stale list responses',async t=>{
  const old=deferred();let reads=0
  const {vm,route}=list(t,{positions:()=>++reads===1?old.promise:Promise.resolve({items:[{id:'new'}],total:1})},{status:'DRAFT'})
  const first=vm.load();await nextTick();await nextTick()
  route.query={status:'PENDING',q:'新查询',campaignId:'2'};await nextTick();await nextTick();await nextTick()
  old.resolve({items:[{id:'old'}],total:1});await first
  assert.equal(vm.active.value,'PENDING');assert.equal(vm.keyword.value,'新查询');assert.equal(vm.items.value[0].id,'new')
})

test('position list withdrawal suppresses duplicate actions and cannot navigate after unmount',async t=>{
  const pending=deferred();let writes=0
  const {vm,handlers,routes}=list(t,{withdrawPosition:()=>{writes++;return pending.promise}})
  const first=vm.withdrawAndEdit({id:'101',version:2,status:'PENDING'})
  await vm.withdrawAndEdit({id:'101',version:2,status:'PENDING'});handlers.unmount();pending.resolve({version:3});await first
  assert.equal(writes,1);assert.deepEqual(routes,[])
})

test('enterprise correction note remains readable and is cleared when another position loads',async t=>{
  const {vm,route}=mount(t,{position:async id=>({...complete,id,version:2,status:'DRAFT',schoolReturn:id==='101'?{id:'7',reason:'补充工作地点',returnedAt:'2026-09-06T00:00:00Z'}:null})},'101')
  await vm.load();assert.equal(vm.schoolReturn.value.reason,'补充工作地点')
  route.params={id:'102'};await nextTick();await nextTick()
  assert.equal(vm.schoolReturn.value,null)
})
