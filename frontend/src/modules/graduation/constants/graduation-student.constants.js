/** 毕设学生字典（展示层常量，非 mock 业务数据） */
export const GD_STAGE = [
  { value: 'TOPIC_SELECTING', label: '选题中' },
  { value: 'TASKBOOK_CONFIRM', label: '任务书确认' },
  { value: 'GUIDING', label: '指导中' },
  { value: 'MIDTERM', label: '中期检查' },
  { value: 'FINAL_CHECK', label: '成果检查' },
  { value: 'DEFENSE', label: '答辩中' },
  { value: 'COMPLETED', label: '已完成' },
  { value: 'ARCHIVED', label: '已归档' }
]

export const GD_RISK_LEVEL = [
  { value: 'NONE', label: '无' },
  { value: 'LOW', label: '低风险' },
  { value: 'MEDIUM', label: '中风险' },
  { value: 'HIGH', label: '高风险' }
]

export const HAS_TOPIC = [
  { value: 'true', label: '已选题' },
  { value: 'false', label: '未选题' }
]

export const GD_ELIGIBILITY = [
  { value: 'PENDING', label: '待认定' },
  { value: 'QUALIFIED', label: '资格合格' },
  { value: 'UNQUALIFIED', label: '资格不合格' }
]

export const GD_GRAD_QUAL = [
  { value: 'UNKNOWN', label: '未联动' },
  { value: 'NONE', label: '未预审' },
  { value: 'PENDING', label: '预审中' },
  { value: 'PASS', label: '毕业资格通过' },
  { value: 'FAIL', label: '毕业资格不通过' }
]

export const HAS_DEFENSE_GROUP = [
  { value: 'true', label: '已分配答辩组' },
  { value: 'false', label: '未分配答辩组' }
]

export const MATERIAL_COMPLETE = [
  { value: 'true', label: '材料齐全' },
  { value: 'false', label: '材料缺失' }
]

export const ARCHIVE_VIEW = [
  { value: 'candidates', label: '待归档' },
  { value: 'archived', label: '已归档' }
]
