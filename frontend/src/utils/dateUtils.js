/**
 * 全系统公共日期工具（唯一口径）。
 * 页面禁止再散落写 Date 格式化 / 空值判断 / 逾期文案。
 *
 * 统一对外字符串：
 * - 日期：YYYY-MM-DD
 * - 日期时间：YYYY-MM-DDTHH:mm（与原生 datetime-local 对齐；提交接口时可再 toISOString）
 */

export const DATE_FMT = 'YYYY-MM-DD'
export const DATETIME_FMT = 'YYYY-MM-DD HH:mm'
export const EMPTY_LABEL = '未设置'
export const FILTER_EMPTY_LABEL = '全部时间'
export const FILTER_EMPTY_LABEL_ALT = '不限日期'

const PAD = (n) => String(n).padStart(2, '0')

export function isEmptyDate(v) {
  if (v == null) return true
  if (typeof v === 'string' && !v.trim()) return true
  if (v instanceof Date && Number.isNaN(v.getTime())) return true
  return false
}

/** 解析为本地 Date；无效返回 null（不抛 Invalid Date） */
export function parseDate(v) {
  if (isEmptyDate(v)) return null
  if (v instanceof Date) return Number.isNaN(v.getTime()) ? null : v
  const s = String(v).trim()
  // 纯日期按本地日处理，避免 UTC 偏移掉到前一天
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) {
    const [y, m, d] = s.split('-').map(Number)
    const dt = new Date(y, m - 1, d, 0, 0, 0, 0)
    return Number.isNaN(dt.getTime()) ? null : dt
  }
  // datetime-local / ISO
  const norm = s.includes('T') ? s : s.replace(' ', 'T')
  const dt = new Date(norm)
  return Number.isNaN(dt.getTime()) ? null : dt
}

export function startOfDay(d = new Date()) {
  const x = new Date(d)
  x.setHours(0, 0, 0, 0)
  return x
}

export function endOfDay(d = new Date()) {
  const x = new Date(d)
  x.setHours(23, 59, 0, 0)
  return x
}

export function addDays(d, n) {
  const x = new Date(d)
  x.setDate(x.getDate() + n)
  return x
}

export function formatDate(v, fallback = EMPTY_LABEL) {
  const d = parseDate(v)
  if (!d) return fallback
  return `${d.getFullYear()}-${PAD(d.getMonth() + 1)}-${PAD(d.getDate())}`
}

export function formatDateTime(v, fallback = EMPTY_LABEL) {
  const d = parseDate(v)
  if (!d) return fallback
  return `${formatDate(d)} ${PAD(d.getHours())}:${PAD(d.getMinutes())}`
}

/** 用于绑定原生 input[type=date] */
export function toDateInputValue(v) {
  return formatDate(v, '')
}

/** 用于绑定原生 input[type=datetime-local] */
export function toDateTimeInputValue(v) {
  const d = parseDate(v)
  if (!d) return ''
  return `${formatDate(d)}T${PAD(d.getHours())}:${PAD(d.getMinutes())}`
}

/** 截止时刻：给定日期的 23:59 */
export function toDeadlineValue(v) {
  const d = parseDate(v)
  if (!d) return ''
  const day = formatDate(d)
  return `${day}T23:59`
}

export function withDeadlineTime(dateOrDateTime) {
  if (isEmptyDate(dateOrDateTime)) return ''
  const day = formatDate(dateOrDateTime, '')
  if (!day) return ''
  return `${day}T23:59`
}

export function todayDate() {
  return formatDate(new Date())
}

export function tomorrowDate() {
  return formatDate(addDays(new Date(), 1))
}

/** 本周五 23:59（若今天已过周五则取本周五；周一~日） */
export function thisFridayDeadline() {
  const now = startOfDay(new Date())
  const day = now.getDay() // 0 Sun … 5 Fri
  const delta = day <= 5 ? 5 - day : 6 // 周日 → 下周五也可：这里取本周五=当天若已过则仍返回本周已过的周五供展示；快捷选「本周五」时若过了则取「下周五」
  const target = day === 0 ? addDays(now, 5) : day <= 5 ? addDays(now, 5 - day) : addDays(now, 6)
  return toDeadlineValue(target)
}

export function daysFromNowDeadline(n) {
  return toDeadlineValue(addDays(new Date(), n))
}

export function validateRange(start, end) {
  const a = parseDate(start)
  const b = parseDate(end)
  if (!a || !b) return { ok: true, message: '' }
  if (a.getTime() > b.getTime()) {
    return { ok: false, message: '开始时间不能晚于结束时间' }
  }
  return { ok: true, message: '' }
}

export function ensureEndAfterStart(start, end) {
  const check = validateRange(start, end)
  return check
}

/**
 * 截止展示语义
 * @param {string|Date} deadline
 * @param {{ status?: string, archived?: boolean, completed?: boolean, now?: Date }} opts
 */
export function getDeadlineMeta(deadline, opts = {}) {
  if (opts.archived || opts.status === 'ARCHIVED') {
    return { kind: 'archived', label: '已归档', tone: 'info', daysLeft: null }
  }
  if (opts.completed || opts.status === 'COMPLETED' || opts.status === 'DONE') {
    return { kind: 'completed', label: '已完成', tone: 'success', daysLeft: null }
  }
  const d = parseDate(deadline)
  if (!d) {
    return { kind: 'empty', label: EMPTY_LABEL, tone: 'default', daysLeft: null }
  }
  const now = startOfDay(opts.now || new Date())
  const due = startOfDay(d)
  const diff = Math.round((due.getTime() - now.getTime()) / 86400000)
  if (diff < 0) {
    return { kind: 'overdue', label: '已逾期', tone: 'danger', daysLeft: diff }
  }
  if (diff === 0) {
    return { kind: 'today', label: '今天截止', tone: 'warning', daysLeft: 0 }
  }
  if (diff === 1) {
    return { kind: 'tomorrow', label: '明天截止', tone: 'warning', daysLeft: 1 }
  }
  return { kind: 'remain', label: `剩余 ${diff} 天`, tone: 'primary', daysLeft: diff }
}

export function formatDeadlineDisplay(deadline, opts = {}) {
  const meta = getDeadlineMeta(deadline, opts)
  if (meta.kind === 'empty') return EMPTY_LABEL
  if (meta.kind === 'archived' || meta.kind === 'completed' || meta.kind === 'overdue' ||
      meta.kind === 'today' || meta.kind === 'tomorrow' || meta.kind === 'remain') {
    const base = formatDateTime(deadline, '') || formatDate(deadline, '')
    if (meta.kind === 'remain' || meta.kind === 'today' || meta.kind === 'tomorrow' || meta.kind === 'overdue') {
      return base ? `${base}（${meta.label}）` : meta.label
    }
    return meta.label
  }
  return formatDateTime(deadline)
}

/** 展示任意日期，空值安全 */
export function formatSafeDisplay(v, { withTime = false, empty = EMPTY_LABEL } = {}) {
  if (isEmptyDate(v)) return empty
  return withTime ? formatDateTime(v, empty) : formatDate(v, empty)
}

/** 本周（周一 ~ 周日） */
export function rangeThisWeek() {
  const now = startOfDay(new Date())
  const day = now.getDay() || 7
  const mon = addDays(now, 1 - day)
  const sun = addDays(mon, 6)
  return { start: formatDate(mon), end: formatDate(sun) }
}

export function rangeThisMonth() {
  const now = new Date()
  const start = new Date(now.getFullYear(), now.getMonth(), 1)
  const end = new Date(now.getFullYear(), now.getMonth() + 1, 0)
  return { start: formatDate(start), end: formatDate(end) }
}

/**
 * 本学期粗估：
 * - 9~1 月：秋季学期 当年-09-01 ~ 次年-01-31
 * - 2~8 月：春季学期 当年-02-01 ~ 当年-08-31
 */
export function rangeThisSemester(now = new Date()) {
  const y = now.getFullYear()
  const m = now.getMonth() + 1
  if (m >= 9 || m === 1) {
    const sy = m === 1 ? y - 1 : y
    return { start: `${sy}-09-01`, end: `${sy + 1}-01-31` }
  }
  return { start: `${y}-02-01`, end: `${y}-08-31` }
}

export function rangeToday() {
  const t = todayDate()
  return { start: t, end: t }
}

export function rangeYesterday() {
  const t = formatDate(addDays(new Date(), -1))
  return { start: t, end: t }
}

/** 筛选快捷项 */
export const FILTER_SHORTCUTS = [
  { key: 'today', label: '今天', range: () => rangeToday() },
  { key: 'yesterday', label: '昨天', range: () => rangeYesterday() },
  { key: 'week', label: '本周', range: () => rangeThisWeek() },
  { key: 'month', label: '本月', range: () => rangeThisMonth() },
  { key: 'semester', label: '本学期', range: () => rangeThisSemester() },
  { key: 'clear', label: '清空', range: () => ({ start: '', end: '' }) }
]

/** 截止快捷项（不含批次；批次由组件注入） */
export const DEADLINE_SHORTCUTS = [
  { key: 'today', label: '今天 23:59', value: () => toDeadlineValue(new Date()) },
  { key: 'tomorrow', label: '明天 23:59', value: () => daysFromNowDeadline(1) },
  { key: 'friday', label: '本周五 23:59', value: () => thisFridayDeadline() },
  { key: 'd7', label: '7 天后 23:59', value: () => daysFromNowDeadline(7) },
  { key: 'd14', label: '14 天后 23:59', value: () => daysFromNowDeadline(14) },
  { key: 'd30', label: '30 天后 23:59', value: () => daysFromNowDeadline(30) },
  { key: 'clear', label: '清空', value: () => '' }
]

const MEMORY_PREFIX = 'app.dateFilter:'

export function loadFilterMemory(pageKey) {
  if (!pageKey || typeof sessionStorage === 'undefined') return null
  try {
    const raw = sessionStorage.getItem(MEMORY_PREFIX + pageKey)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveFilterMemory(pageKey, value) {
  if (!pageKey || typeof sessionStorage === 'undefined') return
  try {
    if (value == null || (typeof value === 'object' && !value.start && !value.end && !value.date)) {
      sessionStorage.removeItem(MEMORY_PREFIX + pageKey)
      return
    }
    sessionStorage.setItem(MEMORY_PREFIX + pageKey, JSON.stringify(value))
  } catch { /* ignore quota */ }
}

export function clearFilterMemory(pageKey) {
  if (!pageKey || typeof sessionStorage === 'undefined') return
  try { sessionStorage.removeItem(MEMORY_PREFIX + pageKey) } catch { /* ignore */ }
}

/**
 * 表单默认起止：优先批次，其次今天 / 截止日期 23:59
 */
export function defaultsFromBatch(batch, { asDeadline = false } = {}) {
  if (!batch) {
    return {
      start: todayDate(),
      end: asDeadline ? toDeadlineValue(addDays(new Date(), 30)) : formatDate(addDays(new Date(), 30))
    }
  }
  const start = formatDate(batch.startDate || batch.startAt || batch.beginDate, '') || todayDate()
  let endRaw = batch.endDate || batch.endAt || batch.deadline || batch.closeDate
  if (!endRaw) endRaw = addDays(parseDate(start) || new Date(), 30)
  const end = asDeadline ? withDeadlineTime(endRaw) : formatDate(endRaw, '')
  return { start, end }
}

export default {
  DATE_FMT,
  DATETIME_FMT,
  EMPTY_LABEL,
  FILTER_EMPTY_LABEL,
  isEmptyDate,
  parseDate,
  formatDate,
  formatDateTime,
  formatSafeDisplay,
  formatDeadlineDisplay,
  getDeadlineMeta,
  toDateInputValue,
  toDateTimeInputValue,
  toDeadlineValue,
  withDeadlineTime,
  validateRange,
  FILTER_SHORTCUTS,
  DEADLINE_SHORTCUTS,
  loadFilterMemory,
  saveFilterMemory,
  clearFilterMemory,
  defaultsFromBatch
}
