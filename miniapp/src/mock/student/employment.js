/** 就业去向 mock（07 毕业与就业中心） */
export const studentEmployment = {
  stageText: '就业意向填报中',
  reportStatus: 'PENDING_SUBMIT',
  intention: { type: '就业', industry: '互联网/软件', city: '长沙 / 深圳', salaryExpect: '6-9K' },
  destination: null, // 尚未确认去向
  verifyStatus: 'NOT_STARTED',
  recommendedJobs: [
    { id: 'j1', company: '湖南智联科技', post: '前端开发工程师', salary: '7-10K', city: '长沙', match: 92 },
    { id: 'j2', company: '深圳云图信息', post: 'Web 前端', salary: '9-13K', city: '深圳', match: 86 },
    { id: 'j3', company: '长沙数联', post: '小程序开发', salary: '6-9K', city: '长沙', match: 81 }
  ],
  steps: [
    { id: 'e1', title: '填报就业意向', status: 'PROCESSING' },
    { id: 'e2', title: '签约 / 去向登记', status: 'NOT_STARTED' },
    { id: 'e3', title: '材料上传（三方/劳动合同）', status: 'NOT_STARTED' },
    { id: 'e4', title: '去向核验', status: 'NOT_STARTED' },
    { id: 'e5', title: '就业质量回访', status: 'NOT_STARTED' }
  ]
}
export default studentEmployment
