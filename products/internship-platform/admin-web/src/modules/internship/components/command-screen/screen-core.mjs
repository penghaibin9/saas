import { normalizeExtension } from './screen-extension.mjs'

/** Read-only projection. No fixtures, HTTP clients, business writes or persisted data here. */
export const ROUTES = Object.freeze({
  stats: ['/admin/internship/stats', 'internship.stats.view'],
  enterprises: ['/admin/internship/enterprises', 'internship.enterprise.view'],
  positions: ['/admin/internship/positions', 'internship.position.view'],
  students: ['/admin/internship/students', 'internship.student.view'],
  match: ['/admin/internship/match', 'internship.match.intention.view'],
  agreements: ['/admin/internship/agreements', 'internship.agreement.view'],
  attendance: ['/admin/internship/attendance', 'internship.attendance.view'],
  exceptions: ['/admin/internship/exceptions', 'internship.attendance.view'],
  reports: ['/admin/internship/reports', 'internship.report.view'],
  guidance: ['/admin/internship/guidance', 'internship.guidance.view'],
  evaluation: ['/admin/internship/enterprise-evals', 'internship.eval.enterprise.view'],
  scores: ['/admin/internship/scores', 'internship.score.view'],
  archive: ['/admin/internship/archive', 'internship.archive.view'],
  risks: ['/admin/internship/risk-disposal', 'internship.risk.handle']
})
export const REQUIRED_PERMISSIONS = [...new Set([
  'internship.stats.view', 'internship.dashboard.view', ...Object.values(ROUTES).map(v => v[1])
])]
export const METRIC_LABELS = Object.freeze({
  placementRate: '实习落实率', matchRate: '岗位匹配率', agreementSignRate: '协议签署率',
  arrivalRate: '到岗覆盖率', checkinComplyRate: '打卡合规率', leaveComplyRate: '请假合规率',
  weeklySubmitRate: '周报提交覆盖率', weeklyReviewRate: '周报批阅率',
  guidanceCoverRate: '指导覆盖率', visitCoverRate: '巡访覆盖率', riskCloseRate: '风险闭环率',
  enterpriseEvalRate: '企业评价完成率', studentEvalRate: '学生自评完成率',
  scorePublishRate: '成绩发布率', employmentRate: '就业转化率',
  helpCoverRate: '未就业帮扶覆盖率', archiveRate: '归档完成率'
})
export const FLOW = Object.freeze([
  ['选岗', '岗位匹配', 'matchRate', 'match', 'search'],
  ['签约', '协议生效', 'agreementSignRate', 'agreements', 'file'],
  ['到岗', '有效打卡覆盖', 'arrivalRate', 'attendance', 'pin'],
  ['打卡', '记录合规', 'checkinComplyRate', 'attendance', 'calendar'],
  ['周报', '学生提交覆盖', 'weeklySubmitRate', 'reports', 'file'],
  ['巡访', '过程指导', 'visitCoverRate', 'guidance', 'pin'],
  ['评价', '企业评价', 'enterpriseEvalRate', 'evaluation', 'star'],
  ['考核', '成绩发布', 'scorePublishRate', 'scores', 'bars'],
  ['就业', '台账落实', 'employmentRate', 'stats', 'briefcase']
])
export function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}
export function finite(value) {
  if (!['number', 'string'].includes(typeof value) || (typeof value === 'string' && !value.trim())) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}
export function count(value) {
  const n = finite(value)
  return n !== null && n >= 0 && Number.isSafeInteger(n) ? n : null
}
export function formatCount(value) { const n = count(value); return n === null ? '—' : n.toLocaleString('zh-CN') }
export function formatRate(value) { const n = finite(value); return n === null || n < 0 || n > 100 ? '—' : `${n.toFixed(1)}%` }
export function can(context, code) { return context?.grants?.[code] === true && context?.accessHealthy !== false }
export function routeFor(key, context) {
  const spec = ROUTES[key]
  if (!spec || !context?.batchId || !can(context, spec[1])) return null
  return `${spec[0]}?${new URLSearchParams({ batchId: String(context.batchId) })}`
}
/** Never trust a route string or student name from the dashboard projection. */
export function workRoute(item, context) {
  if (!item || !/^\d+$/.test(String(item.objectId || ''))) return null
  let key, path
  if (item.kind === 'RISK') { key = 'risks'; path = '/admin/internship/risk-disposal' }
  else if (item.kind === 'ATTENDANCE_EXCEPTION') { key = 'exceptions'; path = `/admin/internship/exceptions/${item.objectId}` }
  else if (item.kind === 'WEEKLY_REPORT') { key = 'reports'; path = `/admin/internship/reports/${item.objectId}` }
  else return null
  if (!routeFor(key, context)) return null
  const q = new URLSearchParams({ batchId: String(context.batchId) })
  if (key === 'risks') q.set('id', String(item.objectId))
  return `${path}?${q}`
}
export function metricOf(list, key) {
  const raw = Array.isArray(list) ? list.find(m => m?.key === key) : null
  if (!raw) return { key, label: METRIC_LABELS[key] || key, rate: null, numerator: null, denominator: null, state: 'missing', note: '接口未返回此指标' }
  const numerator = count(raw.numerator), denominator = count(raw.denominator), r = finite(raw.rate)
  const invalid = raw.anomaly === true || numerator === null || denominator === null || numerator > denominator ||
    (r !== null && (r < 0 || r > 100 || (denominator > 0 && Math.abs(r - numerator / denominator * 100) > 0.11)))
  const empty = denominator === 0
  const state = invalid ? 'anomaly' : empty ? 'empty' : r === null ? 'missing' : 'ok'
  const note = ['enterpriseEvalRate', 'studentEvalRate'].includes(key)
    ? '当前基线的指标字典与 service 分母描述不一致。本屏照接口分子、分母展示，不能作为已核定监管报表；见审计 A03。'
    : (raw.note || raw.definition?.note || '沿用实习统计服务口径')
  return { key, label: METRIC_LABELS[key] || String(raw.label || key), numerator, denominator,
    rate: state === 'ok' ? r : null, state, note,
    threshold: finite(raw.threshold), warn: state === 'ok' && raw.warn === true,
    definition: raw.definition || null, definitionIssue: ['enterpriseEvalRate', 'studentEvalRate'].includes(key) }
}
export function isAccessError(error) {
  const code = String(error?.code || '')
  return /^(401|403)/.test(code) || ['NO_PERMISSION', 'FORBIDDEN', 'UNAUTHORIZED', 'TOKEN_EXPIRED'].includes(code) ||
    /无权限|权限不足|登录已|请.*登录|401|403/.test(String(error?.message || ''))
}
function responseError(value, label) {
  return { code: value?.code || 'UNAVAILABLE', message: String(value?.message || `${label}暂不可用`).slice(0, 160) }
}
export function unwrap(value, batchId, label) {
  if (!value || value.code !== 0 || !value.data || typeof value.data !== 'object') throw responseError(value, label)
  const d = value.data
  const ids = [d.batchId, d.appliedFilters?.batchId, d.dimensions?.batchId].filter(v => v !== undefined && v !== null)
  if (!ids.length || ids.some(v => String(v) !== String(batchId))) throw { code: 'BATCH_MISMATCH', message: `${label}批次回执不一致，已阻止串批次展示` }
  return d
}
function counter(data, key) { return count((Array.isArray(data?.counters) ? data.counters : []).find(c => c?.key === key)?.value) }
/** Backend percentages are used as returned; only chart shares use count / sum. */
export function project(overview, dashboard, trends, context, issues = [], extension = null) {
  const metrics = Object.fromEntries(Object.keys(METRIC_LABELS).map(key => [key, metricOf(overview.metrics, key)]))
  const total = counter(overview, 'totalStudents'), onboard = counter(overview, 'onboardStudents')
  const flowRaw = Array.isArray(dashboard?.flow) ? dashboard.flow : []
  const states = flowRaw.map(f => ({ label: String(f.label || ''), value: count(f.value) })).filter(f => f.label && f.value !== null)
  const stateTotal = states.reduce((a, b) => a + b.value, 0)
  const coherent = states.length > 0 && total !== null && stateTotal === total
  const work = (Array.isArray(dashboard?.workItems) ? dashboard.workItems : []).slice(0, 8).map(item => ({
    kind: item.kind, objectId: /^\d+$/.test(String(item.objectId || '')) ? String(item.objectId) : '',
    tone: item.tone === 'danger' ? 'danger' : 'warning', route: workRoute(item, context),
    label: ({ RISK: '风险跟进', ATTENDANCE_EXCEPTION: '考勤核实', WEEKLY_REPORT: '周报批阅' })[item.kind] || '待核实事项'
  }))
  const distribution = (Array.isArray(overview.scoreDistribution) ? overview.scoreDistribution : []).map(d => ({
    label: String(d.bucket || ''), count: count(d.count)
  })).filter(d => d.label && d.count !== null)
  const allowedSeries = new Set(['records', 'reports', 'guidance', 'visits'])
  const series = (Array.isArray(trends?.series) ? trends.series : []).filter(s => allowedSeries.has(s.key)).map(s => ({
    key: s.key, label: String(s.label || s.key), points: (Array.isArray(s.points) ? s.points : []).filter(p => /^\d{4}-\d{2}$/.test(p.month)).slice(-12).map(p => ({ month: p.month, value: count(p.value) }))
  }))
  const extra = normalizeExtension(extension, total)
  return { extra, metrics, total, onboard, riskStudents: counter(overview, 'riskStudents'),
    states: coherent ? states : [], stateCoherent: coherent,
    stateIssue: states.length && !coherent ? '跨接口快照计数不同，请刷新核对' : '',
    distribution, series, work, workTotal: count(dashboard?.workItemTotal),
    dashboardAvailable: dashboard !== null, trendsAvailable: trends !== null,
    batchId: String(context.batchId), batchName: String(overview.batchName || context.batchName || ''),
    generatedAt: String(overview.generatedAt || ''), trendGeneratedAt: String(trends?.generatedAt || ''),
    metricVersion: String(overview.metricVersion || ''),
    scopeMode: String(overview.appliedFilters?.scopeMode || overview.dimensions?.scopeMode || ''),
    issues: [...issues, ...(extra.issue ? [extra.issue] : []), ...(Array.isArray(overview.partial) ? overview.partial : []).map(p => String(p?.reason || p?.label || '部分统计不可用'))]
  }
}
/** At most four source requests: existing metrics + dashboard + trends + audited extension. */
export async function readSnapshot(loaders, context) {
  if (!context?.batchId) return { status: 'no-batch', message: '先选择实习批次，再查看监管大屏' }
  if (context?.batchError) return { status: 'error', message: context.batchError }
  if (!can(context, 'internship.stats.view')) return { status: 'denied', message: '当前身份无实习统计查看权限，未发起数据请求' }
  const params = { batchId: String(context.batchId) }
  const call = fn => Promise.resolve().then(fn)
  const results = await Promise.allSettled([
    call(() => loaders.overview(params)),
    can(context, 'internship.dashboard.view') ? call(() => loaders.dashboard(params)) : Promise.resolve(null),
    typeof loaders.trends === 'function' ? call(() => loaders.trends({ ...params, months: 6 })) : Promise.resolve(null),
    typeof loaders.extension === 'function' ? call(() => loaders.extension(params)) : Promise.resolve(null)
  ])
  const names = ['统计总览', '工作台待办', '月度趋势', '大屏聚合'], data = [null, null, null, null], errors = []
  results.forEach((result, i) => {
    if (result.status === 'rejected') { errors.push({ index: i, ...responseError(result.reason, names[i]) }); return }
    if (i !== 0 && result.value === null) return
    try { data[i] = unwrap(result.value, context.batchId, names[i]) }
    catch (e) { errors.push({ index: i, ...e }) }
  })
  if (errors.some(isAccessError)) return { status: 'denied', message: '登录或权限已变化，已清除大屏数据；请退出并重新核验身份' }
  if (!data[0]) return { status: 'error', message: errors.find(e => e.index === 0)?.message || '统计数据加载失败' }
  try { return { status: 'ready', model: project(data[0], data[1], data[2], context, errors.map(e => `${names[e.index]}：${e.message}`), data[3]) } }
  catch { return { status: 'error', message: '统计响应结构不符合已冻结契约，请核查当前服务版本' } }
}
/** Generation guard: a late response may not replace data after a batch/identity change. */
export function createCoordinator(load, commit) {
  let generation = 0, pending = null, disposed = false
  return {
    invalidate() { generation++; pending = null },
    async run(context) {
      if (disposed) return
      if (pending) return pending
      const own = ++generation
      pending = Promise.resolve().then(() => load(context)).then(result => {
        if (!disposed && own === generation) commit(result, context)
        return result
      }).catch(error => {
        const result = { status: 'error', message: String(error?.message || '请求失败') }
        if (!disposed && own === generation) commit(result, context)
        return result
      }).finally(() => { if (own === generation) pending = null })
      return pending
    },
    destroy() { disposed = true; generation++; pending = null }
  }
}
