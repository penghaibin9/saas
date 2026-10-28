import test from 'node:test'

test('异常队列将设备和申诉信号转为中文，保留精确原编号及办理版本',async()=>{
  const source=fs.readFileSync(new URL('../src/services/teacherSequentialV3Api.js',import.meta.url),'utf8')
  const raw={id:'9007199254740993999',type:'OUT_OF_RANGE',typeLabel:'OUT_OF_RANGE',distance:'0.2 km',accuracy:'±5 m',deviceRisk:'mock',appealStatus:'PENDING',version:0}
  const api=new Function('realRequest','formatDateTime',source.replace(/^import[^\n]+\n/gm,'').replace(/export /g,'')+'\nreturn {getInternshipReviewQueue}') (async()=>({abnormalCheckins:[raw]}),formatDateTime)
  let row=(await api.getInternshipReviewQueue()).abnormal[0]
  assert.equal(row.id,raw.id);assert.equal(row.expectedVersion,0);assert.equal(row.type,'OUT_OF_RANGE')
  assert.equal(row.typeLabel,'超范围');assert.equal(row.distance,'0.2 千米');assert.equal(row.accuracy,'±5 米')
  assert.equal(row.deviceRisk,'疑似模拟定位');assert.equal(row.appealStatusLabel,'待核实申诉')
  Object.assign(raw,{type:'UNKNOWN_INTERNAL',typeLabel:'UNKNOWN_INTERNAL',deviceRisk:'UNKNOWN_INTERNAL',appealStatus:'UNKNOWN_INTERNAL'})
  row=(await api.getInternshipReviewQueue()).abnormal[0]
  assert.equal(row.typeLabel,'异常类型待核对');assert.equal(row.deviceRisk,'设备风险信号待核对');assert.equal(row.appealStatusLabel,'申诉状态待核对')
})
import assert from 'node:assert/strict'
import fs from 'node:fs'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { renderToString } from '@vue/server-renderer'
import { listPaging } from '../src/utils/listPaging.js'
import { formatDateTime } from '../src/utils/format.js'
import { processReportView, reportFileState } from '../src/services/weeklyReportPresentation.mjs'

const batch='9007199254740993001'
function page(name,extra={}){
  const source=fs.readFileSync(new URL(`../src/pages/teacher-internship/${name}/index.vue`,import.meta.url),'utf8')
  const context={selectedBatchId:batch,batches:[{id:batch,name:'合成批次'}],can:()=>true,restore(){},load:async()=>{},selectBatch(id){if(!this.batches.some(b=>String(b.id)===String(id)))return false;this.selectedBatchId=String(id);return true}}
  const deps={useInternshipContextStore:()=>context,currentSessionGeneration:()=>1,toast:()=>{},formatDateTime,listPaging,
    InternshipVisitEvidenceForm:{},MobileSequentialQueue:{},ReportFilePreview:{},ReportObligations:{},processReportView,reportFileState,
    normalizeError:()=>({pageState:'error',text:'材料服务暂不可用，请重试'}),...extra}
  const script=source.match(/<script>([\s\S]*?)<\/script>/)[1].replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm,'').replace('export default','return')
  const component=new Function(...Object.keys(deps),script)(...Object.values(deps)),mixins=component.mixins||[]
  const vm={...Object.assign({},...mixins.map(m=>m.data?.()||{})),...component.data(),$refs:{},$nextTick:fn=>fn?.()}
  for(const [key,fn] of Object.entries(Object.assign({},...mixins.map(m=>m.methods||{}),component.methods)))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed||{}))Object.defineProperty(vm,key,{get:fn.bind(vm)})
  vm.state='ready';vm.batches=context.batches;vm.batchId=batch
  const template=source.match(/<template>([\s\S]*?)<\/template>\s*<script>/)[1]
  const render=new Function('Vue',compile(template,{prefixIdentifiers:true,isCustomElement:tag=>tag!=='MobileSequentialQueue'}).code)(Vue)
  async function snapshot(){
    const nodes=[],walk=n=>{if(!n||typeof n!=='object')return;nodes.push(n);if(Array.isArray(n.children))n.children.forEach(walk)}
    const html=await renderToString(Vue.createSSRApp({components:{MobileSequentialQueue:{render:()=>null}},render(){const tree=render(vm,[]);walk(tree);return tree}}))
    return {html,nodes}
  }
  return {vm,context,snapshot,component}
}
const hasClass=(node,name)=>String(node.props?.class||'').split(/\s+/).includes(name)

test('报告待办按权威原单定位批次并直接展开，不以当前批次列表猜测对象',async()=>{
  const report={id:'9007199254740993301',batchId:batch,studentName:'合成原单学生',reportType:'DAILY',periodKey:'2026-10-16',reportVersion:2,version:3,status:'PENDING_REVIEW',content:'本次原单正文',versions:[]};let lists=0
  const p=page('process-report-review',{teacherInternshipProcessReportDetail:async id=>{assert.equal(id,report.id);return report},teacherInternshipProcessReports:async()=>{lists++;return {items:[]}},processReportView:r=>({...r,reportTypeLabel:'日报',periodLabel:r.periodKey,statusLabel:'待批阅'})})
  p.vm.focusReportId=report.id;await p.vm.load();assert.equal(p.vm.expanded,report.id);assert.equal(p.vm.detail[report.id].content,report.content);assert.equal(p.vm.list[0].id,report.id);assert.equal(lists,0);assert.equal(p.vm.total,1)
  const view=await p.snapshot();assert.ok(view.html.includes('来自待办的原报告'));assert.ok(view.html.includes('本次原单正文'));assert.ok(!view.html.includes('查询报告'))
})

test('报告原单不在当前身份批次时拒绝展示，旧会话原单回执被丢弃',async()=>{
  const report={id:'801',batchId:'foreign',content:'不应显示的正文'}
  const p=page('process-report-review',{teacherInternshipProcessReportDetail:async()=>report,processReportView:x=>x});p.vm.focusReportId='801';await p.vm.load();assert.equal(p.vm.state,'error');assert.deepEqual(p.vm.list,[])
  let finish,generation=1;const wait=new Promise(r=>finish=r),q=page('process-report-review',{currentSessionGeneration:()=>generation,teacherInternshipProcessReportDetail:()=>wait,processReportView:x=>x});q.vm.focusReportId='802';const reading=q.vm.load();await new Promise(r=>setImmediate(r));generation++;finish({id:'802',batchId:batch,content:'旧账号正文'});await reading;assert.deepEqual(q.vm.list,[])
})

test('变更空队列不重复零统计，待审原单保留关系协议和重新上岗后果',async()=>{
  const {vm,snapshot}=page('internship-change');vm.list=[]
  let view=await snapshot();assert.ok(!view.nodes.some(n=>hasClass(n,'tc__summary')))
  assert.ok(!view.html.includes('刷新真值')&&!view.html.includes('旧协议失效'))
  vm.total=1;vm.list=[{id:'77',studentName:'合成学生',studentNo:'0001',status:'PENDING',statusLabel:'待审核',version:0,recordVersionSnapshot:3,changeType:'CHANGE_ENTERPRISE',changeTypeLabel:'换单位',currentEnterprise:'原企业',currentPosition:'原岗位',targetEnterpriseName:'目标企业',targetPositionName:'目标岗位',reason:'真实申请原因',impactItems:[{label:'重新上岗',detail:'重新满足学校既有上岗条件'}]}]
  view=await snapshot();for(const text of ['原企业','原岗位','目标企业','目标岗位','真实申请原因','旧协议失效','重新完成上岗核验','重新满足学校既有上岗条件'])assert.ok(view.html.includes(text),text)
  assert.ok(view.nodes.some(n=>hasClass(n,'tc__summary')));vm.list[0].status='APPROVED';view=await snapshot()
  assert.ok(!view.nodes.some(n=>hasClass(n,'tc__impact')))
})

test('周报巡访异常三个队列完整，空态去重复统计但保留位置和证据规则',async()=>{
  const {vm,snapshot}=page('internship-review');vm.data={reports:[],abnormal:[],errors:[],pagination:{}};vm.visitState='ready'
  const original=JSON.stringify(vm.data)
  for(const tab of ['weekly','visit','abnormal']){
    vm.tab=tab;const view=await snapshot()
    assert.deepEqual(view.nodes.find(n=>n.type==='MobileSegmented').props.items.map(x=>x.key),['weekly','visit','abnormal'])
    assert.ok(!view.nodes.some(n=>hasClass(n,'ir__summary')))
    if(tab==='visit')assert.ok(view.html.includes('教师位置默认不采集。'))
    if(tab==='abnormal'){assert.ok(view.html.includes('定位异常不等于作弊'));assert.ok(view.html.includes('有效出勤仍以正常签到或已批准补卡为准'))}
  }
  assert.equal(JSON.stringify(vm.data),original)
})

test('过程报告零统计精简，日期类型筛选和总结零分草稿仍完整',async()=>{
  const {vm,snapshot}=page('process-report-review');vm.list=[];vm.total=0
  vm.filters={keyword:'合成学生',startDate:'2026-10-01',endDate:'2026-10-13'}
  let view=await snapshot();assert.ok(!view.nodes.some(n=>hasClass(n,'pr__summary')))
  assert.equal(view.nodes.filter(n=>n.type==='picker'&&n.props.mode==='date').length,2)
  assert.ok(view.html.includes('2026-10-01')&&view.html.includes('2026-10-13'))
  assert.ok(view.nodes.some(n=>n.type==='ReportObligations'&&n.props['batch-id']===batch))
  const draft={action:'APPROVE',summaryScore:'0',comment:'保留批阅意见'}
  vm.reviewPanel={isSummary:true,reportVersion:3,draft};view=await snapshot()
  assert.ok(view.html.includes('0分有效'))
  assert.ok(view.nodes.some(n=>n.type==='input'&&n.props.id==='report-summary-score'&&n.props.value==='0'))
  vm.closeReview();assert.equal(vm.reviewPanel,null);assert.equal(draft.comment,'保留批阅意见');assert.equal(draft.summaryScore,'0')
})

test('材料503保持错误及可读说明，读取恢复后才清除错误而非伪装缺交',async()=>{
  let fail=true;const {vm,snapshot}=page('material-review',{teacherInternshipMaterialRequirements:async()=>{if(fail)throw {status:503};return []}})
  await vm.load();assert.equal(vm.state,'error');assert.equal(vm.loadError,'材料服务暂不可用，请重试')
  let view=await snapshot();assert.ok(view.nodes.some(n=>n.type==='MobileGlobalState'&&n.props.state==='error'&&n.props.description===vm.loadError))
  assert.equal(vm.coverage,null);assert.deepEqual(vm.rows,[])
  fail=false;await vm.load();assert.equal(vm.state,'ready');assert.equal(vm.loadError,'')
})

test('工资实发和约定、零金额、币种、凭证与更正历史均保留',async()=>{
  const {vm,snapshot}=page('payroll-review')
  vm.list=[{id:'91',studentName:'合成学生',studentNo:'0001',payMonth:'2026-09',agreedSalary:0,agreedSalaryCurrency:'CNY',
    current:{id:'92',status:'SUBMITTED',statusLabel:'待审核',revisionNo:2,actualAmount:0,currency:'USD',paidOn:'2026-09-30',evidenceFileId:'220',correctionReason:'原更正原因',reviewComment:'原审核意见'},
    history:[{id:'90',revisionNo:1,statusLabel:'已退回',actualAmount:20,currency:'USD'},{id:'92',revisionNo:2,statusLabel:'待审核',actualAmount:0,currency:'USD'}]}]
  const view=await snapshot()
  for(const text of ['约定报酬','实际发放','人民币 0.00','美元 0.00','当前版本','第2版','查看工资凭证照片','原更正原因','原审核意见','历史版本（2）'])assert.ok(view.html.includes(text),text)
  assert.equal(vm.money(null),'未填写');assert.equal(vm.money(0,'USD'),'美元 0.00')
})
