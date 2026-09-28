import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { reactive } from 'vue'
import * as graduation from '../src/modules/academicAffairs/constants/grade-graduation.js'
import { academicStatusLabel } from '../src/modules/academicAffairs/constants/academic-display.constants.js'

function definition(name, overrides = {}) {
  const source = fs.readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`,import.meta.url),'utf8').match(/<script>([\s\S]*?)<\/script>/)[1]
  const bindings=[...source.matchAll(/^import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]\s*$/gm)].flatMap(([,binding])=>binding.trim().startsWith('{')?binding.replace(/[{}]/g,'').split(',').map(s=>s.trim()).filter(Boolean):[binding.trim()])
  const deps={...graduation,academicStatusLabel,currentUserFromToken:()=>({}),...overrides}
  return new Function(...bindings,source.replace(/^import\s+[\s\S]*?\s+from\s+['"][^'"]+['"]\s*$/gm,'').replace('export default','return'))(...bindings.map(key=>deps[key]??{}))
}

function instance(overrides = {}) {
  const component=definition('AaGraduationAuditConsoleView',{matchPermission:(patterns,key)=>patterns.includes(key),...overrides})
  const vm={...component.data(),$route:{path:'/admin/academic-affairs/graduation/audit-console',fullPath:'/admin/academic-affairs/graduation/audit-console?batchId=12&tab=internship',query:{tab:'results'}},ctx:{permissionPatterns:[]}}
  vm.$router={resolve:target=>({fullPath:`${target.path}?${new URLSearchParams(Object.entries(target.query).filter(([,value])=>value!=null)).toString()}`})}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(vm,key,{get:()=>fn.call(vm)})
  vm.batchId='12';vm.batches=[{batchId:'12',batchName:'验收批次',status:'PRECHECKED',total:2,passed:0,abnormal:2,concluded:0,archived:0}]
  return vm
}

test('缺上游记录时按学号进入责任名单，已有记录仍直达详情并保留审核对象',()=>{
  const vm=instance();vm.ctx.permissionPatterns=['internship.student.view','graduationDesign.student.view']
  vm.batches[0].termId='54';vm.tab='internship'
  const row={resultId:'88',studentNo:'V52023001',items:[{item:'INTERNSHIP',result:'UNKNOWN',owner:'INTERN_MENTOR'}]}
  vm.rows=[row]
  assert.match(vm.responsibilityReason,/学生管理人员建档/)
  const missing=vm.linkFor(row)
  assert.equal(missing.path,'/admin/internship/students')
  assert.equal(missing.query.keyword,'V52023001')
  assert.match(missing.query.returnTo,/termId=54/)
  assert.match(missing.query.returnTo,/batchId=12/)
  assert.match(missing.query.returnTo,/resultId=88/)
  assert.match(missing.query.returnTo,/tab=internship/)
  row.items[0].refId='9007199254740993'
  const existing=vm.linkFor(row)
  assert.equal(existing.path,'/admin/internship/students/9007199254740993')
  assert.equal(existing.query.returnTo,missing.query.returnTo)
  vm.tab='thesis';row.items=[{item:'GRADUATION_DESIGN',result:'UNKNOWN',owner:'GD_MENTOR'}]
  assert.equal(vm.linkFor(row).path,'/admin/graduation/students')
  vm.tab='final';assert.equal(vm.linkForItem(row,row.items[0]).path,'/admin/graduation/students')
  assert.match(vm.linkForItem(row,row.items[0]).query.returnTo,/tab=final/)
  vm.ctx.permissionPatterns=[];assert.equal(vm.linkFor(row),null)
  vm.ctx.permissionPatterns=['graduationDesign.student.view'];delete row.studentNo;assert.equal(vm.linkFor(row),null)
})

test('毕业证据缺项只向有目标权限的账号开放真实责任模块',()=>{
  const vm=instance();vm.tab='final'
  const row={resultId:'88',studentId:'91',studentNo:'V52023001'}
  for(const [item,permission,path] of [
    ['COURSE_REQUIRED','academicAffairs.grade.view','/admin/academic-affairs/grade-overview'],
    ['COURSE_ELECTIVE','academicAffairs.grade.view','/admin/academic-affairs/grade-overview'],
    ['PRACTICE','academicAffairs.program.view','/admin/academic-affairs/programs'],
    ['DISCIPLINE','studentAffairs.discipline.view','/admin/student-affairs/discipline'],
    ['ARCHIVE','studentAffairs.archive.view','/admin/student-affairs/archive']
  ]){
    const evidence={item,result:'UNKNOWN'}
    vm.ctx.permissionPatterns=[];assert.equal(vm.linkForItem(row,evidence),null)
    vm.ctx.permissionPatterns=[permission]
    const target=vm.linkForItem(row,evidence)
    assert.equal(target.path,path)
    assert.match(target.query.returnTo,/resultId=88/)
    assert.equal(vm.sourceLinkLabel(evidence),'进入责任模块，按学号核对')
    if(item==='DISCIPLINE') assert.equal(target.query.studentId,'91')
  }
})

test('旧结果页的来源入口也按真实学号定位并拒绝无权下钻',()=>{
  const component=definition('AaGraduationResultView',{matchPermission:(patterns,key)=>patterns.includes(key),toast:{error:()=>{}}})
  const pushes=[]
  const vm={...component.data(),ctx:{permissionPatterns:['internship.student.view']},$route:{path:'/admin/academic-affairs/graduation/13/results',query:{termId:'54'}},$router:{resolve:target=>({fullPath:`${target.path}?${new URLSearchParams(target.query).toString()}`}),push:target=>pushes.push(target)}}
  for(const [key,fn] of Object.entries(component.methods))vm[key]=fn.bind(vm)
  const row={studentNo:'V52023001',resultId:'77'};const item={item:'INTERNSHIP',drillRoute:'/admin/internship/students'}
  Object.defineProperty(vm,'batchId',{get:()=> '13'})
  assert.equal(vm.canDrillEvidence(item,row),true)
  vm.drillEvidence(item,row)
  assert.equal(pushes[0].path,'/admin/internship/students')
  assert.equal(pushes[0].query.keyword,'V52023001')
  assert.match(pushes[0].query.returnTo,/termId=54/)
  assert.match(pushes[0].query.returnTo,/batchId=13/)
  assert.match(pushes[0].query.returnTo,/resultId=77/)
  item.refId='91';vm.drillEvidence(item,row)
  assert.equal(pushes[1].path,'/admin/internship/students/91')
  const archive={item:'ARCHIVE',drillRoute:'/admin/student-affairs/archive'}
  assert.equal(vm.canDrillEvidence(archive,row),false)
  vm.drillEvidence(archive,row);assert.equal(pushes.length,2)
  vm.ctx.permissionPatterns=['studentAffairs.archive.view']
  assert.equal(vm.canDrillEvidence(archive,row),true)
  vm.drillEvidence(archive,row);assert.equal(pushes[2].path,'/admin/student-affairs/archive')
  archive.drillRoute='/admin/academic-affairs/textbooks?tab=fee'
  vm.drillEvidence(archive,row);assert.equal(pushes[3].path,'/admin/student-affairs/archive')
  const fee={item:'FEE',drillRoute:'/admin/academic-affairs/textbooks?tab=fee'}
  vm.ctx.permissionPatterns=['academicAffairs.textbook.view'];assert.equal(vm.canDrillEvidence(fee,row),false)
  vm.ctx.permissionPatterns=['academicAffairs.textbook.fee.manage'];assert.equal(vm.canDrillEvidence(fee,row),true)
  vm.drillEvidence(fee,row);assert.deepEqual(pushes[4],{path:'/admin/academic-affairs/textbooks',query:{tab:'fee'}})
  vm.ctx.permissionPatterns=['academicAffairs.graduation.view']
  vm.drillEvidence({item:'CREDIT',drillRoute:'/admin/academic-affairs/graduation/audit-console'},row)
  assert.equal(pushes[5].path,'/admin/academic-affairs/graduation/audit-console')
  assert.equal(pushes[5].query.batchId,'13')
  assert.equal(pushes[5].query.resultId,'77')
  assert.equal(pushes[5].query.termId,'54')
  assert.equal(pushes[5].query.tab,'credit')
  assert.match(pushes[5].query.returnTo,/^\/admin\/academic-affairs\/graduation\/13\/results\?termId=54$/)
  vm.ctx.permissionPatterns=[];assert.equal(vm.canDrillEvidence(item,row),false)
  vm.returnToBatch();assert.equal(pushes[6].query.termId,'54')
})

test('毕业预审按实习和毕设正式岗位分别展示证据责任',()=>{
  const vm=instance()
  assert.equal(vm.ownerLabel('INTERN_MENTOR'),'岗位实习责任岗')
  assert.equal(vm.ownerLabel('GD_MENTOR'),'毕业设计责任岗')
})

test('浏览结果或归档页不会把未完成的学院审核和终审打勾',()=>{
  const vm=instance()
  assert.equal(vm.stageIndex,2)
  vm.$route.query.tab='archive';assert.equal(vm.stageIndex,2)
  vm.batches[0].abnormal=0;vm.batches[0].passed=2
  assert.equal(vm.stageIndex,3)
  vm.batches[0].concluded=2;assert.equal(vm.stageIndex,5)
  vm.batches[0].status='ARCHIVED';assert.equal(vm.stageIndex,6)
})

function batchInstance(api = {}, query = {}, canManage = true) {
  const errors=[],successes=[],writes=[]
  const component=definition('AaGraduationBatchView',{
    academicAffairsApi:{listGradBatches:async()=>({code:0,data:{list:[],total:0}}),...api},
    matchPermission:()=>canManage,
    gradeError:(_err,fallback)=>fallback,
    toast:{error:value=>errors.push(value),success:value=>successes.push(value)}
  })
  const page=reactive({...component.data(),ctx:{currentRole:{roleCode:'SCHOOL_ADMIN'},dataScope:{scope:'TENANT_ALL'},permissionPatterns:[]},$route:{path:'/admin/academic-affairs/graduation',query}})
  page.$router={replace:async target=>{writes.push(target);page.$route.query=target.query}}
  for(const [key,fn] of Object.entries(component.methods))page[key]=fn.bind(page)
  for(const [key,fn] of Object.entries(component.computed))Object.defineProperty(page,key,{get:()=>fn.call(page)})
  return {page,component,errors,successes,writes}
}

test('只读毕业账号展示批次正式学期，不额外要求创建页学期查询权限',async()=>{
  const {page}=batchInstance({getCurrentTerm:()=>assert.fail('只读账号不初始化创建表单')},{},false)
  await page.loadDraftTerm()
  assert.equal(page.termError,'');assert.equal(page.termLoading,false)
  assert.equal(page.batchTermLabel({termId:'51',termName:'正式学期'}),'正式学期')
})

test('毕业创建读取合法学期深链，保留大整数字符串且不回退当前学期',async()=>{
  const calls=[],termId='9007199254740993'
  const {page}=batchInstance({getTermDetail:async id=>{calls.push(id);return {code:0,data:{termId:id,termName:'正式第二学期'}}},getCurrentTerm:()=>assert.fail('深链不能改用当前学期')},{termId})
  await page.loadDraftTerm()
  assert.equal(page.draft.termId,termId)
  assert.deepEqual(calls,[termId])
  assert.equal(page.termLoading,false)
  assert.equal(page.termError,'')
})

test('无效或不可读取的学期深链清空旧选择并阻止创建',async()=>{
  let reads=0,writes=0
  const {page}=batchInstance({getTermDetail:async()=>{reads++;throw {code:403}},getCurrentTerm:()=>assert.fail('不可回退'),createGradBatch:async()=>{writes++}},{termId:['51','52']})
  page.draft={batchName:'审核',gradeYear:'2023',majorId:'',termId:'51'}
  await page.loadDraftTerm();await page.createBatch()
  assert.equal(reads,0);assert.equal(writes,0);assert.equal(page.draft.termId,'');assert.ok(page.termError)
  page.$route.query={termId:'52'}
  await page.loadDraftTerm();await page.createBatch()
  assert.equal(reads,1);assert.equal(writes,0);assert.equal(page.termLoading,false);assert.ok(page.termError)
})

test('没有深链时读取正式当前学期，用户选择后刷新保留所选学期',async()=>{
  const {page,writes}=batchInstance({getCurrentTerm:async()=>({code:0,data:{termId:'51'}})})
  await page.loadDraftTerm();assert.equal(page.draft.termId,'51')
  page.selectTerm('52')
  assert.equal(writes[0].query.termId,'52')
  const refreshed=batchInstance({getTermDetail:async id=>({code:0,data:{termId:id}})},writes[0].query)
  await refreshed.page.loadDraftTerm();assert.equal(refreshed.page.draft.termId,'52')
  page.resetBatch();assert.equal(page.draft.termId,'52')
})

test('用户选择、切换身份及卸载均拒收旧学期响应',async()=>{
  let resolve
  const {page,component}=batchInstance({getCurrentTerm:()=>new Promise(done=>{resolve=done}),getTermDetail:async id=>({code:0,data:{termId:id}})})
  const old=page.loadDraftTerm()
  page.selectTerm('52');resolve({code:0,data:{termId:'51'}});await old
  assert.equal(page.draft.termId,'52');assert.equal(page.termLoading,false)
  page.$route.query={};const oldSchool=page.loadDraftTerm();const resolveOld=resolve
  page.ctx.currentRole={roleCode:'OTHER_SCHOOL'};page.clearPrivate();page.$route.query={termId:'53'}
  await page.loadDraftTerm();resolveOld({code:0,data:{termId:'51'}});await oldSchool
  assert.equal(page.draft.termId,'53')
  page.$route.query={};const disposed=page.loadDraftTerm();component.beforeUnmount.call(page)
  resolve({code:0,data:{termId:'54'}});await disposed
  assert.equal(page.draft.termId,'')
})

test('毕业批次创建必须回读同一正式学期，未知结果不自动重发',async()=>{
  const sent=[],termId='9007199254740993'
  const readTerm='52'
  const {page,errors,successes}=batchInstance({
    createGradBatch:async body=>{sent.push(body);return {code:0,data:{batchId:'22',termId}}},
    listGradBatches:async()=>({code:0,data:{list:[{batchId:'22',batchName:'正式审核',gradeYear:'2023',majorId:null,termId:readTerm,termName:'正式第二学期'}],total:1}})
  })
  page.draft={batchName:'正式审核',gradeYear:'2023',majorId:'',termId}
  await page.createBatch();await page.createBatch()
  assert.equal(sent.length,1);assert.equal(sent[0].termId,termId);assert.equal(page.batch,null)
  assert.equal(page.pendingCommand.kind,'create');assert.equal(page.creating,false);assert.equal(successes.length,0);assert.match(errors[0],/待核实/)
})

test('未选择或不精确的学期标识不能创建毕业批次',async()=>{
  let writes=0
  const {page}=batchInstance({createGradBatch:async()=>{writes++}})
  page.draft.batchName='正式审核'
  for(const invalid of ['',null,['51','52'],Number.MAX_SAFE_INTEGER+1]){
    page.draft.termId=invalid;await page.createBatch()
  }
  assert.equal(writes,0);assert.equal(page.pendingCommand,null)
})

test('创建成功保留正式学期字段、刷新入口及单次命令',async()=>{
  let writes=0
  const fresh={batchId:'22',batchName:'正式审核',gradeYear:'2023',majorId:null,termId:'51',termName:'2025-2026学年第二学期'}
  const {page,successes}=batchInstance({createGradBatch:async()=>{writes++;return {code:0,data:{batchId:'22',termId:'51'}}},listGradBatches:async()=>({code:0,data:{list:[fresh],total:1}})})
  page.draft={batchName:fresh.batchName,gradeYear:'2023',majorId:'',termId:'51'}
  await page.createBatch()
  assert.equal(writes,1);assert.equal(page.pendingCommand,null);assert.equal(page.batch.termId,'51')
  assert.equal(page.$route.query.termId,'51');assert.equal(successes.length,1)
  assert.equal(page.batchTermLabel(page.batch),fresh.termName)
})

test('学期切换后的迟到创建回读不会把旧学期批次带回来',async()=>{
  let finish
  const {page,successes}=batchInstance({createGradBatch:async()=>({code:0,data:{batchId:'22'}}),listGradBatches:()=>new Promise(resolve=>{finish=resolve}),getTermDetail:async id=>({code:0,data:{termId:id}})})
  page.draft={batchName:'审核',gradeYear:'',majorId:'',termId:'51'}
  const pending=page.createBatch();await Promise.resolve()
  page.$route.query={termId:'52'};await page.loadDraftTerm()
  finish({code:0,data:{list:[{batchId:'22',batchName:'审核',termId:'51'}],total:1}});await pending
  assert.equal(page.batch,null);assert.equal(page.draft.termId,'52');assert.equal(successes.length,0)
  assert.equal(page.pendingCommand.kind,'create');assert.equal(page.creating,false)
})

test('旧学期创建回读的迟到拒绝不会清除新学期事实或错误提示',async()=>{
  let reject
  const {page,errors}=batchInstance({createGradBatch:async()=>({code:0,data:{batchId:'22'}}),listGradBatches:()=>new Promise((_resolve,fail)=>{reject=fail}),getTermDetail:async id=>({code:0,data:{termId:id}})})
  page.draft={batchName:'审核',gradeYear:'',majorId:'',termId:'51'}
  const pending=page.createBatch();await Promise.resolve()
  page.$route.query={termId:'52'};await page.loadDraftTerm()
  reject({code:403});await pending
  assert.equal(page.draft.termId,'52');assert.equal(page.termError,'');assert.equal(errors.length,0)
  assert.equal(page.pendingCommand.kind,'create');assert.equal(page.creating,false)
})

test('毕业两页只展示正式学期；历史空关联不猜测、不补写',()=>{
  const {page}=batchInstance()
  const legacy={batchId:'12',termId:null,termName:'不能拿此名称冒充关联'}
  assert.equal(page.batchTermLabel(legacy),'历史批次，所属学期待核对')
  const audit=instance();audit.batches=[legacy]
  assert.equal(audit.currentBatchTermLabel,'历史批次，所属学期待核对')
  legacy.termId='51';legacy.termName='2025-2026学年第二学期'
  assert.equal(audit.currentBatchTermLabel,legacy.termName)
  assert.equal(page.batchTermLabel(legacy),legacy.termName)
  const batchSource=fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaGraduationBatchView.vue',import.meta.url),'utf8')
  assert.match(batchSource,/<AppTermEntityPicker[^>]*@update:model-value="selectTerm"/)
  assert.match(batchSource,/#cell-termName[\s\S]*?batchTermLabel\(row\)/)
  assert.match(fs.readFileSync(new URL('../src/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue',import.meta.url),'utf8'),/所属学期：\{\{ currentBatchTermLabel \}\}/)
})

test('进入审核与返回批次页沿正式批次携带学期，历史空关联不借用旧URL学期',()=>{
  const targets=[],{page}=batchInstance()
  page.$router.push=target=>targets.push(target)
  page.enterAudit({batchId:'12',termId:'51'},'results')
  assert.equal(targets[0].query.termId,'51');assert.equal(targets[0].query.batchId,'12')
  const audit=instance();audit.$router={push:target=>targets.push(target)}
  audit.$route.query.termId='99';audit.batches=[{batchId:'12',termId:null}]
  audit.returnToBatchQueue();assert.deepEqual(targets[1].query,{})
  audit.batches[0].termId='52';audit.returnToBatchQueue();assert.equal(targets[2].query.termId,'52')
  audit.$route.query={batchId:'12',returnTo:'/admin/academic-affairs/graduation/12/results?termId=52'}
  assert.equal(audit.returnToResult,audit.$route.query.returnTo)
  audit.returnToBatchQueue();assert.equal(targets[3],audit.$route.query.returnTo)
  audit.$route.query.returnTo='/admin/academic-affairs/graduation/13/results?termId=52'
  assert.equal(audit.returnToResult,'')
})

test('毕业名单展示正式学号而不是学生内部编号',()=>{
  const vm=instance()
  const columns=Object.values(vm).filter(Array.isArray).flat().filter(item=>item?.title==='学号')
  assert.ok(columns.length>=4)
  assert.ok(columns.every(item=>item.key==='studentNo'))
})

test('毕业批次和学籍证据使用中文业务说明',()=>{
  const vm=instance()
  assert.equal(vm.batchOptions[0].label,'验收批次（已预审，应审 2）')
  assert.equal(vm.evidenceText('student_status=NORMAL'),'学籍状态：正常在籍')
  assert.equal(vm.evidenceText('student_status=REGISTERED'),'学籍状态：已注册')
  assert.equal(vm.evidenceText('student_status=RETAINED'),'学籍状态：留级')
  assert.equal(vm.evidenceText('已得 6.0/2.0 学分'),'已得 6.0/2.0 学分')
})

test('历史毕设和学工归档证据按业务项展示中文且不改其他提醒',()=>{
  const vm=instance()
  assert.equal(vm.evidenceText('毕设学生已归档，正式成绩已发布且通过，FILED 归档清单有效','GRADUATION_DESIGN'),
    '毕设学生已归档，正式成绩已发布且通过，已备案的归档清单有效')
  assert.equal(vm.evidenceText('存在毕设记录，但未同时满足学生归档、PUBLISHED 及格成绩和有效 FILED 归档','GRADUATION_DESIGN'),
    '存在毕设记录，但未同时满足学生归档、正式成绩已发布且及格、归档清单已备案并有效')
  assert.equal(vm.evidenceText('学工归档包未生成（不阻断，人工复核）','ARCHIVE'),
    '学工归档包未生成（正式毕业资格审核暂不能通过，请核对学工归档）')
  assert.equal(vm.evidenceText('学工归档包已归档 status=ARCHIVED','ARCHIVE'),'学工归档包已归档')
  assert.equal(vm.evidenceText('学工归档包待补齐 status=PENDING_SUPPLEMENT','ARCHIVE'),
    '学工归档包待补齐（待补材料）')
  assert.equal(vm.evidenceText('学工归档包未生成（不阻断，人工复核）','EMPLOYMENT'),
    '学工归档包未生成（不阻断，人工复核）')
  assert.equal(vm.evidenceText('待财务回填结清状态（本项不阻断）','FEE'),
    '待财务回填结清状态（本项不阻断）')
})
