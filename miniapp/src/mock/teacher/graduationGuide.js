/** 毕设指导 mock（08B 6.5 毕业设计移动处理） */
export const gdStudents = [
  { id: 'G1', name: '王梓萱', className: '软件2401', topic: '基于 Vue3 的高校学生服务小程序设计与实现', node: '中期检查', status: 'PENDING_REVIEW', deadline: '2026-07-05' },
  { id: 'G2', name: '吴佳怡', className: '软件2401', topic: '校园二手交易平台的设计与实现', node: '开题报告', status: 'PENDING_REVIEW', deadline: '2026-07-06' },
  { id: 'G3', name: '黄子豪', className: '软件2402', topic: '基于深度学习的图像分类系统', node: '中期检查', status: 'OVERDUE', deadline: '2026-07-02' },
  { id: 'G4', name: '徐若涵', className: '软件2402', topic: '在线教育平台的前端架构研究', node: '成果提交', status: 'NOT_STARTED', deadline: '2026-07-20' }
]

export const gdReviewDetail = {
  G1: {
    student: '王梓萱', topic: '基于 Vue3 的高校学生服务小程序设计与实现', node: '中期检查',
    submitTime: '2026-07-03 10:12', attachment: '中期检查报告.docx',
    abstract: '目前已完成学生端首页、服务大厅、实习与毕设模块，正在进行教师端联调，测试覆盖核心流程。',
    progress: ['已完成 6 个核心页面', '组件复用率约 70%', '待完成：消息中心与异常态'],
    checkedItem: '进度符合任务书计划，中期完成度约 60%。'
  }
}
export default { gdStudents, gdReviewDetail }
