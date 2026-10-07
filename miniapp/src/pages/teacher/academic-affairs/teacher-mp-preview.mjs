// Local layout preview only. Never imported by a miniapp page or service.
import fs from 'node:fs'
import path from 'node:path'
import vm from 'node:vm'
import { fileURLToPath } from 'node:url'
import * as Vue from 'vue'
import { compile } from '@vue/compiler-dom'
import { parse, compileStyle } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'

const here = path.dirname(fileURLToPath(import.meta.url))
const miniapp = path.resolve(here, '../../../..')
const root = path.dirname(miniapp)
const teacher = path.resolve(here, '..')
const course = { itemId: 101, scheduleItemId: 101, courseName: '机械制图与计算机辅助设计（测试课程）', courseCode: 'TEST-01', className: '机电测试班', teachingClassName: '机电测试班', classroom: '实训楼 302', weekday: 2, slotNo: 3, startWeek: 1, endWeek: 18, weekParity: 'ALL', startTime: '10:10', endTime: '10:55', attendanceRoute: '/pages/teacher/academic-affairs/attendance?sessionId=501', attendanceActionLabel: '开始点名' }
const task = { ...course, taskId: 201, courseVersion: '测试版本 2026', weeklyHours: 4, totalHours: 72, expectedStudents: 32, status: 'ASSIGNED' }
const student = { studentId: 301, realName: '测试学生甲', studentNo: 'TEST0001', status: 'PRESENT' }
const gradeTask = { gradeTaskId: 401, courseName: course.courseName, termCode: '2026-2027-1', usualRatio: 40, finalRatio: 60, midtermRatio: 0, passLine: 60, status: 'INPUTTING' }
const scheduleChange = { changeId: 601, courseName: course.courseName, teacherName: '测试教师', className: course.className, changeType: 'ADJUST', changeTypeLabel: '调课', status: 'COLLEGE_REVIEW', currentNode: 'COLLEGE_REVIEW', origin: course, target: { ...course, weekday: 4, slotNo: 5, classroom: '实训楼 405' }, reason: '测试申请：校内教学安排调整，需要核对正式目标课位。' }
const statusChange = { changeId: 602, realName: '测试学生甲', changeType: 'TRANSFER_CLASS', changeTypeLabel: '转班', status: 'IN_REVIEW', currentNode: 'COLLEGE_REVIEW', fromStatus: '在籍', toStatus: '在籍（班级调整）', effectiveDate: '2026-09-15', reason: '测试申请：按本人申请核对班级调整依据。' }
const defer = { deferId: 603, studentName: '测试学生乙', courseName: course.courseName, status: 'TEACHER_CONFIRM', reasonType: '身体原因', reason: '测试材料：因身体原因申请缓考，材料按正式流程核对。', applyAt: '2026-09-08T08:30:00' }
const warning = { warningId: 604, studentName: '测试学生丙', className: course.className, type: 'ACADEMIC', typeLabel: '学业预警', level: 'HIGH', levelLabel: '高', status: 'PENDING_HANDLE', statusLabel: '待处理', owner: '测试教师', reason: '测试预警：本学期多门课程学习进度需持续跟进。', triggerTime: '2026-09-08T08:30:00', deadline: '2026-09-15' }
const invig = { invigilatorId: 701, courseName: course.courseName, className: course.className, classroom: '教学楼 201', examDate: '2026-09-20', startTime: '09:00', endTime: '11:00', role: 'CHIEF', confirmStatus: 'CONFIRMED', workStatus: 'UPCOMING' }
const evaluation = { taskId: 801, courseName: course.courseName, teacherName: '测试教师', batchStatus: '评价开放中', status: 'PENDING' }
const result = { resultId: 901, courseName: course.courseName, batchName: '测试教学评价批次', studentAvg: 88.5, studentCount: 32, level: 'GOOD' }
const gradeData = { tasks: [gradeTask], loaded: true, active: gradeTask, roster: [student, { ...student, studentId: 302, realName: '测试学生乙', studentNo: 'TEST0002' }], rosterState: 'ready', scores: { 301: { usualScore: '85', finalScore: '90', totalScore: 88, exceptionFlag: 'NORMAL' }, 302: { usualScore: '', finalScore: '', totalScore: '', exceptionFlag: 'DEFERRED' } }, dirty: { 301: true } }
const homeData = { scheduleItems: [course], todayItems: [course], timeBands: [course], currentWeek: 2, calendarSource: 'NORMAL', todayDate: '2026-09-08', clockDate: '2026-09-08', clockMinute: 590, counts: { grade: 2, academicTask: 1 }, taskDetails: { grade: course.courseName, academicTask: course.courseName }, invigilationWorkbench: { items: [invig], upcomingCount: 1, total: 1 } }
const definitions = [
 ['TW-001','我的教学','academic-affairs/index.vue',homeData],
 ['TW-002','我的课表','my-schedule/index.vue',{items:[course],todayItems:[course],todayDate:'2026-09-08',timeBands:[course],currentWeek:2,selectedWeek:2,selectedDay:2,teachingWeeks:18,termCode:'2026-2027-1'}],
 ['TW-003','教学任务确认','academic-task/index.vue',{tasks:[task]}],
 ['TW-004','课堂考勤','academic-affairs/attendance.vue',{sessions:[{sessionId:501,...course,sessionDate:'2026-09-08',status:'DRAFT',totalCount:32}],loaded:true}],
 ['TW-005','成绩录入','academic-affairs/grade-entry.vue',{tasks:[gradeTask],loaded:true}],
 ['TW-006','调停课办理','schedule-change/index.vue',{changes:[scheduleChange]}],
 ['TW-007','调停课审批','academic-affairs/schedule-change-review.vue',{list:[scheduleChange]}],
 ['TW-008','学籍异动审批','academic-affairs/status-change-review.vue',{list:[statusChange]}],
 ['TW-009','缓考审批','exam-defer/index.vue',{list:[defer]}],
 ['TW-010','学业预警跟进','academic-warning/index.vue',{list:[warning]}],
 ['TW-011','工作量申报','academic-affairs/workload.vue',{d:{items:[{declarationId:1001,categoryLabel:'监考',hours:4,termCode:'2026-2027-1',status:'SUBMITTED',description:'测试申报：期末监考两场。'}]}}],
 ['TW-012','我的正式课次','my-schedule/index.vue',{items:[course],todayItems:[course],lessonId:'101',lessonIsToday:true,todayDate:'2026-09-08',timeBands:[course],termCode:'2026-2027-1'}],
 ['TW-013','教学任务核对','academic-task/index.vue',{tasks:[task],detailId:'201'}],
 ['TW-014','本课次点名','academic-affairs/attendance.vue',{sessions:[],loaded:true,active:{sessionId:501,...course,sessionDate:'2026-09-08',status:'DRAFT'},items:[student,{...student,studentId:302,realName:'测试学生乙',studentNo:'TEST0002',status:'ABSENT'}]}],
 ['TW-015','逐人成绩录入','academic-affairs/grade-entry.vue',gradeData],
 ['TW-016','提交前核验','academic-affairs/grade-entry.vue',{...gradeData,dirty:{},reviewMode:true,qualityReport:{canSubmit:false,summary:'测试核验：请核对缺失成绩后再次提交。',rosterCount:32,missingCount:1,incompleteCount:1,specialCount:2,deadline:'2026-09-30T18:00:00',issues:[{studentId:302,realName:'测试学生乙',code:'MISSING',message:'成绩项尚未填写完整'}]}}],
 ['TW-017','调停课申请','schedule-change/index.vue',{tab:'new',changes:[],items:[course],scheduleState:'ready',reason:'测试申请：教学安排调整。',targetWeekday:'4',targetSlotNo:'5',targetStartWeek:'2',targetEndWeek:'2',targetClassroom:'实训楼405'}],
 ['TW-018','调停课证据核对','academic-affairs/schedule-change-review.vue',{list:[scheduleChange],detailId:'601'}],
 ['TW-019','异动证据核对','academic-affairs/status-change-review.vue',{list:[statusChange],detailId:'602'}],
 ['TW-020','缓考申请核对','exam-defer/index.vue',{list:[defer],detailId:'603'}],
 ['TW-021','追加跟进记录（接口待接入）','academic-warning/index.vue',{list:[warning],detailId:'604'}],
 ['TW-022','提交工作量申报','academic-affairs/workload.vue',{d:{items:[]},showForm:true,form:{hours:'4',termCode:'2026-2027-1',description:'测试申报：监考两场。'},catIndex:1}],
 ['TW-023','我的监考安排','academic-affairs/index.vue',{...homeData,selectedInvigId:'701'}],
 ['TW-024','教学评价','evaluation/index.vue',{tasks:[evaluation],tasksState:'ready'}],
 ['TW-025','填写教学评价','evaluation/index.vue',{tasks:[evaluation],tasksState:'ready',submitTarget:evaluation,score:'88',comment:'测试意见：教学组织清晰，课堂练习充分。'}],
 ['TW-026','评价结果申诉','evaluation/index.vue',{tab:'results',resultsState:'ready',results:[result],appealTarget:result,appealReason:'测试申诉：申请核对本次评价统计范围。'}]
]
const esc = (s) => String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;')
const components = {
 MobileNavBar: { props:['title','subtitle'], setup:p=>()=>Vue.h('header',{class:'preview-nav'},[Vue.h('b',p.title),Vue.h('small',p.subtitle)]) },
 MobileTabBar: { setup:()=>()=>Vue.h('nav',{class:'preview-tabbar'},'工作台　　待办　　消息　　我的') },
 MobileSafeAreaBar: { setup:(_,c)=>()=>Vue.h('footer',{class:'preview-actions'},c.slots.default?.()) },
 MobileGlobalState: { props:['state','title','description'], emits:['retry'], setup:(p,c)=>()=>['loading','error','empty','restricted'].includes(p.state) ? Vue.h('div',{class:'preview-state'},[p.title,p.description]) : Vue.h('div',c.slots.default?.()) },
 MobileStatusTag: { props:['label','status','type'], setup:p=>()=>Vue.h('span',{class:'preview-tag'},p.label||p.status||'—') },
 AppInlineAlert: { props:['description'], setup:p=>()=>Vue.h('p',{class:'preview-state'},p.description) }
}
let styles = 'view{display:block}text{display:inline}picker{display:block}textarea,input,button{font:inherit}button{cursor:default}*{box-sizing:border-box}'
const assets = path.join(miniapp,'dist/build/h5/assets')
for (const name of fs.readdirSync(assets).filter(n=>n.endsWith('.css'))) styles += fs.readFileSync(path.join(assets,name),'utf8')
let sections = ''
for (const [id,title,file,data] of definitions) {
 const source=fs.readFileSync(path.join(teacher,file),'utf8')
 const {descriptor}=parse(source)
 const sandbox={teacherApi:{},academicGradeEntryApi:{},toast(){},go(){},getStatusBarHeight:()=>20,normalizeError:()=>({text:'测试错误'}),createSubmitLock:()=>({run:fn=>fn()}),useSessionStore:()=>({identity:{userId:1},currentRole:'teacher',realUser:{tenantId:1}})}
 vm.runInNewContext(descriptor.script.content.replace(/^import .*$/gm,'').replace('export default','globalThis.options ='),sandbox)
 const options=sandbox.options
 const originalData=options.data
 options.data=function(){return {...originalData(),state:'ready',...data}}
 const scope='data-v-preview-'+id.toLowerCase()
 options.__scopeId=scope
 options.render=new Function('Vue',compile(descriptor.template.content,{mode:'function',isCustomElement:t=>['view','text','picker','scroll-view'].includes(t)}).code)(Vue)
 options.render._rc=true
 for(const style of descriptor.styles) {
  const compiled=compileStyle({source:style.content,filename:file,id:scope,scoped:style.scoped})
  if(compiled.errors.length)throw compiled.errors[0]
  styles+=compiled.code
 }
 const app=Vue.createSSRApp(options)
 for(const [name,component] of Object.entries(components))app.component(name,component)
 app.config.warnHandler=(message)=>{ if(!message.includes('Symbol(')) console.error(id+': '+message) }
 const body=await renderToString(app)
 sections+='<section class="screen" id="'+id+'"><h2>'+id+' · '+esc(title)+'</h2><div class="phone">'+body+'</div></section>'
}
const navigation=definitions.map(([id,title])=>'<option value="'+id+'">'+id+' '+esc(title)+'</option>').join('')
const html='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>教师微信 · 26 视角布局预览</title><style>'+styles+`
body{margin:0;background:#e9eef2;font-family:"Microsoft YaHei",system-ui,sans-serif;color:#172b35}
.preview-toolbar{position:sticky;top:0;z-index:999;background:#102f39;color:white;padding:16px;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
.preview-toolbar small{font-size:12px;color:#bcd3d8}.preview-toolbar select{max-width:100%;padding:10px;border-radius:8px}
.screen{display:none;margin:20px auto;width:393px;max-width:100%}.screen.active{display:block}.screen h2{font-size:15px;padding:0 12px}
.phone{background:#f5f7f9;min-height:820px;border:1px solid #ccd8dc;border-radius:18px;overflow:hidden;padding-bottom:16px;box-shadow:0 14px 48px #183e4920}
.preview-nav{background:#fff;padding:20px 16px;display:flex;flex-direction:column;gap:4px}.preview-nav small{color:#647982;font-size:12px}
.preview-tag{background:#e8f2f2;color:#087e88;border-radius:20px;padding:4px 8px;font-size:12px}
.preview-actions{display:flex;gap:12px;padding:16px;background:white;border-top:1px solid #e1eaec;margin-top:20px}
.preview-actions button{flex:1}.preview-tabbar{text-align:center;padding:20px 6px;color:#55737d;background:white;font-size:13px}
.preview-state{padding:20px;border-radius:12px;background:#fff7e7;color:#795c24;font-size:13px}
`+'</style><div class="preview-toolbar"><b>教师微信 · 26 视角</b><select id="view">'+navigation+'</select><small>测试数据 / 实际页面模板静态渲染 / 共享导航为预览占位 / 控件不发请求</small></div>'+sections+'<script>const select=document.getElementById("view");function show(){const id=location.hash.slice(1)||"TW-001";document.querySelectorAll(".screen").forEach(s=>s.classList.toggle("active",s.id===id));select.value=id;window.scrollTo(0,0);}select.onchange=()=>location.hash=select.value;window.onhashchange=show;show();<\/script></html>'
const output=path.join(root,'teacher-mp-design-preview.html')
fs.writeFileSync(output,html)
console.log('Rendered '+definitions.length+' implementation views: '+output)
