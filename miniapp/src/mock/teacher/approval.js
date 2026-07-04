/** 教师审批处理 mock（轻审批） */
export const approvals = [
  {
    id: 'AP1', title: '学生请假申请', type: '请假 · 病假', student: '孙雨桐', className: '软件2401',
    submitTime: '2026-07-03 08:30', status: 'PENDING_REVIEW', level: 'normal',
    fields: [
      { label: '请假类型', value: '病假' },
      { label: '起止时间', value: '2026-07-05 全天' },
      { label: '事由', value: '感冒发热，需就医休息' },
      { label: '附件', value: '就诊记录.jpg' }
    ],
    flow: [
      { node: '学生提交', time: '07-03 08:30', done: true },
      { node: '辅导员审批', time: '待处理', done: false, current: true },
      { node: '学院备案', time: '—', done: false }
    ]
  },
  {
    id: 'AP2', title: '实习请假申请', type: '请假 · 事假', student: '李思远', className: '软件2401',
    submitTime: '2026-07-02 19:10', status: 'PENDING_REVIEW', level: 'high',
    fields: [
      { label: '请假类型', value: '事假' },
      { label: '起止时间', value: '2026-07-07 半天' },
      { label: '事由', value: '办理银行卡（发薪需要）' },
      { label: '企业导师意见', value: '同意' }
    ],
    flow: [
      { node: '学生提交', time: '07-02 19:10', done: true },
      { node: '企业导师确认', time: '07-02 20:00', done: true },
      { node: '校内导师审批', time: '待处理', done: false, current: true }
    ]
  },
  {
    id: 'AP3', title: '在校证明开具', type: '证明 · 在校证明', student: '陈子涵', className: '软件2401',
    submitTime: '2026-07-01 14:00', status: 'PENDING_REVIEW', level: 'normal',
    fields: [
      { label: '证明类型', value: '在校证明' },
      { label: '用途', value: '办理助学贷款' },
      { label: '接收单位', value: '某银行支行' }
    ],
    flow: [
      { node: '学生提交', time: '07-01 14:00', done: true },
      { node: '辅导员审批', time: '待处理', done: false, current: true },
      { node: '教务盖章', time: '—', done: false }
    ]
  }
]
export default approvals
