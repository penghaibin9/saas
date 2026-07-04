/** 就业跟进 mock（08B 就业老师场景 / 07 就业中心） */
export const employmentStats = { total: 196, employed: 159, rate: 81, unemployed: 37, verified: 128 }

export const employmentTabs = [
  { key: 'unemployed', label: '未就业', badge: 37 },
  { key: 'following', label: '跟进中', badge: 12 },
  { key: 'verify', label: '待核验', badge: 8 },
  { key: 'done', label: '已落实' }
]

export const employmentStudents = [
  { id: 'E1', name: '周浩然', className: '软件2401', group: 'unemployed', intention: '未填报', city: '—', contactTimes: 1, last: '2026-06-28 已电话联系一次', status: 'PENDING_HANDLE' },
  { id: 'E2', name: '林可欣', className: '软件2401', group: 'following', intention: '互联网/前端', city: '长沙/深圳', contactTimes: 2, last: '2026-07-02 推荐 3 个岗位', status: 'PROCESSING' },
  { id: 'E3', name: '何俊杰', className: '软件2402', group: 'verify', intention: '已签约', city: '深圳', company: '深圳云图信息', contactTimes: 3, last: '待核验三方协议', status: 'PENDING_REVIEW' },
  { id: 'E4', name: '张欣怡', className: '软件2402', group: 'done', intention: '已就业', city: '长沙', company: '湖南智联科技', contactTimes: 4, last: '去向已核验', status: 'COMPLETED' },
  { id: 'E5', name: '刘宇轩', className: '软件2401', group: 'unemployed', intention: '拟升学', city: '—', contactTimes: 0, last: '尚未联系', status: 'PENDING_HANDLE' }
]

export const jobPool = [
  { id: 'JP1', company: '湖南智联科技', post: '前端开发工程师', salary: '7-10K', city: '长沙', headcount: 5 },
  { id: 'JP2', company: '深圳云图信息', post: 'Web 前端', salary: '9-13K', city: '深圳', headcount: 3 },
  { id: 'JP3', company: '长沙数联', post: '小程序开发', salary: '6-9K', city: '长沙', headcount: 2 }
]
export default { employmentStats, employmentTabs, employmentStudents, jobPool }
