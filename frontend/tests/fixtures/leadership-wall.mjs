/** Explicit visual fixture only. This file is NOT installed in the production app. */
export function makeFixture(){
 const status=['IN_PROGRESS','IN_PROGRESS','ENDED','NOT_STARTED','IN_PROGRESS','UNKNOWN'];
 const courses=['数据结构','大学英语','高等数学','线性代数','思想道德与法治','创新创业实践'];
 const r={scopeRestricted:false,scopeNote:'全校教务范围 · 设计样例',generatedAt:'2026-09-06T08:28:35',
  todayTeaching:{dateLabel:'2026-09-06（周日）',termLabel:'2026-2027 第 1 学期',weekNo:2,totalToday:1268,notStarted:64,inProgress:1092,ended:112,adjustedCount:12,examCount:3,teacherCount:892,classCount:412,roomCount:489,note:''},
  todayCourses:{count:1268,shown:30,items:Array.from({length:30},(_,i)=>({itemId:`c${i+1}`,slotNo:7+i%3,startTime:'15:55',endTime:'16:40',courseName:courses[i%6],className:`软件${2601+i}`,teacherName:'此字段不会传入展示模型',classroom:`明德楼MD${401+i}`,runStatus:status[i%6],changed:i%7===0}))},
  gradeProgress:{totalTasks:1280,counts:{NOT_STARTED:4,INPUTTING:12,SUBMITTED:12,ACADEMIC_REVIEW:6,RETURNED:2,PUBLISHED:1244},submittedRate:98.6,pendingTasks:[]},
  resourceOccupancy:{totalRooms:557,occupiedToday:486,occupancyRate:87.3,unmatchedCount:3,items:Array.from({length:10},(_,i)=>({classroom:`明德楼MD${401+i}`,useCount:3+i%5,slots:[1,3,5,7]})),note:'另有3处排课教室文本未匹配字典'},
  scheduleChangeReminders:{count:12,items:[]},warningReminders:{count:326,items:[{studentName:'敏感样本不可显示',reason:'不应投屏的个人情况'}]},
  examReminders:{count:18,windowDays:14,items:[['09-08','大学英语','PUBLISHED'],['09-10','高等数学','ARRANGED'],['09-12','线性代数','PUBLISHED'],['09-15','大学物理','ARRANGED'],['09-18','思想道德与法治','PUBLISHED']].map(([dt,courseName,batchStatus],i)=>({examCourseId:`e${i}`,examDate:'2026-'+dt,startTime:'09:00',endTime:'11:00',courseName,batchStatus,className:`2026级${i+1}班`}))},
  dataTrends:{days:[],series:[
   {key:'gradeSubmit',label:'成绩提交',points:[24,30,28,35,42,37,30,32,48,52,44,39,53,58]},
   {key:'scheduleChange',label:'调停课申请',points:[14,18,10,9,15,8,16,18,20,13,12,19,15,12]},
   {key:'warning',label:'新增学业预警',points:[8,12,9,7,5,8,6,9,12,8,4,5,7,3]},
   {key:'statusChange',label:'学籍异动申请',points:[6,3,7,5,9,8,12,5,7,4,6,10,5,8]}
  ].map(s=>({...s,points:s.points.map((value,i)=>({date:new Date(Date.UTC(2026,7,24+i)).toISOString().slice(0,10),value}))}))}
 };
 const readiness={term:{termId:'202601',termLabel:'2026-2027 第 1 学期'},stage:'TEACHING',stageLabel:'教学运行',currentWeek:2,today:'2026-09-06',status:'RISK',conclusion:'当前阶段可以继续，仍有需跟进的教务事项',blockerCount:0,riskCount:94,itemCount:5,scopeType:'TENANT_ALL',items:[
  {key:'HIGH_WARNING_PENDING',title:'高等级学业预警待处置',severity:'RISK',count:78,ownerRole:'辅导员 / 学院教务员',deadlineLabel:'未配置明确截止',route:'/admin/academic-affairs/warnings'},
  {key:'SCHEDULE_CHANGE_PENDING',title:'在途调停课申请需跟进',severity:'RISK',count:12,ownerRole:'学院教务员 / 教务处',deadlineLabel:'未配置明确截止',route:'/admin/academic-affairs/schedule-changes'},
  {key:'GRADE_NOT_READY',title:'部分成绩任务尚未提交',severity:'RISK',count:2,ownerRole:'任课教师 / 教务处',deadlineLabel:'2026-09-10',route:'/admin/academic-affairs/grades'},
  {key:'PROGRAM_BINDING',title:'培养方案绑定关系待核查',severity:'RISK',count:1,ownerRole:'教务处',deadlineLabel:'未配置明确截止',route:'/admin/academic-affairs/programs'},
  {key:'EXAM_COURSE',title:'近期考试课程安排待完善',severity:'RISK',count:1,ownerRole:'考务管理员',deadlineLabel:'2026-09-12',route:'/admin/academic-affairs/exams'}
 ]};
 const qi=(key,label,numerator,denominator)=>({key,label,numerator,denominator,value:Math.round(numerator/denominator*10000)/100,unit:'%',appliedFilters:[]});
 const quality={indicators:[qi('failRate','挂科率',182,4280),qi('programPublishRate','培养方案发布率',94,100),qi('taskCompleteRate','教学任务确认率',1150,1280),qi('gradePublishRate','成绩任务发布率',1244,1280),{key:'courseEnabled',value:2146},{key:'warningCount',value:372}],generatedAt:r.generatedAt};
 return {term:{state:'OK',data:{termId:'202601',yearCode:'2026-2027',termNo:1,termName:'2026-2027学年第一学期',isCurrent:true,currentAuthority:'CALENDAR_GOVERNANCE'}},reminders:{state:'OK',data:r},readiness:{state:'OK',data:readiness},quality:{state:'OK',data:quality},meta:{isSample:true,schoolName:'跃科 · 教务中心',scope:'全校范围 · 样例'}};
}
export const VISUAL_SPATIAL={
 usage:{mingde:92,boxue:78,shiyan:65,zhixing:88,qiushi:81},
 floors:[{label:'6F',used:12,total:18},{label:'5F',used:16,total:18},{label:'4F',used:17,total:18},{label:'3F',used:15,total:18},{label:'2F',used:14,total:18},{label:'1F',used:10,total:18}]
};
