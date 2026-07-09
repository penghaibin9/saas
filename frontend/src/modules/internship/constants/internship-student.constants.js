/** 实习学生字典（展示层常量，非 mock 业务数据） */
export const STUDENT_STATUS = [
  { value: 'PREPARING', label: '准备中' },
  { value: 'READY', label: '待上岗' },
  { value: 'ONBOARD', label: '在岗中' },
  { value: 'ASSESSING', label: '考核中' },
  { value: 'ARCHIVED', label: '已归档' }
]

export const ELIGIBILITY_STATUS = [
  { value: 'PENDING', label: '待认定' },
  { value: 'QUALIFIED', label: '资格合格' },
  { value: 'UNQUALIFIED', label: '资格不合格' }
]

export const DESTINATION_TYPE = [
  { value: 'NONE', label: '未落实' },
  { value: 'ASSIGNED', label: '已分配岗位' },
  { value: 'SELF_ARRANGED', label: '自主实习' },
  { value: 'EXEMPTED', label: '免实习' }
]

export const RISK_LEVEL = [
  { value: 'NONE', label: '无' },
  { value: 'LOW', label: '低风险' },
  { value: 'MEDIUM', label: '中风险' },
  { value: 'HIGH', label: '高风险' }
]
