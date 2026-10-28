import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { getVisibleNavPlan } from '../src/config/navPlan.js'

test('系统身份从默认入口登录直接进入可用系统页，显式业务深链继续保留',async()=>{
  const source=fs.readFileSync(new URL('../src/views/auth/StandaloneLoginView.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[^\n]+\n/gm,'').replace('export default','return')
  let permissions=['system.overview.view'],mustChange=false;const targets=[]
  const component=new Function('loginWithPassword','clearPermissionPatterns','getAuthContext','refreshLastActive','request','getVisibleNavPlan',script)(
    async()=>({mustChangePassword:mustChange}),()=>{},()=>{},()=>{},async()=>({permissionPatterns:permissions}),getVisibleNavPlan)
  const vm={...component.data(),$route:{query:{redirect:'/admin/internship'}},$router:{replace:async path=>targets.push(path)}}
  await component.methods.submit.call(vm);assert.equal(targets.pop(),'/admin/system')
  permissions=['system.notification.view'];await component.methods.submit.call(vm);assert.equal(targets.pop(),'/admin/system/notification')
  permissions=['internship.dashboard.view'];await component.methods.submit.call(vm);assert.equal(targets.pop(),'/admin/internship')
  vm.$route.query.redirect='/admin/internship/leaves?batchId=12&id=34';await component.methods.submit.call(vm)
  assert.equal(targets.pop(),'/admin/internship/leaves?batchId=12&id=34')
  for(const value of ['//external.example','https://external.example','/login',undefined]){
    permissions=['system.overview.view'];vm.$route.query.redirect=value;await component.methods.submit.call(vm);assert.equal(targets.pop(),'/admin/system')
  }
  permissions=[];vm.$route.query.redirect='/admin/internship';await component.methods.submit.call(vm);assert.equal(targets.pop(),'/security/403')
  mustChange=true;await component.methods.submit.call(vm);assert.equal(targets.pop(),'/account/security')
})

test('已登录账号从根入口按真实权限选择工作页，显式无权深链和权限服务故障仍拦截',async()=>{
  const source=fs.readFileSync(new URL('../src/router/index.js',import.meta.url),'utf8')
    .replace(/^import[^\n]+\n/gm,'').replace('import.meta.env.BASE_URL',"'/'").replace('export default router','return router')
  let guard,permissions=['system.overview.view'],failure='',allowed=false
  const router=new Function('createRouter','createWebHistory','internshipRoutes','systemRoutes','request','ensurePermissionPatterns','getPermissionPatterns','getRbacLoadFailed','checkRouteAccess','getVisibleNavPlan',source)(
    ()=>({beforeEach:fn=>{guard=fn},afterEach(){}}),()=>{}, {}, {},async()=>({mustChangePassword:false}),async()=>{},()=>permissions,()=>failure,
    ()=>({allowed,failure:'FORBIDDEN'}),getVisibleNavPlan)
  const route={fullPath:'/admin/internship',meta:{},redirectedFrom:{path:'/'}}
  assert.equal(await guard(route),'/admin/system')
  assert.equal((await guard({...route,redirectedFrom:undefined})).path,'/security/403')
  permissions=[];assert.equal((await guard(route)).path,'/security/403')
  permissions=['system.overview.view'];failure='暂时无法读取权限';assert.equal((await guard(route)).path,'/security/500')
  failure='';allowed=true;assert.equal(await guard(route),true)
  assert.ok(router)
})
