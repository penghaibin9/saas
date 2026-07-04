/** 教师移动待办 mock（08B 6.4 移动待办） */
export const todoFilters = [
  { key: 'all', label: '全部' },
  { key: 'approve', label: '待审批' },
  { key: 'review', label: '待批阅' },
  { key: 'confirm', label: '待确认' },
  { key: 'risk', label: '待处理风险' },
  { key: 'contact', label: '待联系' },
  { key: 'soon', label: '即将超时' },
  { key: 'done', label: '已处理' }
]

export const teacherTodos = [
  { id: 'T1', group: 'review', title: '批阅第 8 周周报', student: '李思远', module: '岗位实习', deadline: '2026-07-04 20:00', level: 'high', status: 'PENDING_REVIEW', soon: true },
  { id: 'T2', group: 'risk', title: '处理打卡异常（超范围）', student: '李思远', module: '岗位实习', deadline: '2026-07-04 12:00', level: 'high', status: 'ABNORMAL', soon: true },
  { id: 'T3', group: 'approve', title: '请假审批（病假 1 天）', student: '孙雨桐', module: '在校服务', deadline: '2026-07-04 12:00', level: 'normal', status: 'PENDING_REVIEW', soon: true },
  { id: 'T4', group: 'review', title: '批阅毕设中期报告', student: '王梓萱', module: '毕业设计', deadline: '2026-07-05 18:00', level: 'high', status: 'PENDING_REVIEW', soon: false },
  { id: 'T5', group: 'contact', title: '关怀回访（连续未登录）', student: '陈子涵', module: '学工', deadline: '2026-07-05 18:00', level: 'normal', status: 'PENDING_HANDLE', soon: false },
  { id: 'T6', group: 'confirm', title: '确认学生到岗信息', student: '郑一鸣', module: '岗位实习', deadline: '2026-07-06 18:00', level: 'normal', status: 'PENDING_HANDLE', soon: false },
  { id: 'T7', group: 'done', title: '批阅第 7 周周报', student: '郑一鸣', module: '岗位实习', deadline: '2026-06-28 20:00', level: 'normal', status: 'COMPLETED', soon: false }
]
export default { todoFilters, teacherTodos }
