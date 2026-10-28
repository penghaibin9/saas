import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'

function page(path, overrides={}) {
  const source=fs.readFileSync(new URL('../src/pages/'+path+'/index.vue',import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1],imports=[...script.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,b])=>b.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  let modal;const deps={studentApi:{},currentSessionGeneration:()=>1,normalizeError:()=>({text:'读取失败'}),uni:{showModal:options=>{modal=options}},FORCE_PASSWORD_CHANGE_ROUTE:'/pages/common/change-password/index',...overrides}
  imports.push('uni');const component=new Function(...imports,script.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...imports.map(key=>deps[key]||{}))
  const vm={...component.data()};for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  for(const[key,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:tag=>tag!=='MobileNavBar'}).code)(Vue)
  async function snapshot(){const nodes=[];const walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)}
    const html=await renderToString(Vue.createSSRApp({components:{MobileNavBar:{props:['title'],setup:(props,{slots})=>()=>Vue.h('header',[props.title,slots.right?.()])}},render(){const tree=render(vm,[]);walk(tree);return tree}}));return{html,nodes}}
  return {vm,component,snapshot,modal:()=>modal}
}

test('基础资料只有真实学生状态与三字段，空性别保持未填写且返回保留草稿',async()=>{
  const p=page('student-internship/basic-info');Object.assign(p.vm,{state:'ready',batchId:'2673',profile:{name:'合成学生',studentNo:'000001',statusLabel:'待完善',editable:true,missingFields:['性别'],complete:false,version:0}})
  let view=await p.snapshot();assert.ok(view.nodes.some(n=>typeof n.type==='object'||n.type==='MobileNavBar'))
  assert.ok(!view.html.includes('同步更新')&&!view.html.includes('1项待办')&&!view.html.includes('空白保存'))
  assert.equal(p.vm.form.gender,'');assert.equal(p.vm.genderIndex,0);assert.ok(view.html.includes('不填详细住址'))
  p.vm.dirty=true;p.vm.form.sourceRegion='合成地区';const pending=p.vm.beforeBack();p.modal().success({confirm:false});assert.equal(await pending,false);assert.equal(p.vm.form.sourceRegion,'合成地区')
  p.vm.submitting=true;assert.equal(p.vm.beforeBack(),false)
})

test('登录真实学生教师模式保留三项输入和密码遮挡，删除重复说明',async()=>{
  const p=page('login')
  let view=await p.snapshot();assert.ok(!view.html.includes('只进入岗位实习业务')&&!view.html.includes('跃科岗位实习管理平台'))
  for(const id of ['mobile-login-school','mobile-login-account','mobile-login-password'])assert.ok(view.nodes.some(n=>n.props?.id===id))
  const password=view.nodes.find(n=>n.props?.id==='mobile-login-password');assert.ok(Object.hasOwn(password.props,'password')&&password.props.password!==false)
  assert.ok(view.html.includes('学生登录'));view.nodes.find(n=>n.type==='button'&&n.children==='教师').props.onClick();view=await p.snapshot();assert.ok(view.html.includes('教师登录'));assert.ok(view.nodes.some(n=>String(n.props?.class||'').includes('is-teacher')))
})

test('登录方法仍提交实际选定的客户端身份并按原改密条件跳转',async()=>{
  for(const mode of ['STUDENT_MINI','TEACHER_MINI']){
    const calls=[],identity={roleCode:mode==='STUDENT_MINI'?'STUDENT':'INTERN_MENTOR'}
    const p=page('login',{loginMobile:async body=>{calls.push(body);return{identity,data:{mustChangePassword:true},home:'/unused-home'}},useSessionStore:()=>({setIdentity:value=>calls.push(value)}),relaunch:path=>calls.push(path)})
    Object.assign(p.vm,{mode,tenantCode:'synthetic-school',loginName:'synthetic-account',password:'unit-only'})
    await p.vm.submit();assert.deepEqual(calls,[{tenantCode:'synthetic-school',loginName:'synthetic-account',password:'unit-only',clientType:mode},identity,'/pages/common/change-password/index']);assert.equal(p.vm.loading,false)
  }
})
