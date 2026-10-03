/**
 * 岗位库字典（展示层常量，非 mock 业务数据）。
 * 枚举值与后端 app/modules/internship/schemas/internship_position.py 的 Literal 一一对应，
 * 只补中文展示名，不新增/改名任何取值——改了会导致提交被后端 422 拒绝。
 */

/** 岗位库状态字典 */
export const POSITION_STATUS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'PENDING', label: '待审核' },
  { value: 'PUBLISHED', label: '已上架' },
  { value: 'OFFLINE', label: '已下架' },
  { value: 'SUSPENDED', label: '已暂停' },
  { value: 'FULL', label: '已满员' },
  { value: 'RISK', label: '风险岗位' },
  { value: 'ARCHIVED', label: '已归档' }
]

/** 报酬类型（企业给实习生的报酬是按什么口径计算的） */
export const REMUNERATION_TYPE = [
  { value: 'MONTHLY', label: '月薪' },
  { value: 'DAILY', label: '日薪' },
  { value: 'HOURLY', label: '时薪' },
  { value: 'ALLOWANCE', label: '实习补贴' },
  { value: 'UNPAID', label: '无报酬' },
  { value: 'OTHER', label: '其他' }
]

/** 发放周期（多久发一次） */
export const REMUNERATION_CYCLE = [
  { value: 'MONTHLY', label: '每月发放' },
  { value: 'WEEKLY', label: '每周发放' },
  { value: 'DAILY', label: '每日发放' },
  { value: 'ON_COMPLETION', label: '实习结束后一次性发放' },
  { value: 'OTHER', label: '其他' }
]

export const REMUNERATION_TYPE_LABEL = REMUNERATION_TYPE.reduce((acc, o) => {
  acc[o.value] = o.label
  return acc
}, {})

export const REMUNERATION_CYCLE_LABEL = REMUNERATION_CYCLE.reduce((acc, o) => {
  acc[o.value] = o.label
  return acc
}, {})
