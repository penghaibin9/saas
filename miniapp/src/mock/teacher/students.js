/** 教师端学生库 mock（08B 我的学生 / 学生360摘要） */
export const students = [
  { id: 'S001', name: '陈子涵', studentNo: '2024010601', className: '软件2401', major: '软件工程', stage: '在校', task: '心理问卷未交', risk: 'MEDIUM', pending: 2, last: '3 天未登录平台', intern: false, gd: false },
  { id: 'S002', name: '李思远', studentNo: '2024010602', className: '软件2401', major: '软件工程', stage: '实习', task: '本周周报未交', risk: 'HIGH', pending: 3, last: '打卡异常 2 次', intern: true, gd: false },
  { id: 'S003', name: '王梓萱', studentNo: '2024010603', className: '软件2401', major: '软件工程', stage: '毕设', task: '中期待批阅', risk: 'LOW', pending: 1, last: '提交中期报告', intern: false, gd: true },
  { id: 'S004', name: '赵启航', studentNo: '2024010604', className: '软件2401', major: '软件工程', stage: '在校', task: '两门课程预警', risk: 'HIGH', pending: 2, last: '高数补考未通过', intern: false, gd: false },
  { id: 'S005', name: '孙雨桐', studentNo: '2024010605', className: '软件2401', major: '软件工程', stage: '实习', task: '请假待审批', risk: 'MEDIUM', pending: 1, last: '提交病假申请', intern: true, gd: false },
  { id: 'S006', name: '周浩然', studentNo: '2024010606', className: '软件2401', major: '软件工程', stage: '就业', task: '去向未登记', risk: 'MEDIUM', pending: 1, last: '未填报就业意向', intern: false, gd: false },
  { id: 'S007', name: '吴佳怡', studentNo: '2024010607', className: '软件2401', major: '软件工程', stage: '毕设', task: '开题已通过', risk: 'LOW', pending: 0, last: '按计划推进', intern: false, gd: true },
  { id: 'S008', name: '郑一鸣', studentNo: '2024010608', className: '软件2401', major: '软件工程', stage: '实习', task: '巡访待记录', risk: 'LOW', pending: 1, last: '到岗正常', intern: true, gd: false }
]

/** 学生360摘要（教师端点开详情） */
export const student360 = {
  S002: {
    base: { name: '李思远', studentNo: '2024010602', className: '软件2401', major: '软件工程', stage: '实习', phone: '13600000602' },
    risk: { level: 'HIGH', types: ['实习打卡异常', '周报逾期'], since: '2026-07-01' },
    tags: ['实习中', '重点关注'],
    timeline: [
      { id: 'a1', time: '2026-07-03 09:10', text: '打卡异常：定位超出企业范围', type: 'risk' },
      { id: 'a2', time: '2026-07-02 22:00', text: '第 8 周周报逾期未提交', type: 'warn' },
      { id: 'a3', time: '2026-06-28 18:20', text: '第 7 周周报已通过', type: 'ok' }
    ],
    intern: { company: '广州极简网络', post: '后端实习生', mentor: '本人', companyMentor: '钱工' },
    pendingItems: [
      { id: 'p1', title: '第 8 周周报（逾期）', action: '催交 / 批阅' },
      { id: 'p2', title: '打卡异常复核', action: '处理异常' },
      { id: 'p3', title: '风险跟进记录', action: '记录联系' }
    ]
  }
}
export default { students, student360 }
