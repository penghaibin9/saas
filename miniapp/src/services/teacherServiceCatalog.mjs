// Shared existing teacher entry contract. This catalogue changes presentation, never grants permission.
export const TEACHER_SERVICE_ROUTES = {
        weekly: '/pages/teacher-internship/internship-review/index',
        'review-open': '/pages/teacher/graduation-guide/index?tab=review&kind=proposal',
        'review-mid': '/pages/teacher/graduation-guide/index?tab=midterm',
        'review-result': '/pages/teacher/graduation-guide/index?tab=review&kind=final',
        checkin: '/pages/teacher-internship/internship-review/index?tab=abnormal',
        visit: '/pages/teacher-internship/internship-review/index?tab=visit',
        makeup: '/pages/teacher-internship/internship-approval/index',
        leave: '/pages/teacher-internship/internship-approval/index?tab=leave',
        'internship-students': '/pages/teacher-internship/internship-students/index',
        'internship-positions': '/pages/teacher-internship/internship-positions/index',
        guidance: '/pages/teacher-internship/internship-guidance/index',
        'stu-eval': '/pages/teacher-internship/student-eval/index',
        'ent-eval': '/pages/teacher-internship/enterprise-eval/index',
        insurance: '/pages/teacher-internship/insurance-verify/index',
        'internship-change': '/pages/teacher-internship/internship-change/index',
        'internship-score': '/pages/teacher-internship/internship-score/index',
        'agreement-confirm': '/pages/teacher-internship/agreement-confirm/index',
        'process-report': '/pages/teacher-internship/process-report-review/index',
        'plan-task': '/pages/teacher-internship/plan-task-review/index',
        'internship-application': '/pages/teacher-internship/internship-application/index',
        'internship-volunteers': '/pages/teacher-internship/internship-volunteers/index',
        'internship-risk': '/pages/teacher-internship/internship-risk/index',
        approval: '/pages/teacher/approval/index',
        todos: '/pages/teacher/todos/index',
        risk: '/pages/teacher/affairs-review/index?type=RISK_HANDLE',
        follow: '/pages/teacher/employment-follow/index',
        recommend: '/pages/teacher/employment-follow/index?tab=unemployed',
        verify: '/pages/teacher/employment-follow/index?tab=verify',
        unemployed: '/pages/teacher/employment-follow/index',
        employmentTransfer: '/pages/teacher/employment-transfer/index',
        employmentCompany: '/pages/teacher/employment-company/index',
        warning: '/pages/teacher/academic-warning/index',
        progress: '/pages/teacher/academic-affairs/index',
        status: '/pages/teacher/exam-defer/index',
        'topic-review': '/pages/teacher/graduation-topics/index',
        taskbook: '/pages/teacher/graduation-taskbook/index',
        'guide-log': '/pages/teacher/graduation-guide/index',
        'gd-overview': '/pages/teacher/graduation-guide/index',
        'gd-peer-review': '/pages/teacher/graduation-guide/index?tab=peer',
        'gd-defense': '/pages/teacher/graduation-guide/index?tab=defense',
        'gd-grade': '/pages/teacher/graduation-guide/index?tab=grade',
        'affairs-stats': '/pages/teacher/affairs/stats/index',
        'campus-service': '/pages/teacher/campus-service/index',
        myClasses: '/pages/teacher/my-classes/index',
        myStudents: '/pages/teacher/my-students/index',
        talk: '/pages/teacher/affairs/talk/index',
        mental: '/pages/teacher/affairs/mental/index',
        affairs: '/pages/teacher/affairs/index',
        familyContact: '/pages/teacher/family-contact/index',
        contact: '/pages/teacher/my-students/index',
        record: '/pages/teacher/family-contact/index?mode=create',
        // Historical shortcut keys reuse the named real service, not a new command.
        care: '/pages/teacher/affairs/talk/index',
        urge: '/pages/teacher/notify-publish/index',
        affairsLeave: '/pages/teacher/affairs-leave/index',
        dormReview: '/pages/teacher/dorm-review/index',
        classCadre: '/pages/teacher/class-cadre/index',
        classMaterial: '/pages/teacher/class-material/index',
        academicTask: '/pages/teacher/academic-task/index',
        scheduleChange: '/pages/teacher/schedule-change/index',
        examDefer: '/pages/teacher/exam-defer/index',
        evaluation: '/pages/teacher/evaluation/index',
        defenseScore: '/pages/teacher/defense-score/index',
        notifyPublish: '/pages/teacher/notify-publish/index',
        overview: '/pages/teacher/dashboard/index',
        orientationVerify: '/pages/teacher/orientation/verify/index',
        orientationDashboard: '/pages/teacher/orientation/dashboard/index'
}
export const INTERNSHIP_PERMISSIONS = {
  'internship-students': 'internship.student.view',
  'internship-positions': 'internship.position.view',
  weekly: 'internship.report.review',
  checkin: 'internship.attendance.review',
  visit: 'internship.visit.manage',
  makeup: 'internship.makeup.review',
  leave: 'internship.leave.review',
  guidance: 'internship.guidance.manage',
  'stu-eval': 'internship.eval.self.view',
  'ent-eval': 'internship.eval.enterprise.view',
  insurance: 'internship.insurance.view',
  'internship-change': 'internship.change.view',
  'internship-score': 'internship.score.view',
  'agreement-confirm': 'internship.agreement.view',
  'process-report': 'internship.report.view',
  'plan-task': 'internship.task.view',
  'internship-application': 'internship.application.view',
  'internship-volunteers': 'internship.application.view',
  'internship-risk': 'internship.risk.view'
}

const groups = [
  ['班级管理', ['myClasses', 'myStudents', 'classCadre', 'classMaterial']],
  ['日常事务', ['affairsLeave', 'dormReview', 'talk', 'mental', 'contact', 'record', 'care', 'affairs', 'campus-service']],
  ['家校沟通', ['familyContact']],
  ['教学事务', ['academicTask', 'scheduleChange', 'progress']],
  ['考试与评价', ['examDefer', 'status', 'evaluation', 'warning']],
  ['实习指导', ['internship-students', 'internship-positions', 'weekly', 'checkin', 'makeup', 'leave', 'visit', 'guidance', 'stu-eval', 'ent-eval', 'insurance', 'internship-change', 'internship-score', 'agreement-confirm', 'process-report', 'plan-task', 'internship-application', 'internship-volunteers', 'internship-risk']],
  ['毕业设计', ['topic-review', 'taskbook', 'review-open', 'review-mid', 'review-result', 'guide-log', 'gd-overview', 'gd-peer-review', 'gd-defense', 'gd-grade', 'defenseScore']],
  ['就业服务', ['follow', 'recommend', 'verify', 'unemployed', 'employmentTransfer', 'employmentCompany']],
  ['通知与管理', ['notifyPublish', 'overview', 'risk', 'urge', 'approval', 'todos', 'affairs-stats', 'orientationVerify', 'orientationDashboard']]
]
export function teacherServiceRoute(key, role) {
  if (key === 'risk' && role === 'intern_mentor') return '/pages/teacher-internship/internship-risk/index'
  return TEACHER_SERVICE_ROUTES[key] || ''
}
export function teacherServices(config, role, context = null) {
  const seen = new Set()
  return (config.quickActions || []).filter(q => {
    if (role !== 'intern_mentor') return true
    const permission = INTERNSHIP_PERMISSIONS[q.key]
    return !!(context && permission && context.can(permission))
  }).flatMap(q => {
    const path = teacherServiceRoute(q.key, role)
    // status and examDefer are the same published service. Keep a single catalogue entry.
    const identity = path || q.key
    if (seen.has(identity)) return []
    seen.add(identity)
    return [{ ...q, path, group: groups.find(([, keys]) => keys.includes(q.key))?.[0] || '其他服务',
      disabledReason: path ? '' : '该服务暂未开放' }]
  })
}
const visuals = [
  [/请假|续假|销假/, 'calendar', 'green'], [/宿舍|住宿/, 'home', 'teal'],
  [/谈心|谈话|联系|沟通/, 'message-dots', 'cyan'], [/家校/, 'user', 'amber'],
  [/材料|任务书|成果|开题|中期|周报|报告/, 'file-text', 'violet'], [/班级|学生|报到/, 'user', 'blue'],
  [/预警|异常|风险/, 'alert-circle', 'red'], [/通知|催办/, 'bell', 'amber'],
  [/岗位|企业|就业|巡访/, 'briefcase', 'teal'], [/评价|评分|评阅|答辩|考试|缓考/, 'clipboard-check', 'amber'],
  [/教学|课程|调停|课表/, 'book', 'blue'], [/安全|保险|协议/, 'shield-check', 'green']
]
export function teacherVisual(label) {
  // Family contact is distinct from a counselling conversation.
  if (/家校/.test(String(label || ''))) return { icon: 'user', tone: 'amber' }
  const match = visuals.find(([pattern]) => pattern.test(String(label || '')))
  return { icon: match?.[1] || 'file-text', tone: match?.[2] || 'violet' }
}
export function teacherDateText(date = new Date()) {
  return `${date.getFullYear()}年${date.getMonth()+1}月${date.getDate()}日  星期${'日一二三四五六'[date.getDay()]}`
}
export function teacherGreeting(date = new Date()) {
  const hour = date.getHours()
  return hour < 11 ? '上午好' : hour < 14 ? '中午好' : hour < 18 ? '下午好' : '晚上好'
}
