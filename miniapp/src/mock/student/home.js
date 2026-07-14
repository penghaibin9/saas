/** 学生首页 mock：阶段主任务 / 下一步 / 阻断 / 今日日程 / 待办概览（08A 5.1） */
export const studentHome = {
  greeting: '下午好',
  stageCard: {
    stage: 'ENROLLED',
    stageText: '在校',
    title: '你正处于「在校学习」阶段',
    subtitle: '本学期第 14 周 · 课程与实践并行',
    progress: 62
  },
  nextAction: {
    title: '完成《大学生心理健康》问卷',
    desc: '学工处要求本周内完成，用时约 5 分钟',
    deadline: '2026-07-06 18:00',
    actionText: '立即办理',
    route: '/pages/student/campus-service/index'
  },
  blockers: [
    {
      id: 'blk1',
      title: '图书馆超期未还 1 本',
      reason: '《数据结构与算法》已超期 3 天，产生滞纳金 ¥1.5',
      solveText: '去处理',
      level: 'MEDIUM'
    }
  ],
  todayCourses: [
    { id: 'c1', time: '10:00-11:40', name: '软件工程导论', place: '实训楼 A-305', status: 'current' },
    { id: 'c2', time: '14:00-15:40', name: '数据库原理', place: '教学楼 B-201', status: 'upcoming' },
    { id: 'c3', time: '19:00-20:40', name: '英语视听说', place: '教学楼 C-108', status: 'upcoming' }
  ],
  todos: [
    { id: 't1', title: '心理健康问卷', module: '学工服务', deadline: '2026-07-06 18:00', status: 'PENDING_HANDLE' },
    { id: 't2', title: '实训室安全承诺书签署', module: '在校服务', deadline: '2026-07-08 12:00', status: 'PENDING_SUBMIT' }
  ],
  notices: [
    { id: 'n1', title: '关于 2026 年暑期放假安排的通知', source: '教务处', time: '2026-07-03 09:12', important: true },
    { id: 'n2', title: '第二课堂学分认定开始申报', source: '校团委', time: '2026-07-02 16:40', important: false }
  ],
  metrics: { todoCount: 2, unread: 3, riskCount: 0, creditRate: 78 },
  quickServices: [
    { key: 'leave', label: '请假', icon: '✈', route: '/pages/student/campus-service/index' },
    { key: 'certificate', label: '证明开具', icon: '▤', route: '/pages/student/campus-service/index' },
    { key: 'score', label: '成绩查询', icon: '▦', route: '/pages/student/academic-affairs/index' },
    { key: 'internship', label: '实习打卡', icon: '📍', route: '/pages/student/internship/index' },
    { key: 'graduation', label: '毕业设计', icon: '✎', route: '/pages/student/graduation/index' },
    { key: 'employment', label: '就业去向', icon: '★', route: '/pages/student/employment/index' }
  ],
  campusCode: { valid: true, refreshIn: 58 }
}
export default studentHome
