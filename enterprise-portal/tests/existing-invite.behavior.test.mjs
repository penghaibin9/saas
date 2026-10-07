import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { parse } from '@vue/compiler-sfc'
import { computed, ref } from 'vue'

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return {promise,resolve} }
const preview = { inviteMode:'EXISTING_MEMBER',memberId:'7',campaignId:'2',companyName:'虚构企业' }
function page(api) {
  const source = parse(fs.readFileSync(new URL('../src/views/InviteAcceptView.vue',import.meta.url),'utf8')).descriptor.script.content.replace(/^import.*$/gm,'').replace('export default','return')
  const options = new Function('enterpriseAuthApi',source)(api), routes=[]
  const vm = {...options.data(),$route:{query:{tenantCode:'fixture',token:'synthetic-token'}},$router:{push:r=>routes.push(r)}}
  for(const [key,fn] of Object.entries(options.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(options.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  return {vm,options,routes}
}

test('existing account signs in, re-inspects the same invitation, then accepts without password reset',async()=>{
  const calls=[]
  const {vm,routes}=page({login:async body=>calls.push(['login',body]),inspectInvite:async body=>{calls.push(['inspect',body]);return preview},acceptExistingInvite:async body=>calls.push(['accept',body]),acceptInvite:()=>assert.fail('must not call public activation')})
  vm.loading=false;vm.preview=preview;vm.form={loginName:'existing',password:'synthetic-only',phone:''}
  await vm.accept()
  assert.deepEqual(calls.map(c=>c[0]),['login','inspect','accept'])
  assert.equal(calls[0][1].memberId,'7');assert.deepEqual(Object.keys(calls[2][1]).sort(),['tenantCode','token'])
  assert.equal(vm.form.password,'');assert.deepEqual(routes,['/home'])
})

test('failed existing login preserves identity, clears password and never accepts the invitation',async()=>{
  let accepts=0
  const {vm}=page({login:async()=>{throw new Error('账号不匹配')},acceptExistingInvite:()=>accepts++})
  vm.loading=false;vm.preview=preview;vm.form={loginName:'existing',password:'synthetic-only',phone:''}
  await vm.accept();assert.equal(accepts,0);assert.equal(vm.form.loginName,'existing');assert.equal(vm.form.password,'');assert.equal(vm.error,'账号不匹配')
})

test('repeated submit while login waits performs one login and no stale acceptance after route change',async()=>{
  const pending=deferred();let logins=0,accepts=0
  const {vm}=page({login:()=>{logins++;return pending.promise},inspectInvite:async()=>preview,acceptExistingInvite:()=>accepts++})
  vm.loading=false;vm.preview=preview;vm.form={loginName:'existing',password:'synthetic-only',phone:''}
  const first=vm.accept();await vm.accept();vm.$route.query.token='new-token';pending.resolve();await first
  assert.equal(logins,1);assert.equal(accepts,0)
})

test('a late invitation preview cannot replace a new route or survive unmount',async()=>{
  const pending=deferred();let reads=0
  const {vm,options}=page({inspectInvite:()=>++reads===1?pending.promise:Promise.resolve({...preview,memberId:'9'})})
  const first=vm.load();vm.$route.query.token='new-token';await vm.load();pending.resolve(preview);await first
  assert.equal(vm.preview.memberId,'9')
  options.beforeUnmount.call(vm);assert.equal(vm.alive,false)
})

test('first activation continues to use phone and new password with no company or campaign body fields',async()=>{
  let sent
  const {vm}=page({acceptInvite:async body=>{sent=body}})
  vm.loading=false;vm.preview={...preview,inviteMode:'NEW_MEMBER'};vm.form={loginName:'',phone:'13800001234',password:'synthetic-only'}
  await vm.accept();assert.deepEqual(Object.keys(sent).sort(),['password','phone','tenantCode','token'])
})

function authAdapter(request) {
  const selected=[],tokens=[]
  const source=fs.readFileSync(new URL('../src/services/authApi.js',import.meta.url),'utf8').replace(/^import.*$/gm,'').replace('export const enterpriseAuthApi=','const enterpriseAuthApi=')+'\nreturn enterpriseAuthApi'
  const api=new Function('request','setAuthTokens','setSelectedCampaignId','setTenantCode',source)(request,data=>tokens.push(data),id=>selected.push(id),()=>{})
  return {api,selected,tokens}
}
test('adapter requires matching inspected link and only selects server-confirmed campaign after authenticated acceptance',async()=>{
  const requests=[]
  const {api,selected,tokens}=authAdapter(async(path,options)=>{requests.push({path,options});return {campaignId:'2'}})
  await assert.rejects(api.acceptExistingInvite({tenantCode:'fixture',token:'one'}),/校验/)
  await api.inspectInvite({tenantCode:'fixture',token:'one'})
  await assert.rejects(api.acceptExistingInvite({tenantCode:'fixture',token:'two'}),/校验/)
  await api.acceptExistingInvite({tenantCode:'fixture',token:'one'})
  assert.deepEqual(selected,['2']);assert.deepEqual(tokens,[])
  assert.equal(requests[1].options.auth,undefined);assert.equal(requests[1].path.endsWith('/accept-existing'),true)
  await assert.rejects(api.acceptExistingInvite({tenantCode:'fixture',token:'one'}),/校验/)
})

test('late inspect and acceptance never replace newer invitation selection',async()=>{
  const old=deferred(),accept=deferred()
  const {api,selected}=authAdapter((path,options)=>path.endsWith('/accept-existing')?accept.promise:options.body.token==='old'?old.promise:Promise.resolve({campaignId:'3'}))
  const first=api.inspectInvite({tenantCode:'fixture',token:'old'})
  await api.inspectInvite({tenantCode:'fixture',token:'new'});old.resolve({campaignId:'2'});await assert.rejects(first,/切换/)
  const accepting=api.acceptExistingInvite({tenantCode:'fixture',token:'new'})
  await api.inspectInvite({tenantCode:'fixture',token:'newer'});accept.resolve({campaignId:'3'});await assert.rejects(accepting,/切换/)
  assert.deepEqual(selected,[])
})

function selector(api = {}) {
  const source=parse(fs.readFileSync(new URL('../src/views/CampaignSelectView.vue',import.meta.url),'utf8')).descriptor.scriptSetup.content.replace(/^import.*$/gm,'')+'\nreturn {items,activeItems,historyItems,collaborationItems,waitingItems,enter,load,loading,error}'
  const selected=[],routes=[]
  let unmount
  const vm=new Function('computed','ref','onMounted','onBeforeUnmount','useRouter','enterpriseInternshipApi','setSelectedCampaignId',source)(computed,ref,()=>{},fn=>{unmount=fn},()=>({push:r=>routes.push(r)}),api,id=>selected.push(id))
  vm.loading.value=false
  return {vm,selected,routes,unmount:()=>unmount()}
}
const usableCampaign = {id:'2',batchId:'23',status:'OPEN',participationStatus:'ACCEPTED',recruitmentAvailable:true}
test('campaign selector separates actual recruitment, history, collaboration-only and unavailable access',async()=>{
  const {vm,selected,routes}=selector({context:async id=>({campaignId:id})})
  vm.items.value=[{id:'1',status:'OPEN',participationStatus:'INVITED'},usableCampaign,{...usableCampaign,id:'3',status:'CLOSED'},{...usableCampaign,id:'4',recruitmentAvailable:false},{...usableCampaign,id:'5',recruitmentAvailable:false,collaborationAvailable:true}]
  assert.deepEqual(vm.activeItems.value.map(v=>v.id),['2']);assert.deepEqual(vm.historyItems.value.map(v=>v.id),['3'])
  assert.deepEqual(vm.waitingItems.value.map(v=>v.id),['1','4'])
  assert.deepEqual(vm.collaborationItems.value.map(v=>v.id),['5'])
  await vm.enter(vm.items.value[0]);assert.deepEqual(selected,[])
  await vm.enter(vm.items.value[1]);assert.deepEqual(selected,['2']);assert.deepEqual(routes,['/home'])
})

test('selector rechecks context before selecting and reports expiry without navigation',async()=>{
  const {vm,selected,routes}=selector({context:async()=>{throw new Error('访问已过期')}})
  await vm.enter(usableCampaign)
  assert.deepEqual(selected,[]);assert.deepEqual(routes,[]);assert.equal(vm.error.value,'访问已过期')
})

test('selector preserves collaboration-only entry and never verifies it as recruitment',async()=>{
  let received
  const {vm,selected}=selector({context:()=>assert.fail('recruitment call'),collaborationContext:async id=>{received=id;return {batchId:id}}})
  await vm.enter({...usableCampaign,recruitmentAvailable:false,collaborationAvailable:true},'COLLABORATION')
  assert.equal(received,'23');assert.deepEqual(selected,['2'])
})

test('selector ignores duplicate clicks and an unmounted late context response',async()=>{
  const pending=deferred();let calls=0
  const {vm,selected,unmount}=selector({context:()=>{calls++;return pending.promise}})
  const first=vm.enter(usableCampaign);await vm.enter(usableCampaign);unmount();pending.resolve({campaignId:'2'});await first
  assert.equal(calls,1);assert.deepEqual(selected,[])
})

test('selector isolates overlapping reloads and rejects a mismatched response scope',async()=>{
  const pending=deferred();let calls=0
  const {vm,selected}=selector({campaigns:()=>++calls===1?pending.promise:Promise.resolve([usableCampaign]),context:async()=>({campaignId:'wrong'})})
  const first=vm.load();await vm.load();pending.resolve([]);await first
  assert.equal(vm.items.value[0].id,'2')
  await vm.enter(usableCampaign);assert.deepEqual(selected,[]);assert.match(vm.error.value,/范围已变化/)
})
