/** 实习周报批阅 mock（08B 6.6 岗位实习移动处理） */
export const weeklyReports = [
  {
    id: 'W1', student: '李思远', className: '软件2401', week: '第 8 周',
    company: '广州极简网络', post: '后端实习生', submitTime: '逾期未提交',
    status: 'OVERDUE', overdue: true, content: '', tasks: '', gain: '', problem: ''
  },
  {
    id: 'W2', student: '郑一鸣', className: '软件2401', week: '第 8 周',
    company: '长沙数联', post: '测试实习生', submitTime: '2026-07-03 11:00',
    status: 'PENDING_REVIEW', overdue: false,
    tasks: '完成登录模块用例编写与执行，提交缺陷 12 个。',
    gain: '熟悉了黑盒测试用例设计方法与缺陷管理流程。',
    problem: '自动化脚本编写还不熟练，下周计划学习 pytest。'
  },
  {
    id: 'W3', student: '孙雨桐', className: '软件2401', week: '第 8 周',
    company: '株洲云创', post: 'UI 设计实习生', submitTime: '2026-07-03 09:40',
    status: 'PENDING_REVIEW', overdue: false,
    tasks: '完成 App 首页 3 版视觉稿，参与评审。',
    gain: '掌握了从需求到高保真的完整流程。',
    problem: '对设计规范落地到开发标注还需加强。'
  },
  {
    id: 'W4', student: '吴佳怡', className: '软件2401', week: '第 7 周',
    company: '广州极简网络', post: '前端实习生', submitTime: '2026-06-27 21:00',
    status: 'APPROVED', overdue: false, score: '优',
    tasks: '完成商品列表页开发与联调。',
    gain: '提升了组件封装能力。',
    problem: '无。',
    feedback: '任务描述清晰，产出充实，继续保持。'
  }
]

export const abnormalCheckins = [
  { id: 'CK1', student: '李思远', time: '2026-07-03 09:10', type: '超出企业定位范围', distance: '820m', note: '学生说明：临时被派往客户现场', status: 'PENDING_HANDLE' },
  { id: 'CK2', student: '李思远', time: '2026-07-02 09:05', type: '定位失败', distance: '—', note: '学生说明：地下车库无信号', status: 'PENDING_HANDLE' }
]
export default { weeklyReports, abnormalCheckins }
