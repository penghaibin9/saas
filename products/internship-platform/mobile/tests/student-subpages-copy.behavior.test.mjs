import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import * as employment from '../src/services/employmentPresentation.mjs'
import { reportFilesReady } from '../src/services/weeklyReportPresentation.mjs'

function page(name){
  const source=fs.readFileSync(new URL(`../src/pages/student-internship/${name}/index.vue`,import.meta.url),'utf8')
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const deps={studentApi:{},toast:()=>{},formatDateTime:value=>value,reportFilesReady,ReportFilePreview:{},currentSessionGeneration:()=>1,...employment}
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),vm=component.data()
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:fn.bind(vm)})
  const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:()=>true}).code)(Vue)
  async function snapshot(){
    const nodes=[],walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)}
    const html=await renderToString(Vue.createSSRApp({render(){const tree=render(vm,[]);walk(tree);return tree}}))
    return {html,nodes,nav:nodes.find(n=>n.type==='MobileNavBar')}
  }
  return {vm,component,snapshot}
}
const batch='9007199254740993001'

test('协议空态及返回真实批次，阅读详情先关闭且提交中不能退出',async()=>{
  const {vm,snapshot}=page('agreement');vm.pageState='ready';vm.requestedBatchId=batch
  let view=await snapshot()
  assert.equal(view.nav.props.title,'三方协议');assert.equal(view.nav.props['fallback-url'],'/pages/student-internship/index?batchId='+batch)
  assert.ok(view.nodes.some(n=>n.type==='MobileInlineAlert'&&n.props.title==='暂无三方协议'&&n.props.description.includes('阅读正文并确认')))
  vm.detail={id:'91',status:'PENDING_STUDENT',renderedBody:'必须阅读的合成正文',enterpriseName:'合成企业'}
  vm.submitting=true;view=await snapshot();assert.equal(view.nav.props['before-back'](),false);assert.equal(vm.detail.id,'91')
  assert.ok(view.html.includes('必须阅读的合成正文'))
  vm.submitting=false;assert.equal(view.nav.props['before-back'](),false);assert.equal(vm.detail,null)
  assert.equal(vm.beforeBack(),true)
  assert.equal(vm.statusHint('PENDING_ENTERPRISE'),'待企业签署，由学校登记纸质协议')
})

test('免实习只保留一次标题，依据去向原因材料和未批准边界完整',async()=>{
  const {vm,snapshot}=page('exemption');vm.pageState='ready';vm.requestedBatchId=batch
  vm.recordStatus='PREPARING';vm.destinationType='NONE'
  let view=await snapshot()
  assert.equal(view.nav.props.title,'免实习申请')
  assert.ok(view.html.includes('提交后需学校审核，不等于已批准免实习。'))
  for(const label of ['免实习类型','免实习后去向','申请原因','佐证材料'])assert.ok(view.html.includes(label))
  assert.ok(!view.html.includes('系统才会')&&!view.html.includes('class="card-title">免实习申请'))
  view.nodes.find(n=>n.type==='picker').props.onChange({detail:{value:2}})
  assert.equal(vm.form.exemptionType,'HEALTH')
  vm.form.exemptionReason='保留已有原因';vm.uploading=true;assert.equal(view.nav.props['before-back'](),false)
  assert.equal(vm.form.exemptionReason,'保留已有原因')
  vm.uploading=false;vm.application={status:'APPROVED',statusLabel:'已批准',reviewComment:'学校意见'}
  view=await snapshot();assert.ok(!view.html.includes('不等于已批准'));assert.equal(vm.editable,false)
  assert.ok(view.html.includes('免实习申请内容'));assert.ok(!view.nodes.some(n=>n.type==='textarea'))
  vm.application=null;vm.recordStatus='ONBOARD';vm.destinationType='ASSIGNED';view=await snapshot();assert.ok(view.html.includes('当前阶段不能新增'));assert.ok(!view.nodes.some(n=>n.type==='textarea'))
})

test('请假记录页保持病假和三天证明规则，返回先收起草稿而不清空',async()=>{
  const {vm,snapshot}=page('leave');vm.pageState='ready';vm.requestedBatchId=batch
  vm.context={hasBatch:true,batchId:batch,statusText:'READY'}
  let view=await snapshot();assert.equal(view.nav.props.title,'实习请假')
  assert.ok(view.html.includes('病假或连续3天及以上请假，必须上传证明。'))
  assert.ok(view.html.includes('当前实习阶段暂不能提交请假。'));assert.equal(vm.writable,false)
  vm.context.statusText='ONBOARD';vm.form={leaveType:'PERSONAL',startDate:'2026-10-13',endDate:'2026-10-14',reason:'保留草稿原因',fileId:'220',fileName:'合成证明'}
  assert.equal(vm.evidenceRequired,false);vm.form.endDate='2026-10-15';assert.equal(vm.evidenceRequired,true)
  vm.form.endDate='2026-10-13';vm.form.leaveType='SICK';assert.equal(vm.evidenceRequired,true)
  vm.formVisible=true;const before=JSON.stringify(vm.form);view=await snapshot()
  assert.equal(view.nav.props['before-back'](),false);assert.equal(vm.formVisible,false);assert.equal(JSON.stringify(vm.form),before)
  vm.reading=true;assert.equal(vm.beforeBack(),false)
})

test('就业先显示方式和状态，全部字段、零薪资、否对口和来源限制保留',async()=>{
  const {vm,snapshot}=page('employment');vm.loaded=true;vm.state='ready';vm.batchId=batch
  vm.batchName='合成批次';vm.mentorName='合成导师';vm.prefill={canTransfer:false,transferHint:'当前没有有效实习企业关系',identityEditable:{enrollmentYear:true}}
  Object.assign(vm.form.fields,{studentName:'合成学生',studentNo:'000000000000000001',salary:'0',majorMatch:false})
  let view=await snapshot();assert.equal(view.nav.props.title,'就业登记')
  assert.equal(view.nav.props['fallback-url'],'/pages/student-internship/index?batchId='+batch)
  assert.ok(view.html.indexOf('登记方式')<view.html.indexOf('学生信息'))
  assert.ok(view.nodes.some(n=>n.type==='MobileStatusTag'&&n.props.label==='尚未提交'))
  for(const field of employment.employmentFields)assert.ok(view.html.includes(field.label),field.key)
  assert.equal(view.html.split('学校信息有误请联系学校。').length-1,1)
  assert.equal(vm.fieldReadonly({key:'studentName',school:true}),true)
  assert.ok(view.html.includes('当前没有有效实习企业关系'))
  assert.ok(!view.html.includes('学校核验通过后可回读结果')&&!view.html.includes('来自学校档案；更正请联系学校'))
  const before=JSON.stringify(vm.form);vm.scanning=true;assert.equal(view.nav.props['before-back'](),false)
  assert.equal(JSON.stringify(vm.form),before);assert.equal(vm.form.fields.salary,'0');assert.equal(vm.form.fields.majorMatch,false)
})
