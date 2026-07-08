/** 毕设批次字典（展示层常量，非 mock 业务数据） */
export const BATCH_STATUS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'RUNNING', label: '进行中' },
  { value: 'CLOSED', label: '已结束' },
  { value: 'ARCHIVED', label: '已归档' },
  { value: 'VOIDED', label: '已作废' }
]

export const STATUS_TONE = {
  DRAFT: 'default', RUNNING: 'success', CLOSED: 'warning', ARCHIVED: 'default', VOIDED: 'danger'
}
