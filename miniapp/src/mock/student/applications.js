/** 我的申请 mock（08A 7.5 我的办理） */
export const applicationTabs = [
  { key: 'all', label: '全部' },
  { key: 'processing', label: '处理中' },
  { key: 'supplement', label: '需补充' },
  { key: 'done', label: '已办结' },
  { key: 'rejected', label: '已驳回' }
]

export const applications = [
  {
    id: 'ap1', no: 'SV20260703001', name: '学生请假（事假 1 天）', group: 'processing',
    status: 'REVIEWING', applyTime: '2026-07-03 08:40', dept: '学工处', handler: '周敏',
    eta: '2026-07-04', lastOpinion: '辅导员审核中', hasResult: false
  },
  {
    id: 'ap2', no: 'SV20260702006', name: '在校证明开具', group: 'supplement',
    status: 'RETURNED', applyTime: '2026-07-02 15:10', dept: '教务处', handler: '教务窗口',
    eta: '2026-07-05', lastOpinion: '请补充用途说明与接收单位名称', hasResult: false
  },
  {
    id: 'ap3', no: 'SV20260628003', name: '第二课堂学分认定', group: 'done',
    status: 'COMPLETED', applyTime: '2026-06-28 10:20', dept: '校团委', handler: '团委老师',
    eta: '2026-07-01', lastOpinion: '认定通过，计 1.0 学分', hasResult: true
  },
  {
    id: 'ap4', no: 'SV20260620009', name: '奖学金申请（校级二等）', group: 'rejected',
    status: 'REJECTED', applyTime: '2026-06-20 09:00', dept: '资助中心', handler: '资助中心',
    eta: '2026-06-25', lastOpinion: '本次名额已满，建议下学期再申请', hasResult: true
  },
  {
    id: 'ap5', no: 'SV20260618002', name: '宿舍报修（空调不制冷）', group: 'done',
    status: 'COMPLETED', applyTime: '2026-06-18 20:30', dept: '后勤中心', handler: '维修班',
    eta: '2026-06-19', lastOpinion: '已维修完成', hasResult: true
  }
]
export default { applicationTabs, applications }
