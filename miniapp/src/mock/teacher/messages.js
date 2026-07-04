/** 教师消息中心 mock（08B 6.7 消息与风险） */
export const teacherMessageTabs = [
  { key: 'system', label: '系统通知', badge: 1 },
  { key: 'dynamic', label: '学生动态', badge: 3 },
  { key: 'risk', label: '风险预警', badge: 2 },
  { key: 'urge', label: '催办提醒', badge: 1 }
]

export const teacherMessages = {
  system: [
    { id: 'tm1', title: '毕业设计中期检查将于 7/8 截止', module: '教务处', level: 'high', time: '2026-07-03 09:00', read: false },
    { id: 'tm2', title: '暑期实习巡访安排通知', module: '实习管理', level: 'normal', time: '2026-07-01 15:00', read: true }
  ],
  dynamic: [
    { id: 'tm3', title: '王梓萱 提交了毕设中期报告', module: '毕业设计', level: 'normal', time: '2026-07-03 10:12', read: false },
    { id: 'tm4', title: '郑一鸣 提交了第 8 周周报', module: '岗位实习', level: 'normal', time: '2026-07-03 11:00', read: false },
    { id: 'tm5', title: '孙雨桐 发起病假申请', module: '在校服务', level: 'normal', time: '2026-07-03 08:30', read: false }
  ],
  risk: [
    { id: 'tm6', title: '李思远 打卡异常（超范围 820m）', module: '风险预警', level: 'high', time: '2026-07-03 09:10', read: false },
    { id: 'tm7', title: '赵启航 学业预警×2（高数补考未过）', module: '风险预警', level: 'high', time: '2026-07-02 16:00', read: false }
  ],
  urge: [
    { id: 'tm8', title: '学院催办：本周风险学生处理率待提升', module: '学院管理', level: 'normal', time: '2026-07-03 08:00', read: false }
  ]
}
export default { teacherMessageTabs, teacherMessages }
