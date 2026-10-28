import fs from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

test('切学校后隐藏旧校名与服务信息，迟到配置不能覆盖新学校',async()=>{
  let generation=1,resolve,reads=0
  const session={user:{tenantId:'1',userId:'11',roleCode:'STUDENT'}}
  const source=fs.readFileSync(new URL('../src/stores/portalConfig.js',import.meta.url),'utf8').replace(/^import[^\n]+\n/gm,'').replace('export const usePortalConfigStore','const usePortalConfigStore')
  const api={portalConfig:async()=>{reads++;if(reads===1)return new Promise(r=>resolve=r);return {brand:{schoolName:'新学校'},service:{contactPhone:'新咨询电话'}}}}
  const definition=new Function('defineStore','portalApi','currentSessionGeneration','useSessionStore',source+'\nreturn usePortalConfigStore')((_name,value)=>value,api,()=>generation,()=>session)
  const state=definition.state();Object.assign(state,definition.actions)
  for(const [name,get] of Object.entries(definition.getters))Object.defineProperty(state,name,{get:()=>get.call(state,state)})
  const old=state.load();session.user={...session.user,tenantId:'2',userId:'22'};generation++
  assert.equal(state.brand.schoolName,'');assert.equal(state.visibleConfig.service,undefined)
  await state.load();resolve({brand:{schoolName:'旧学校'},service:{contactPhone:'旧电话'}});await old
  assert.equal(state.brand.schoolName,'新学校');assert.equal(state.visibleConfig.service.contactPhone,'新咨询电话')
  await state.load();assert.equal(reads,2)
  session.user=null;assert.equal(state.brand.schoolName,'');assert.equal(state.visibleConfig.service,undefined)
})
