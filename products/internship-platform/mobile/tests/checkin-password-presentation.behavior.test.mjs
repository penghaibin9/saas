import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import * as display from '../src/services/checkinPresentation.mjs'

function page(path,overrides={}){
  const source=fs.readFileSync(new URL('../src/pages/'+path+'/index.vue',import.meta.url),'utf8'),script=source.match(/<script>([\s\S]*?)<\/script>/)[1]
  const imports=[...script.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"];?\s*/gm)].flatMap(([,s])=>s.replace(/[{}]/g,'').split(',').map(x=>x.trim()))
  const deps={currentSessionGeneration:()=>1,ReportFilePreview:{},...display,...overrides}
  const component=new Function(...imports,script.replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return'))(...imports.map(key=>deps[key]||{})),vm={}
  for(const[key,fn]of Object.entries(component.methods))vm[key]=(...args)=>fn.apply(vm,args)
  Object.assign(vm,component.data.call(vm));for(const[key,fn]of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  const template=source.slice(source.indexOf('<template>')+10,source.indexOf('\n<script>')).replace(/<\/template>\s*$/,'')
  const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:()=>true}).code)(Vue)
  async function snapshot(){const nodes=[],walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)}
    const html=await renderToString(Vue.createSSRApp({render(){const tree=render(vm,[]);walk(tree);return tree}}));return{html,nodes}}
  return{vm,snapshot}
}

test('签到首屏显示真实岗位日期状态，普通主按钮保留原确认方法',async()=>{
  const p=page('student-internship/checkin');Object.assign(p.vm,{state:'ready',i:{post:'合成在岗岗位',company:'合成企业',historyMode:false,checkin:{done:false,place:'真实岗位地点',note:'点击时定位'}},calendarData:{timezoneName:'Asia/Shanghai',summary:{ABSENT:6,CHECKIN:1}}})
  const {html,nodes}=await p.snapshot()
  assert.ok(html.includes('合成在岗岗位')&&html.includes('真实岗位地点')&&html.includes('今日未签到'))
  const primary=nodes.find(n=>n.type==='button'&&String(n.props?.class||'').includes('ci__submit'))
  assert.ok(primary);assert.equal(primary.props.onClick,p.vm.checkin);assert.equal(primary.props.disabled,false)
  assert.ok(html.includes('不后台定位')&&html.includes('人工核验')&&html.includes('现场相机'))
  p.vm.i.checkin.done=true;assert.equal((await p.snapshot()).nodes.find(n=>n.type==='button'&&String(n.props?.class||'').includes('ci__submit')).props.disabled,true)
  p.vm.i.historyMode=true;const history=await p.snapshot();assert.ok(history.html.includes('签到记录'));assert.ok(!history.html.includes('现场拍照'));assert.ok(!history.nodes.some(n=>n.type==='button'&&/ci__submit|ci__exempt-toggle/.test(String(n.props?.class||''))))
})

test('日历保留未来和期间外的紧凑空标记，详情和无障碍名称仍明确说明状态',()=>{
  const p=page('student-internship/checkin')
  assert.equal(p.vm.calendarStatusLabel('FUTURE'),'');assert.equal(p.vm.calendarDetailLabel('FUTURE'),'未到签到日期')
  assert.equal(p.vm.calendarDetailLabel('OUTSIDE'),'实习期间外');assert.equal(p.vm.calendarDetailLabel('EXEMPT'),'免签');assert.equal(p.vm.calendarDetailLabel('UNKNOWN'),'状态待确认')
})

test('日历收起仍有真实缺卡和补卡入口，选项展开收起不丢备注',async()=>{
  const p=page('student-internship/checkin');Object.assign(p.vm,{state:'ready',i:{checkin:{done:false,place:'岗位地址'},historyMode:false},calendarData:{summary:{ABSENT:6}},calendarDays:[{date:'2026-10-07',day:7,status:'ABSENT',canApplyMakeup:true}]})
  let view=await p.snapshot();assert.equal(p.vm.calendarOpen,false);assert.ok(view.html.includes('缺卡 6'))
  view.nodes.find(n=>n.type==='button'&&n.children==='查看缺卡并补卡').props.onClick();assert.equal(p.vm.calendarOpen,true)
  view=await p.snapshot();view.nodes.find(n=>n.type==='button'&&String(n.props?.class||'').split(/\s+/).includes('ci__day')).props.onClick()
  assert.equal(p.vm.selectedDate,'2026-10-07');assert.equal(p.vm.selectedCalendarDay.status,'ABSENT')
  view=await p.snapshot();assert.ok(view.nodes.some(n=>n.type==='button'&&n.children==='为这一天申请补卡'))
  p.vm.checkinNote='已填备注';view.nodes.find(n=>String(n.props?.class||'').includes('ci__options-toggle')).props.onClick();assert.equal(p.vm.optionsOpen,true)
  view=await p.snapshot();assert.ok(view.html.includes('境外签到'));view.nodes.find(n=>String(n.props?.class||'').includes('ci__options-toggle')).props.onClick();assert.equal(p.vm.checkinNote,'已填备注')
})

test('改密码完整强度说明独立显示，三项密码输入与原提交事件保留',async()=>{
  const p=page('common/change-password'),view=await p.snapshot()
  assert.ok(view.html.includes('至少10位，含大小写字母、数字和特殊字符'))
  assert.ok(view.nodes.some(n=>n.type==='text'&&String(n.children).includes('至少10位')))
  assert.equal(view.nodes.filter(n=>n.type==='input'&&Object.hasOwn(n.props||{},'password')).length,3)
  assert.ok(!view.html.includes('临时密码必须先更换')&&!view.html.includes('请先完成密码修改'))
  assert.equal(view.nodes.find(n=>n.type==='button').props.onClick,p.vm.submit)
})

test('改密的空值、强度、重复和确认错误定位到字段，未发送也不清空输入',async()=>{
  let calls=0
  for(const [currentPassword,newPassword,confirmPassword,field] of [
    ['', 'Example!12345','Example!12345','current'],['unit-only-old','short','short','new'],
    ['Example!12345','Example!12345','Example!12345','new'],['unit-only-old','Example!12345','Example!54321','confirm']]){
    const p=page('common/change-password',{realRequest:()=>{calls++}})
    Object.assign(p.vm,{currentPassword,newPassword,confirmPassword});await p.vm.submit()
    assert.equal(p.vm.invalidField,field);assert.equal(p.vm.newPassword,newPassword);assert.equal(p.vm.confirmPassword,confirmPassword);assert.equal(p.vm.loading,false)
  }
  assert.equal(calls,0)
})
