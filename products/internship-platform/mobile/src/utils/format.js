/** 轻量格式化工具（无第三方依赖） */

export function pad2(n) {
  return n < 10 ? '0' + n : '' + n
}

/** 相对时间：刚刚 / n分钟前 / n小时前 / 昨天 / MM-DD */
export function fromNow(input) {
  const d = new Date(input)
  if (isNaN(d.getTime())) return String(input || '')
  const diff = Date.now() - d.getTime()
  const min = Math.floor(diff / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return min + '分钟前'
  const hour = Math.floor(min / 60)
  if (hour < 24) return hour + '小时前'
  const day = Math.floor(hour / 24)
  if (day === 1) return '昨天'
  if (day < 7) return day + '天前'
  return pad2(d.getMonth() + 1) + '-' + pad2(d.getDate())
}

/** 距截止：已逾期 x天 / 剩 x天 / 今天到期 */
export function deadlineText(input) {
  const d = new Date(input)
  if (isNaN(d.getTime())) return ''
  const days = Math.ceil((d.getTime() - Date.now()) / 86400000)
  if (days < 0) return '已逾期 ' + Math.abs(days) + ' 天'
  if (days === 0) return '今天到期'
  return '剩 ' + days + ' 天'
}

export function isOverdue(input) {
  const d = new Date(input)
  return !isNaN(d.getTime()) && d.getTime() < Date.now()
}

/** 百分比夹取 0-100 */
export function clampPercent(v) {
  const n = Number(v) || 0
  return Math.max(0, Math.min(100, Math.round(n)))
}

/** 将带时区的接口时间转换为设备本地时间。 */
export function formatDateTime(input) {
  if (!input) return '—'
  const date = new Date(input)
  if (Number.isNaN(date.getTime())) return '—'
  return [date.getFullYear(), pad2(date.getMonth() + 1), pad2(date.getDate())].join('-') + ' ' + pad2(date.getHours()) + ':' + pad2(date.getMinutes())
}

export default { formatDateTime, pad2, fromNow, deadlineText, isOverdue, clampPercent }
