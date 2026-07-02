/**
 * Dashboard 表现层映射（纯 UI，不含业务聚合）
 * 颜色、标签、accent 等展示逻辑统一在此，adapter 只做数据转换。
 */

/** @param {{ metricId?: string, id?: string, trendQuality?: string, status?: string }} metric */
export function metricAccent(metric) {
  const id = metric.metricId || metric.id
  const warningIds = ['pt-teacher-todos', 'gd-midterm-pending', 'pt-todo-completion']
  const riskIds = ['pt-risk', 'int-abnormal-streak', 'int-risk', 'gd-overdue']
  if (warningIds.includes(id)) return 'warning'
  if (riskIds.includes(id) || metric.trendQuality === 'bad' || metric.status === 'bad' || metric.status === 'danger')
    return 'risk'
  if (metric.trendQuality === 'good' || metric.status === 'good') return 'success'
  if (metric.status === 'warning') return 'warning'
  return 'primary'
}

/** @param {'todo'|'doing'|'done'|string} status */
export function taskStatusCode(status) {
  const map = { todo: 'PENDING_HANDLE', doing: 'PENDING_REVIEW', done: 'COMPLETED' }
  return map[status] || 'PENDING_HANDLE'
}

/** @param {'pending'|'processing'|'resolved'|string} status */
export function riskStatusCode(status) {
  const map = {
    pending: 'PENDING_HANDLE',
    processing: 'REVIEWING',
    resolved: 'COMPLETED'
  }
  return map[status] || 'PENDING_HANDLE'
}

/** @param {{ status?: string, statusLabel?: string }} risk */
export function riskStatusLabel(risk) {
  if (risk.status === 'resolved') return '已处理'
  if (risk.status === 'processing') return '处理中'
  return risk.statusLabel || '待处理'
}

/** @param {'LOW'|'MEDIUM'|'HIGH'|'CRITICAL'|string} level */
export function riskLevelLabel(level) {
  const map = { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '严重' }
  return map[level] || level
}

/** @param {'LOW'|'MEDIUM'|'HIGH'|'CRITICAL'|string} level */
export function riskLevelBadgeType(level) {
  if (level === 'CRITICAL' || level === 'HIGH') return 'danger'
  if (level === 'MEDIUM') return 'warning'
  return 'neutral'
}

/** @param {'high'|'medium'|'low'|string} priority */
export function taskPriorityBadgeType(priority) {
  if (priority === 'high') return 'danger'
  if (priority === 'medium') return 'warning'
  return 'neutral'
}

/** 学生跟进抽屉：是否存在未处理风险 */
export function studentFollowStatusCode(hasActiveRisk) {
  return hasActiveRisk ? 'PENDING_HANDLE' : 'COMPLETED'
}

/** 抽屉详情 status → AppStatusTag code */
export function handleDetailStatusCode(status) {
  if (status === 'todo' || status === 'doing' || status === 'done') return taskStatusCode(status)
  return riskStatusCode(status)
}

/** 待办完成率 → 展示 status（非趋势，基于当前值） */
export function completionRateStatus(rate) {
  if (rate >= 80) return 'good'
  if (rate >= 60) return 'warning'
  return 'danger'
}
