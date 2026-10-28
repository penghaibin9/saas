import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { compile, createSSRApp, h } from 'vue'
import { renderToString } from '@vue/server-renderer'
import { normalizeError } from './request-module.mjs'

const read=path=>fs.readFileSync(new URL('../src/'+path,import.meta.url),'utf8')
function options(source,deps){const script=source.match(/<script>([\s\S]*?)<\/script>/)[1];return new Function(...Object.keys(deps),script.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...Object.values(deps))}
const template=source=>source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
const globalSource=read('components/MobileGlobalState.vue'),globalComponent=options(globalSource,{back(){},relaunch(){}})
globalComponent.render=compile(template(globalSource),{isCustomElement:tag=>['view','text'].includes(tag)})
const loaders={'checkin-exemption':'teacherInternshipCheckinExemptions','enterprise-eval':'teacherInternshipEnterpriseEvals','insurance-verify':'teacherInternshipInsurancePending','student-eval':'teacherInternshipStudentEvals'}
function page(name,error){
  const source=read(`pages/teacher-internship/${name}/index.vue`),context={roleCode:'INTERN_MENTOR',batches:[{id:'2673',name:'合成批次',studentCount:0}],selectedBatchId:'2673',restore(){},load:async()=>{},can:()=>false}
  const deps={normalizeError,currentSessionGeneration:()=>1,useInternshipContextStore:()=>context,useSessionStore:()=>({identity:{userId:'11'}}),toast(){},fileSdk:{},createSubmitLock:()=>({}),[loaders[name]]:async()=>{throw error}}
  const component=options(source,deps),vm={...component.data()}
  for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const[key,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  const components={MobileGlobalState:globalComponent,MobileNavBar:{props:['title'],setup:props=>()=>h('header',props.title)},MobilePrivacyGate:{render:()=>null},MobileStatusTag:{render:()=>null},MobileInlineAlert:{render:()=>null},MobileSafeAreaBar:{render:()=>null}}
  return{vm,html:()=>renderToString(createSSRApp({components,setup:()=>vm,render:compile(template(source),{isCustomElement:tag=>['view','text','picker','switch','image'].includes(tag)})}))}
}

for(const name of Object.keys(loaders))test(`${name}消费真实错误分类：无权页不重试，服务失败不能伪装空数据`,async()=>{
  const denied=page(name,{code:1,bizCode:'NO_PERMISSION',httpStatus:403,message:'raw_scope_internal'})
  await denied.vm.load();assert.equal(denied.vm.state,'forbidden');assert.match(denied.vm.error,/暂无访问权限/)
  const forbiddenHtml=await denied.html();assert.ok(forbiddenHtml.includes('暂无访问权限'));assert.ok(!forbiddenHtml.includes('重试')&&!forbiddenHtml.includes('raw_scope_internal'))
  const failed=page(name,{code:1,bizCode:'NO_PERMISSION',httpStatus:503,message:'raw_server_internal'})
  await failed.vm.load();assert.equal(failed.vm.state,'error');assert.match(failed.vm.error,/服务暂时不可用/)
  const errorHtml=await failed.html();assert.ok(errorHtml.includes('重试'));assert.ok(!errorHtml.includes('raw_server_internal'))
})
