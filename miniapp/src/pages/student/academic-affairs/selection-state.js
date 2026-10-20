export const SELECTION_STATUS = Object.freeze({
  PENDING_LOTTERY: {
    label: '已报名待抽签',
    tone: 'waiting',
    description: '报名已登记，当前没有取得名额。请等待学校公布抽签结果。'
  },
  SELECTED: {
    label: '已取得名额',
    tone: 'success',
    description: '本人选课记录已确认。名单锁定并发布后，请在课表中核对上课安排。'
  },
  LOCKED: {
    label: '名单已锁定',
    tone: 'success',
    description: '名单已经锁定，普通退课已关闭。后续安排以学校通知为准。'
  },
  LOTTERY_LOST: {
    label: '未中签',
    tone: 'danger',
    description: '本轮抽签未取得名额。是否可以参加其它批次，以服务器允许的动作为准。'
  },
  DROPPED: {
    label: '已退课',
    tone: 'muted',
    description: '本人记录已更新为已退课。课程余量与课表请以服务器最新结果为准。'
  },
  COURSE_CANCELLED: {
    label: '课程取消',
    tone: 'danger',
    description: '课程已经取消。若学校开放补选，页面会显示服务器下发的办理入口。'
  },
  RESULT_UNKNOWN: {
    label: '结果待核实',
    tone: 'warning',
    description: '网络中断或返回状态不完整。页面不会自动重复提交，正在核对本人正式记录。'
  }
})

const RECORD_STATUSES = new Set([
  'PENDING_LOTTERY', 'SELECTED', 'LOCKED', 'LOTTERY_LOST', 'DROPPED', 'COURSE_CANCELLED'
])

export const normalizeSelectionStatus = (value) => String(value || '').trim().toUpperCase()

export function selectionStatusMeta(value) {
  const status = normalizeSelectionStatus(value)
  return SELECTION_STATUS[status] || {
    label: status ? '状态待核实' : '结果待核实',
    tone: 'warning',
    description: '服务器返回了当前客户端尚未识别的状态，请刷新本人记录后再办理。'
  }
}

export function isVisibleSelectionRecord(record) {
  if (!record || (!record.recordId && !record.selectionCourseId)) return false
  const status = normalizeSelectionStatus(record.status)
  return RECORD_STATUSES.has(status) || Boolean(status)
}

export function hasConfirmedSeat(record) {
  return ['SELECTED', 'LOCKED'].includes(normalizeSelectionStatus(record && record.status))
}

export function isPendingLottery(record) {
  return normalizeSelectionStatus(record && record.status) === 'PENDING_LOTTERY'
}

export function findSelectionRecord(records, selectionCourseId) {
  const wanted = String(selectionCourseId || '')
  return (Array.isArray(records) ? records : []).find((record) =>
    String(record && record.selectionCourseId || '') === wanted
  ) || null
}

export function isUncertainSelectionError(error) {
  if (!error) return true
  const code = normalizeSelectionStatus(error.code || error.errorCode || error.statusCode)
  const httpStatus = Number(error.httpStatus || error.statusCode || error.code)
  if (httpStatus >= 500 || httpStatus === 408 || httpStatus === 429) return true
  const text = String(error.message || error.errMsg || '').toLowerCase()
  if (['408', '429', 'SELECTION_BUSY', 'TIMEOUT', 'NETWORK_ERROR', 'REQUEST_TIMEOUT'].includes(code)) return true
  if (/timeout|timed out|network|连接|超时|断开|request:fail/.test(text)) return true
  return !error.biz
}

export function receiptFromRecord(record, fallbackName = '') {
  const status = normalizeSelectionStatus(record && record.status) || 'RESULT_UNKNOWN'
  return {
    status,
    courseName: (record && record.courseName) || fallbackName || '当前课程',
    ...selectionStatusMeta(status)
  }
}

// An old record (for example SELECTED after a timed-out DROP) does not
// establish the outcome of the current command.
export function recordConfirmsOperation(record, operation) {
  const status = normalizeSelectionStatus(record && record.status)
  return operation === 'DROP' ? status === 'DROPPED'
    : ['PENDING_LOTTERY', 'SELECTED', 'LOCKED'].includes(status)
}
