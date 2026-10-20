/** Public wall projection: reject malformed or contradictory aggregates; never expose individual coordinates. */
export const EXTENSION_VERSION = 'ix-command-screen-1'
const integer = v => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0 ? v : null
const text = (v, max = 40) => typeof v === 'string' ? v.slice(0, max) : ''
const array = (v, max) => Array.isArray(v) ? v.slice(0, max) : []
const validDay = s => /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$/.test(s) && new Date(s + 'T00:00:00Z').toISOString().slice(0, 10) === s
const validMonth = s => /^\d{4}-(0[1-9]|1[0-2])$/.test(s)
const unique = (rows, key) => rows.filter((row, index) => rows.findIndex(other => other[key] === row[key]) === index)
export function normalizeExtension(raw, total) {
  const missing = { available: false, totals: {}, regions: [], majors: [], riskLevels: [], riskNewDaily: [], attendanceDaily: [], employmentMonths: [], issue: '大屏聚合未返回；地图和排行不使用预览数字补齐' }
  if (!raw) return missing
  if (raw.contractVersion !== EXTENSION_VERSION) return { ...missing, issue: '大屏聚合版本不匹配，请安装包内只读聚合端点' }
  if (total === null || integer(raw.totals?.students) !== total) return { ...missing, issue: '聚合与统计人数不一致；已隐藏地图与排行，请刷新' }
  const keys = ['students', 'enterprises', 'positions', 'schoolMentors', 'enterpriseMentors', 'pendingExceptions', 'visits7d', 'openRisks']
  const totals = Object.fromEntries(keys.map(key => [key, integer(raw.totals?.[key])]))
  const regions = array(raw.regions, 35).map(r => ({ code: /^\d{6}$/.test(String(r.code)) ? String(r.code) : '', name: text(r.name, 12), students: integer(r.students), enterprises: integer(r.enterprises) })).filter(r => r.code && r.name && r.students !== null && r.enterprises !== null)
  const majors = array(raw.majors, 8).map(r => ({ name: text(r.name), students: integer(r.students), enterprises: integer(r.enterprises) })).filter(r => r.name && r.students !== null && r.enterprises !== null)
  const riskLevels = array(raw.riskLevels, 4).map(r => ({ key: ['HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'].includes(r.key) ? r.key : 'UNKNOWN', value: integer(r.value) })).filter(r => r.value !== null)
  const geography = { unlocatedStudents: integer(raw.geography?.unlocatedStudents), unlocatedEnterprises: integer(raw.geography?.unlocatedEnterprises) }
  const invalid = Object.values(totals).some(v => v === null) ||
    totals.enterprises > total || totals.positions > total || totals.schoolMentors > total || totals.enterpriseMentors > total ||
    geography.unlocatedStudents === null || geography.unlocatedEnterprises === null ||
    regions.reduce((sum, r) => sum + r.students, 0) + geography.unlocatedStudents !== total ||
    regions.reduce((sum, r) => sum + r.enterprises, 0) + geography.unlocatedEnterprises !== totals.enterprises ||
    new Set(regions.map(r => r.code)).size !== regions.length ||
    riskLevels.reduce((sum, r) => sum + r.value, 0) !== totals.openRisks ||
    majors.reduce((sum, r) => sum + r.students, 0) > total
  if (invalid) return { ...missing, issue: '大屏聚合校验失败：分布合计、去重数量或必需字段异常' }
  const daily = (rows, attendance = false) => unique(array(rows, 7).map(r => ({ date: text(r.date, 10), value: integer(r.value), ...(attendance ? { compliant: integer(r.compliant) } : {}) })).filter(r => validDay(r.date) && r.value !== null && (!attendance || (r.compliant !== null && r.compliant <= r.value))), 'date').sort((a,b) => a.date.localeCompare(b.date))
  const riskNewDaily = daily(raw.riskNewDaily), attendanceDaily = daily(raw.attendanceDaily, true)
  const employmentMonths = unique(array(raw.employmentMonths, 6).map(r => ({ month: text(r.month, 7), value: integer(r.value) })).filter(r => validMonth(r.month) && r.value !== null), 'month').sort((a,b)=>a.month.localeCompare(b.month))
  const issue = [riskNewDaily.length !== 7 ? '风险新增日序列不完整' : '', attendanceDaily.length !== 7 ? '打卡日序列不完整' : '', employmentMonths.length !== 6 ? '签约月份序列不完整' : ''].filter(Boolean).join('；')
  return { available: true, totals, regions, majors, riskLevels, geography,
    riskNewDaily, attendanceDaily, employmentMonths, issue,
    snapshotAt: text(raw.snapshotAt, 40), timezone: text(raw.timezone, 50),
    quality: array(raw.quality, 8).map(q => text(q, 120)),
    majorOther: Math.max(0, total - majors.reduce((sum, r) => sum + r.students, 0)) }
}
