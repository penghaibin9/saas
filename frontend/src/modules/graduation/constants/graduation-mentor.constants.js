/** 导师管理 / 导师分配字典（展示层常量，非 mock 业务数据） */
export const MENTOR_QUALIFICATION_STATUS = [
  { value: 'PENDING_REVIEW', label: '待审核' },
  { value: 'QUALIFIED', label: '已认证' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'DISABLED', label: '已停用' },
  { value: 'ARCHIVED', label: '已归档' }
]

export const MENTOR_TYPE = [
  { value: 'INTERNAL', label: '校内导师' },
  { value: 'ENTERPRISE', label: '企业导师' },
  { value: 'DUAL', label: '双导师' }
]
