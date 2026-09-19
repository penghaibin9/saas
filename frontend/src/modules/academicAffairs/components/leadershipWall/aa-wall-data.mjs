/** Read-only, audited bafc9db. No production sample values or personal warning details. */
export const BASELINE = 'bafc9db2f48e98a1ac906a4f88cf37fce39915ce';
export const STATES = ['OK','MISSING','INVALID','ERROR','RESTRICTED','NO_DATA','LOADING'];
export const ENDPOINTS = Object.freeze({
  context: {path:'/rbac/current-context',permission:null},
  brand: {path:'/tenant/brand',permission:null},
  term: {path:'/academic-affairs/terms/current',permission:'academicAffairs.term.view'},
  reminders: {path:'/academic-affairs/dashboard/reminders',permission:'academicAffairs.dashboard.view'},
  readiness: {path:'/academic-affairs/dashboard/readiness',permission:'academicAffairs.dashboard.view'},
  quality: {path:'/academic-affairs/quality/dashboard',permission:'academicAffairs.quality.dashboard.view'}
});
export const DESTINATIONS = Object.freeze({
  teaching:'aa-schedule',resource:'aa-classrooms',grade:'aa-grade-overview',exams:'aa-exam',
  warning:'aa-warnings',changes:'aa-schedule-change-ledger',quality:'aa-quality',
  readiness:'aa-dashboard',trends:'aa-stats'
});
// Contract entries: id / label / unit / endpoint / JSON path / definition / route key.
export const METRICS = [
 ['todayTotal','今日排课课次','课次','reminders','todayTeaching.totalToday','有效课表项数，不是课程门数，也不是实际上课次数。','teaching'],
 ['teacherCount','排课涉及教师','人','reminders','todayTeaching.teacherCount','按 teacher_key 去重的排课教师，不代表到课人数。','teaching'],
 ['classCount','排课涉及班级','个','reminders','todayTeaching.classCount','今日课表 class_id 去重；不代表上课学生数。','teaching'],
 ['occupiedRooms','今日占用教室','间','reminders','resourceOccupancy.occupiedToday','今日排课/已通过预约匹配 AVAILABLE 教室字典；不是当前实时占用。','resource'],
 ['gradeSubmittedRate','成绩提交率','%','reminders','gradeProgress.submittedRate','(SUBMITTED+ACADEMIC_REVIEW+PUBLISHED)/totalTasks；累计任务口径，已归档不自动并入。','grade'],
 ['pendingChanges','在途调停课','单','reminders','scheduleChangeReminders.count','SUBMITTED/COLLEGE_REVIEW/ACADEMIC_REVIEW 全量计数；不是今日次数。','changes'],
 ['warningCount','待处置学业预警','条','reminders','warningReminders.count','ACTIVE 且 PENDING_HANDLE 的记录数，不是学生去重人数。','warning'],
 ['notStarted','未开始','课次','reminders','todayTeaching.notStarted','按课程开始时间判定；不代表到课。','teaching'],
 ['inProgress','按课表进行中','课次','reminders','todayTeaching.inProgress','按节次时刻判定，不是考勤或实际执行证明。','teaching'],
 ['ended','按课表已结束','课次','reminders','todayTeaching.ended','按节次结束时刻判定。','teaching'],
 ['unknownSlots','时间未确定','课次','reminders','derived: totalToday-notStarted-inProgress-ended','完整同口径总量的剩余值；不得把缺少作息时间当已结束。','teaching'],
 ['adjustedToday','调课关联课位','课位','reminders','todayTeaching.adjustedCount','今日有效课表中带 change_id 的课位数，不是调停课申请单数。','changes'],
 ['examToday','今日考试','项','reminders','todayTeaching.examCount','已确认考试课程数，批次 ARRANGED/PUBLISHED。','exams'],
 ['roomTexts','排课教室文本','项','reminders','todayTeaching.roomCount','classroom_text 去重，不用于计算教室占用率。','resource'],
 ['roomTotal','可用教室字典','间','reminders','resourceOccupancy.totalRooms','AaClassroom.status=AVAILABLE 的字典教室数，不是学校所有物理教室。','resource'],
 ['roomRate','今日占用比例','%','reminders','resourceOccupancy.occupancyRate','后端值范围0–100；分母为0显示暂无口径；比例越界拒绝展示。','resource'],
 ['unmatchedRooms','未匹配教室文本','项','reminders','resourceOccupancy.unmatchedCount','无法匹配教室字典的不同文本；不解释为真实空闲。','resource'],
 ['gradeTotal','成绩任务总数','项','reminders','gradeProgress.totalTasks','当前学校范围内累计成绩任务；接口没有 termId 入参。','grade'],
 ['gradeSubmitted','已提交/审核/发布','项','reminders','derived: counts.SUBMITTED+ACADEMIC_REVIEW+PUBLISHED','与提交率同一稀疏状态计数；不以预览行数充当总量。','grade'],
 ['gradePublished','成绩已发布','项','reminders','gradeProgress.counts.PUBLISHED','当前状态已发布的成绩任务。','grade'],
 ['gradeInputting','成绩录入中','项','reminders','gradeProgress.counts.INPUTTING','当前状态录入中的成绩任务。','grade'],
 ['gradeNotStarted','成绩未开始','项','reminders','gradeProgress.counts.NOT_STARTED','当前状态未开始的成绩任务。','grade'],
 ['gradeReturned','成绩已退回','项','reminders','gradeProgress.counts.RETURNED','当前状态已退回的成绩任务。','grade'],
 ['gradeArchived','成绩已归档','项','reminders','gradeProgress.counts.ARCHIVED','与已发布分开展示，不添加到原后端 submittedRate。','grade'],
 ['examUpcoming','近期考试课程','项','reminders','examReminders.count','未来 windowDays 窗口内已确认考试课程，明细最多10项。','exams'],
 ['blockers','运行检查阻断','项','readiness','blockerCount','多规则命中数量的汇总；不作为去重事故/人数。','readiness'],
 ['readinessRisks','运行检查风险','项','readiness','riskCount','多规则命中数量汇总；不同规则可能涉及同一对象。','readiness'],
 ['ruleItems','需关注规则','条','readiness','itemCount','规则结果条数，与各规则 count 的合计不同。','readiness'],
 ['failRate','成绩记录挂科率','%','quality','indicators[key=failRate].value','累计台账成绩口径；无可靠学期映射，不标注本学期。','quality'],
 ['programRate','培养方案发布率','%','quality','indicators[key=programPublishRate].value','累计方案口径；PUBLISHED/ENABLED 占全部方案。','quality'],
 ['taskRate','教学任务确认率','%','quality','indicators[key=taskCompleteRate].value','累计教学任务确认口径，不是排课执行率。','quality'],
 ['qualityGradeRate','成绩任务发布率','%','quality','indicators[key=gradePublishRate].value','质量接口累计任务口径，与成绩提交率概念不同。','quality'],
 ['enabledCourses','启用课程','门','quality','indicators[key=courseEnabled].value','ENABLED 课程数，不能改名今日开课门数。','quality'],
 ['qualityWarnings','在办学业预警','条','quality','indicators[key=warningCount].value','质量接口 status!=CLOSED；不同于待处置 PENDING_HANDLE，不能混算。','quality']
].map(([id,label,unit,endpoint,path,definition,route])=>({id,label,unit,endpoint,path,definition,route}));
export const record = x => x !== null && typeof x === 'object' && !Array.isArray(x);
export function num(x,{integer=false,max=Infinity}={}) {
  return typeof x==='number' && Number.isFinite(x) && x>=0 && x<=max && (!integer || Number.isSafeInteger(x)) ? x : null;
}
export function count(x){return num(x,{integer:true});}
const at=(obj,path)=>path.split('.').reduce((a,k)=>record(a)?a[k]:undefined,obj);
export function domain(state='MISSING',data=null,note=''){return {state,data,note};}
export function safeText(x,max=240){return typeof x==='string'?x.slice(0,max):'';}
const hasUrlControl = value => Array.from(value).some(char=>char.charCodeAt(0)<=32);
export function safeAsset(x,{blob=false}={}) {
  if(typeof x!=='string'||x.length>12*1024*1024)return '';
  if(blob && /^blob:/.test(x))return x;
  if(/^data:image\/(png|jpeg|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$/.test(x))return x;
  if(/^https:\/\//.test(x))return x;
  if(x.startsWith('/') && !x.startsWith('//') && !hasUrlControl(x) && !/[\\<>"']/.test(x))return x;
  return '';
}
export function routeTarget(x) {
  if(typeof x!=='string' || hasUrlControl(x) || /[\\<>"']/.test(x))return null;
  if(/^aa-[a-z0-9-]+$/.test(x))return {name:x};
  try {
    const decoded=decodeURIComponent(x);
    if(/[\\<>"']/.test(decoded)||decoded.split(/[/?#]/).some(k=>k==='..'||k==='.')||/%2f|%5c/i.test(x))return null;
    const u=new URL(x,'https://local.invalid');
    if(!x.startsWith('/')||u.origin!=='https://local.invalid')return null;
    if(u.pathname==='/admin/academic-affairs'||u.pathname.startsWith('/admin/academic-affairs/')) {
      // Readiness uses this historical plural path; the audited canonical route is singular.
      const path=u.pathname==='/admin/academic-affairs/schedule-changes'
        ? '/admin/academic-affairs/schedule-change' : u.pathname;
      return {path:path+u.search+u.hash};
    }
  } catch { return null; }
  return null;
}
export function identityKey(u) {
  if(!record(u))return '';
  return JSON.stringify([String(u.tenantId||''),String(u.userId||u.loginName||''),String(u.currentRoleCode||''),String(u.activeContextId||'')]);
}
export const STATE_LABELS={OK:'已更新',MISSING:'暂未提供',INVALID:'数据待核对',ERROR:'读取失败',RESTRICTED:'当前范围不可见',NO_DATA:'暂无统计对象',LOADING:'正在读取'};
// A successful empty list is different from a missing or failed response.
export function previewState(sourceState, items, total, mismatch=false) {
  if(sourceState!=='OK')return sourceState;
  if(mismatch)return 'INVALID';
  if(!Array.isArray(items)||count(total)===null)return 'MISSING';
  if(items.length>total||items.some(x=>!record(x)))return 'INVALID';
  return total===0?'NO_DATA':items.length?'OK':'MISSING';
}
export function emptyView(state='LOADING',note='') {
  return buildViewModel({reminders:domain(state),readiness:domain(state),quality:domain(state),term:domain(state),meta:{note}});
}
export function buildViewModel(input={}) {
  input=record(input)?input:{};
  const diag=[];
  const sources={};
  for(const key of ['reminders','readiness','quality','term'])sources[key]=input[key]||domain();
  let r=sources.reminders.data;
  if(sources.reminders.state==='OK') {
    if(!record(r))sources.reminders=domain('INVALID',null,'聚合返回结构异常');
    else if(r.scopeRestricted===true)sources.reminders=domain('RESTRICTED',null,safeText(r.scopeNote));
    else if(r.scopeRestricted!==false)sources.reminders=domain('INVALID',null,'缺少范围标记，不展示汇总');
  }
  for(const key of ['term','quality','readiness']) {
    if(sources[key].state==='OK'&&!record(sources[key].data))sources[key]=domain('INVALID',null,'返回结构异常');
  }
  if(sources.reminders.state==='RESTRICTED')sources.quality=domain('RESTRICTED',null,'学校级质量汇总不向受限范围降级放开');
  r=sources.reminders.state==='OK'?sources.reminders.data:{};
  const rid=sources.readiness.data?.term?.termId,tid=sources.term.data?.termId;
  if(sources.readiness.state==='OK'&&tid&&rid&&String(rid)!==String(tid)) {sources.readiness=domain('INVALID',null,'运行检查学期与公共学期不一致');diag.push('运行检查学期不一致');}
  const d=sources.readiness.state==='OK'&&record(sources.readiness.data)?sources.readiness.data:{};
  const q=sources.quality.state==='OK'&&record(sources.quality.data)?sources.quality.data:{};
  const t=sources.term.state==='OK'&&record(sources.term.data)?sources.term.data:{};
  const metrics={};
  const put=(spec,value,forceState,detail)=>{
    let state=forceState||sources[spec.endpoint].state;
    if(state==='OK')state=value===undefined||value===null?'MISSING':(num(value,{integer:spec.unit!=='%',max:spec.unit==='%'?100:Infinity})===null?'INVALID':'OK');
    metrics[spec.id]={...spec,value:state==='OK'?value:null,state,note:detail||STATE_LABELS[state]||spec.definition};
  };
  for(const s of METRICS) {
    if(s.path.startsWith('derived:')||s.path.includes('[key=')||s.path.startsWith('gradeProgress.counts.'))continue;
    put(s,at(sources[s.endpoint].state==='OK'?sources[s.endpoint].data:null,s.path));
  }
  const spec=id=>METRICS.find(s=>s.id===id);
  const force=(ids,state,detail)=>ids.forEach(id=>put(spec(id),null,state,detail));
  const val=id=>metrics[id]?.value??null;
  const tt=record(r.todayTeaching)?r.todayTeaching:{};
  const parts=['totalToday','notStarted','inProgress','ended'].map(k=>count(tt[k]));
  const unknown=parts.every(v=>v!==null)?parts[0]-parts[1]-parts[2]-parts[3]:null;
  put(spec('unknownSlots'),unknown,unknown!==null&&unknown<0?'INVALID':undefined);
  if(unknown!==null&&unknown<0){force(['todayTotal','notStarted','inProgress','ended','unknownSlots'],'INVALID','课时状态数大于总量');diag.push('课时状态分布不自洽');}
  const gp=record(r.gradeProgress)?r.gradeProgress:{};
  const counts=gp.counts; const total=count(gp.totalTasks);
  const validCounts=record(counts)&&Object.values(counts).every(v=>count(v)!==null);
  const sumCounts=validCounts?Object.values(counts).reduce((a,b)=>a+b,0):null;
  const gradeIntegrity=validCounts&&total!==null&&sumCounts===total;
  for(const s of METRICS.filter(s=>s.path.startsWith('gradeProgress.counts.'))) {
    const k=s.path.split('.').at(-1);
    put(s,gradeIntegrity?(counts[k]??0):null, sources.reminders.state==='OK'&&!gradeIntegrity?'INVALID':undefined,'累计任务状态，接口稀疏字典缺项=0；必须先通过总量对账');
  }
  const submitted=gradeIntegrity?['SUBMITTED','ACADEMIC_REVIEW','PUBLISHED'].reduce((a,k)=>a+(counts[k]??0),0):null;
  put(spec('gradeSubmitted'),submitted,sources.reminders.state==='OK'&&!gradeIntegrity?'INVALID':undefined);
  if(sources.reminders.state==='OK'){
    if(total===0)force(['gradeSubmittedRate'],'NO_DATA','暂无成绩任务，提交率暂不计算');
    else if(!gradeIntegrity||val('gradeSubmittedRate')===null||Math.abs(submitted/total*100-val('gradeSubmittedRate'))>.15){force(['gradeSubmittedRate'],'INVALID','成绩状态与提交率不一致');diag.push('成绩状态/比例待核查');}
  }
  const ro=record(r.resourceOccupancy)?r.resourceOccupancy:{};
  const rt=count(ro.totalRooms), oc=count(ro.occupiedToday), rate=num(ro.occupancyRate,{max:100});
  if(sources.reminders.state==='OK'){
    if(rt===0)force(['roomRate'],'NO_DATA','尚未配置可用教室');
    else if(rt===null||oc===null||oc>rt||rate===null||Math.abs(oc/rt*100-rate)>.15){force(['occupiedRooms','roomRate'],'INVALID','教室总量/占用数/比例需对账');diag.push('教室占用口径待核查');}
  }
  const inds=Array.isArray(q.indicators)?q.indicators.filter(record):[];
  for(const s of METRICS.filter(s=>s.path.includes('[key='))) {
    const key=s.path.match(/key=([^\]]+)/)[1];const matches=inds.filter(x=>x.key===key);const row=matches.length===1?matches[0]:null;
    put(s,row?.value,matches.length>1?'INVALID':undefined);
    if(s.unit==='%'&&row) {
      const den=count(row.denominator), numerator=count(row.numerator);
      if(den===0)force([s.id],'NO_DATA','暂无可统计的业务记录');
      else if(den===null||numerator===null||numerator>den||val(s.id)===null||Math.abs(numerator/den*100-val(s.id))>.15)force([s.id],'INVALID','质量指标分子/分母/比例不一致');
    }
  }
  // Course timing and resource data currently use the legacy term flag, compare to public resolver.
  const expected=t.yearCode&&t.termNo?`${t.yearCode} 第 ${t.termNo} 学期`:'';
  const reported=safeText(tt.termLabel);
  let termMismatch=!!(expected&&reported&&expected!==reported);
  if(termMismatch){
    force(['todayTotal','teacherCount','classCount','notStarted','inProgress','ended','unknownSlots','adjustedToday','examToday','roomTexts','occupiedRooms','roomRate'],'INVALID','学期治理与今日教学上下文不一致');
    diag.push('公共当前学期与今日教学学期不一致');
  }
  const toSegment=(key,label,value)=>({key,label,value});
  const teachingSegments=[['notStarted','未开始'],['inProgress','进行中'],['ended','已结束'],['unknownSlots','时间未确定']].map(([k,l])=>toSegment(k,l,val(k)));
  const gradeSegments=gradeIntegrity?[
    ['SUBMITTED','学院审核中'],['ACADEMIC_REVIEW','教务审核中'],['PUBLISHED','已发布'],['INPUTTING','录入中'],['NOT_STARTED','未开始'],['RETURNED','已退回'],['ARCHIVED','已归档']
  ].map(([k,l])=>toSegment(k,l,counts[k]??0)).concat(Object.entries(counts).filter(([k])=>!['SUBMITTED','ACADEMIC_REVIEW','PUBLISHED','INPUTTING','NOT_STARTED','RETURNED','ARCHIVED'].includes(k)).map(([k,c])=>toSegment(k,'其他状态',c))):[];
  const resources=!termMismatch&&Array.isArray(ro.items)?ro.items.filter(x=>record(x)&&count(x.useCount)!==null).map(x=>({classroom:safeText(x.classroom,90),useCount:x.useCount,slots:Array.isArray(x.slots)?x.slots.filter(v=>count(v)!==null):[]})).slice(0,10):[];
  const tc=record(r.todayCourses)?r.todayCourses:{};
  const courses=!termMismatch&&Array.isArray(tc.items)?tc.items.filter(record).map(x=>({id:safeText(x.itemId,50),slotNo:count(x.slotNo),startTime:safeText(x.startTime,10),endTime:safeText(x.endTime,10),courseName:safeText(x.courseName,120),className:safeText(x.className,120),classroom:safeText(x.classroom,90),runStatus:['NOT_STARTED','IN_PROGRESS','ENDED','UNKNOWN'].includes(x.runStatus)?x.runStatus:'UNKNOWN',changed:x.changed===true})).slice(0,30):[];
  const er=record(r.examReminders)?r.examReminders:{};
  const exams=Array.isArray(er.items)?er.items.filter(record).slice(0,10).map(x=>({id:safeText(x.examCourseId,50),courseName:safeText(x.courseName,120),className:safeText(x.className,90),date:safeText(x.examDate,12),startTime:safeText(x.startTime,10),endTime:safeText(x.endTime,10),status:['ARRANGED','PUBLISHED'].includes(x.batchStatus)?x.batchStatus:'UNKNOWN'})):[];
  const trends=[];
  const dt=record(r.dataTrends)?r.dataTrends:{};
  for(const s of Array.isArray(dt.series)?dt.series.filter(record):[]){
    if(!['statusChange','scheduleChange','gradeSubmit','warning'].includes(s.key)||!Array.isArray(s.points))continue;
    const valid=s.points.every(p=>record(p)&&/^\d{4}-\d{2}-\d{2}$/.test(p.date)&&count(p.value)!==null);
    if(!valid){diag.push('趋势序列含未知点，未补0或插值');continue;}
    trends.push({key:s.key,label:safeText(s.label,40),points:s.points.slice(-30).map(p=>({date:p.date,value:p.value}))});
  }
  const issues=Array.isArray(d.items)?d.items.filter(record).map(x=>({key:safeText(x.key,100),title:safeText(x.title,180),severity:x.severity==='BLOCKER'?'BLOCKER':'RISK',count:count(x.count),ownerRole:safeText(x.ownerRole,100),deadline:safeText(x.deadlineLabel||x.deadline,80)||'未配置',target:routeTarget(x.route)})):[];
  const restricted=sources.reminders.state==='RESTRICTED';
  const previews={
    courses:previewState(sources.reminders.state,tc.items,count(tc.count),termMismatch),
    resources:previewState(sources.reminders.state,ro.items,count(ro.occupiedToday),termMismatch),
    exams:previewState(sources.reminders.state,er.items,count(er.count))
  };
  const essential=['todayTotal','teacherCount','classCount','occupiedRooms','gradeSubmittedRate','pendingChanges','warningCount'];
  const okN=essential.filter(k=>['OK','NO_DATA'].includes(metrics[k]?.state)).length;
  const optionalIssue=Object.values(sources).some(x=>x.state!=='OK')||Object.values(metrics).some(x=>!['OK','NO_DATA'].includes(x.state))||Object.values(previews).some(x=>!['OK','NO_DATA'].includes(x));
  const state=restricted?'RESTRICTED':okN===essential.length&&!optionalIssue?'READY':okN?'PARTIAL':sources.reminders.state==='LOADING'?'LOADING':'UNAVAILABLE';
  return {
    state,metrics,teachingSegments,gradeSegments,resources,courses,exams,trends,issues,
    metadata:{
      isSample:input.meta?.isSample===true,
      previews,
      hasNoData:Object.values(metrics).some(x=>x.state==='NO_DATA'),
      schoolName:safeText(input.meta?.schoolName,100),
      scope:safeText(input.meta?.scope,120)||safeText(r.scopeNote,120),
      currentAuthority:safeText(t.currentAuthority,80),
      sourceTime:safeText(r.generatedAt,64),
      termId:safeText(t.termId,80),termLabel:expected||safeText(d.term?.termLabel,100)||'当前学期未确认',
      dateLabel:safeText(tt.dateLabel,50),weekNo:count(tt.weekNo),
      status:safeText(d.status,30),stageLabel:safeText(d.stageLabel,60),
      conclusion:safeText(d.conclusion,200),
      notes:[safeText(input.meta?.note),safeText(sources.reminders.note),safeText(tt.note),safeText(ro.note),...diag].filter(Boolean),
      courseCount:count(tc.count),courseShown:count(tc.shown),resourceShown:resources.length,
      examWindow:count(er.windowDays),termMismatch,
      qualityScope:'累计口径（不带学期筛选）',
      spatialStatus:'MISSING',
      sources:Object.fromEntries(Object.entries(sources).map(([k,v])=>[k,{state:v.state,note:safeText(v.note)}]))
    }
  };
}
