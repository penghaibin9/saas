import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const row={id:'batch:9007199254741001',scopeType:'BATCH',campaignId:null,batchId:'9007199254741001',name:'普通实习批次',collaborationAvailable:true,recruitmentAvailable:false}
function context(api){
  const source=fs.readFileSync(new URL('../src/stores/enterpriseContext.js',import.meta.url),'utf8').replace(/^import.*$/gm,'').replace('export const useEnterpriseContextStore','const useEnterpriseContextStore')+'\nreturn useEnterpriseContextStore'
  const modes=[],options=new Function('defineStore','enterpriseInternshipApi','setEnterpriseApiContext','getSelectedCampaignId',source)((_,o)=>o,{campaigns:async()=>[row],company:async()=>({name:'虚构企业'}),messageCount:async()=>({unread:0}),...api},(...args)=>modes.push(args),()=>row.id)
  const vm=options.state()
  for(const [k,fn] of Object.entries(options.actions))vm[k]=fn.bind(vm)
  for(const [k,fn] of Object.entries(options.getters))Object.defineProperty(vm,k,{get:()=>fn(vm)})
  return {vm,modes}
}
test('普通批次协同刷新后仍只核验批次授权，不请求或开放招聘接口',async()=>{
  let recruitment=0,received
  const {vm}=context({context:async()=>{recruitment++;throw Error('不应请求招聘')},collaborationContext:async id=>{received=id;return {batchId:id,memberRole:'COMPANY_ADMIN',grantId:'4',capabilities:{recruitmentWrite:false,internshipCollab:true}}}})
  await vm.load()
  assert.equal(recruitment,0);assert.equal(received,row.batchId);assert.equal(vm.contextMode,'COLLABORATION')
  assert.equal(vm.internshipCollabReady,true);assert.equal(vm.recruitmentWritable,false);assert.equal(vm.applicationViewAllowed,false)
})
test('普通批次授权在列表读取后被撤销，刷新不得保留旧学生范围或能力',async()=>{
  const {vm}=context({context:async()=>{throw Error('没有招聘范围')},collaborationContext:async()=>{throw Error('授权已撤销')}})
  vm.contextReady=true;vm.scopeKey='old';vm.capabilities={recruitmentWrite:true,internshipCollab:true}
  await vm.load();assert.equal(vm.contextReady,false);assert.equal(vm.scopeKey,'');assert.equal(vm.campaign,null)
  assert.equal(vm.internshipCollabReady,false);assert.equal(vm.recruitmentWritable,false)
})
