/** 岗位实习 mock（06 岗位实习中心）。该视图演示 INTERN 情景下的实习首页。 */
export const studentInternship = {
  hasBatch: true,
  batch: '2026 届春季顶岗实习',
  company: '湖南智联科技有限公司',
  post: '前端开发实习生',
  schoolMentor: '张明远',
  companyMentor: '赵工（企业导师）',
  status: {
    agreement: 'APPROVED', // 协议
    insurance: 'APPROVED', // 保险
    onboard: 'COMPLETED', // 到岗
    todayCheckin: 'PENDING_HANDLE', // 今日打卡
    weekly: 'PENDING_SUBMIT', // 本周周报
    leave: 'NOT_STARTED'
  },
  checkin: { done: false, place: '公司未定位', range: '有效范围 500m', note: '仅在点击时采集定位，不后台定位' },
  weekly: { week: '第 8 周', deadline: '2026-07-06 22:00', submitted: false, lastFeedback: '第 7 周：任务描述再具体些，附上产出截图。' },
  weeklyList: [
    { week: 7, status: 'APPROVED', reviewComment: '第 7 周：任务描述再具体些，附上产出截图。',
      workContent: '完成用户中心页面重构；联调登录、资料、消息 3 个接口。', harvestContent: '熟悉 Vue3 组合式 API 与真实接口联调流程。',
      planContent: '下周计划完成消息模块并补充单元测试。', submittedAt: '2026-06-29T18:20:00' },
    { week: 6, status: 'APPROVED', reviewComment: '内容完整，继续保持。',
      workContent: '完成登录页与权限校验逻辑联调。', harvestContent: '了解了 JWT 鉴权与路由守卫的实现方式。',
      planContent: '', submittedAt: '2026-06-22T20:05:00' }
  ],
  risk: [],
  timeline: [
    { id: 'i1', title: '岗位分配', status: 'COMPLETED', time: '2026-03-01' },
    { id: 'i2', title: '签署三方协议', status: 'COMPLETED', time: '2026-03-05' },
    { id: 'i3', title: '购买实习保险', status: 'COMPLETED', time: '2026-03-06' },
    { id: 'i4', title: '到岗确认', status: 'COMPLETED', time: '2026-03-10' },
    { id: 'i5', title: '实习进行中（每日打卡/周报）', status: 'PROCESSING', time: '进行中' },
    { id: 'i6', title: '实习总结与成绩', status: 'NOT_STARTED', time: '—' }
  ],
  entries: ['岗位申请', '我的实习', '实习协议', '保险信息', '每日打卡', '周报', '请假', '教师指导', '企业评价', '实习成绩']
}
export default studentInternship
