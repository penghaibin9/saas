export const positionFilters = [
  { value: '', label: '全部' }, { value: 'PUBLISHED', label: '已上架' },
  { value: 'PENDING', label: '待审核' }, { value: 'DRAFT', label: '草稿' },
  { value: 'OFFLINE', label: '已下架' }, { value: 'SUSPENDED', label: '已暂停' },
  { value: 'FULL', label: '已满员' }, { value: 'RISK', label: '风险岗位' },
  { value: 'ARCHIVED', label: '已归档' }
]
export function positionQuery(query = {}) {
  const page = Number(query.page)
  return { batchId: String(query.batchId || ''),
    status: positionFilters.some(item => item.value === query.status) ? query.status : '',
    keyword: String(query.keyword || '').trim().slice(0, 100),
    page: Number.isSafeInteger(page) && page > 0 ? page : 1 }
}
function queryString(query) {
  return Object.entries(positionQuery(query)).map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join('&')
}
export const positionListUrl = query => '/pages/teacher/internship-positions/index?' + queryString(query)
export const positionDetailUrl = (id, query) => '/pages/teacher/internship-positions/detail?id=' + encodeURIComponent(id) + '&' + queryString(query)
const amount = (value, unit) => value == null || value === '' ? '待补充' : value + unit
const yesNo = value => value === true ? '是' : value === false ? '否' : '待补充'
export function positionFacts(row = {}) {
  return [
    { title: '工作安排', items: [
      ['每日工时', amount(row.dailyHours, ' 小时')], ['每周工时', amount(row.weeklyHours, ' 小时')],
      ['每周休息', amount(row.restDaysPerWeek, ' 天')], ['存在夜班', yesNo(row.nightShift)], ['允许加班', yesNo(row.overtimeAllowed)]
    ] },
    { title: '报酬与生活', items: [
      ['报酬标准', amount(row.remunerationAmount, ' 元')],
      ['计酬方式', ({ MONTHLY: '月薪', DAILY: '日薪', HOURLY: '时薪', ALLOWANCE: '实习补贴', UNPAID: '无报酬', OTHER: '其他' })[row.remunerationType] || '待补充'],
      ['发放周期', ({ MONTHLY: '每月', WEEKLY: '每周', DAILY: '每日', ON_COMPLETION: '实习结束后一次性发放', OTHER: '其他' })[row.remunerationCycle] || '待补充'],
      ['提供住宿', yesNo(row.accommodationProvided)], ['提供餐食', yesNo(row.mealProvided)], ['补贴', row.subsidy || '未说明']
    ] },
    { title: '安全条件', items: [['危险或特殊岗位', yesNo(row.hazardousFlag)], ['特殊设备', row.specialEquipment || '未说明']] }
  ]
}
