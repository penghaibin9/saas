export function domainMetric(domains, key, metric = 'total') {
  const domain = domains.find(item => item.key === key)
  if (domain?.status !== 'OK') return null
  const value = metric === 'total' || metric === 'highlight' ? domain[metric] : domain.metrics?.[metric]
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
}
export function occupancyRate(domains) {
  const total = domainMetric(domains, 'dorm'), occupied = domainMetric(domains, 'dorm', 'occupiedBeds')
  if (total === null || occupied === null || total === 0 || occupied > total) return null
  return Math.round(occupied / total * 1000) / 10
}
export const SUPPORT_DOMAINS = [
  { key: 'aid', title: '困难认定', unit: '份申请', detail: '已认定' },
  { key: 'funding', title: '奖助支持', unit: '份申请', detail: '已获资助' },
  { key: 'talk', title: '谈心谈话', unit: '次记录', detail: '已完成' },
  { key: 'activity', title: '校园活动', unit: '项活动', detail: '获学分学生' }
]
