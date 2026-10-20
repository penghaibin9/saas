import labels from '../../../../../shared/contracts/leave-presentation.json'

const lookup = (dict, value, fallback) => Object.prototype.hasOwnProperty.call(dict, String(value || '')) ? dict[value] : fallback
export const leaveTypes = Object.entries(labels.types).map(([value, label]) => ({ value, label }))
export const leaveStatuses = Object.entries(labels.statuses).map(([value, label]) => ({ value, label }))
export const leaveStatusText = (value) => lookup(labels.statuses, value, '状态待确认')
export const leaveOperationText = (value) => lookup(labels.operations, value, '状态待确认')
export function leaveDate(value, withTime = false) {
  if (!value) return '—'
  const raw = String(value).trim()
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(raw) ? raw + 'T00:00:00' : raw.replace(' ', 'T'))
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (v) => String(v).padStart(2, '0')
  const date = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate())
  return withTime ? date + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) : date
}
export function leaveError(error, fallback = '操作未完成，请重试') {
  const code = String(error?.bizCode || error?.code || '')
  if (/CONFLICT|409/.test(code)) return '记录已更新，请刷新后核对。填写的内容仍保留。'
  if (/403|NO_PERMISSION/.test(code)) return '当前身份无法办理这项业务，请确认身份与管理范围。'
  if (/401/.test(code)) return '登录已失效，请重新登录。'
  const message = String(error?.message || error || '')
  return /[\u4e00-\u9fff]/.test(message) && !/[A-Z][A-Z0-9]+_[A-Z0-9_]+|(?:Error|Exception|Traceback|SQL|permission|tenant_id|studentId|days=|wf=|actual_return=)\b/.test(message) && message.length < 180 ? message : fallback
}
export function presentLeave(row = {}) {
  const status = row.affairsStatus || row.status || ''
  const timeline = (row.timeline || row.auditTrail || []).map((event, index) => {
    const label = lookup(labels.actions, event.action, '办理状态已更新')
    return { ...event, eventId: event.eventId || String(index), actionLabel: label, description: label }
  })
  return { ...row, id: String(row.id || row.leaveId || ''), leaveId: String(row.leaveId || row.id || ''),
    status, affairsStatus: status, statusLabel: leaveStatusText(status), affairsStatusLabel: leaveStatusText(status),
    leaveTypeLabel: lookup(labels.types, row.leaveType, '假种待确认'),
    tone: ['REJECTED','OVERDUE'].includes(status) ? 'danger' : ['CLOSED','APPROVED','ARCHIVED'].includes(status) ? 'success' : 'warning',
    nextHint: lookup(labels.next, status, '请查看办理记录或联系辅导员了解进度。'),
    startDate: leaveDate(row.startTime), endDate: leaveDate(row.endTime), timeline,
    auditTrail: (row.auditTrail || []).map(event => ({ ...event, actionCode: event.action, action: lookup(labels.actions, event.action, '办理状态已更新'), detail: leaveError(event.detail, '') })),
    extensions: (row.extensions || []).map((item) => ({ ...item, statusLabel: leaveOperationText(item.status) })),
    cancelRecords: (row.cancelRecords || []).map((item) => ({ ...item, statusLabel: leaveOperationText(item.status) }))
  }
}

