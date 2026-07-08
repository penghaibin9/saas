/** 题目库字典（展示层） */
export const GD_TOPIC_SOURCE = [
  { value: 'TEACHER', label: '教师申报' },
  { value: 'ENTERPRISE', label: '企业题目' },
  { value: 'STUDENT', label: '学生自拟' },
  { value: 'ADMIN', label: '管理员录入' }
]

export const GD_TOPIC_REVIEW = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'PENDING_REVIEW', label: '待审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' }
]

export const GD_TOPIC_STATUS = [
  { value: 'PENDING_CONFIRM', label: '待确认' },
  { value: 'CONFIRMED', label: '已入池' },
  { value: 'DISABLED', label: '已停用' },
  { value: 'ARCHIVED', label: '已归档' }
]

export const GD_TOPIC_CATEGORY = [
  '软件系统', '硬件设计', '综合设计', '理论研究', '社会调查', '艺术创作'
]

export const GD_TOPIC_DIFFICULTY = [
  { value: 'EASY', label: '较易' },
  { value: 'MEDIUM', label: '中等' },
  { value: 'HARD', label: '较难' }
]

export const IS_FULL = [
  { value: 'false', label: '未满员' },
  { value: 'true', label: '已满员' }
]

export const ARCHIVE_VIEW = [
  { value: 'active', label: '在库题目' },
  { value: 'archived', label: '已归档' }
]
