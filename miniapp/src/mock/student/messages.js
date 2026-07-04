/** 学生消息中心 mock（08A 八、消息中心） */
export const studentMessageTabs = [
  { key: 'todo', label: '待办', badge: 2 },
  { key: 'notice', label: '通知', badge: 1 },
  { key: 'progress', label: '服务进度', badge: 0 },
  { key: 'course', label: '课程教务', badge: 0 }
]

export const studentMessages = {
  todo: [
    { id: 'm1', title: '心理健康问卷待完成', module: '学工服务', level: 'high', time: '2026-07-03 09:00', deadline: '2026-07-06 18:00', actionable: true, read: false, status: 'PENDING_HANDLE' },
    { id: 'm2', title: '实训室安全承诺书待签署', module: '在校服务', level: 'normal', time: '2026-07-02 14:00', deadline: '2026-07-08 12:00', actionable: true, read: false, status: 'PENDING_SUBMIT' }
  ],
  notice: [
    { id: 'm3', title: '关于 2026 年暑期放假安排的通知', module: '教务处', level: 'high', time: '2026-07-03 09:12', receipt: true, read: false },
    { id: 'm4', title: '校园卡系统升级维护公告', module: '信息中心', level: 'normal', time: '2026-07-01 18:00', receipt: false, read: true }
  ],
  progress: [
    { id: 'm5', title: '你的「学生请假」已进入辅导员审核', module: '服务进度', level: 'normal', time: '2026-07-03 08:45', read: true, status: 'REVIEWING' },
    { id: 'm6', title: '你的「在校证明」被退回，需补充材料', module: '服务进度', level: 'high', time: '2026-07-02 16:20', read: false, status: 'RETURNED' }
  ],
  course: [
    { id: 'm7', title: '数据库原理 期末考试安排已发布', module: '教务处', level: 'normal', time: '2026-07-01 10:00', read: true },
    { id: 'm8', title: '软件工程导论 调课通知（周四→周五）', module: '教务处', level: 'normal', time: '2026-06-30 15:30', read: true }
  ]
}
export default { studentMessageTabs, studentMessages }
