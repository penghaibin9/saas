import { WALL_METRICS } from '../config/studentAffairsWall.contract.js'

const finite = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
const statusFromCode = code => [401, 403, 401001, 403001].includes(Number(code)) ? 'RESTRICTED' : Number(code) === 403002 ? 'NO_SCOPE' : 'ERROR'

export const wallPacket = result => result?.code === 0 && result.data && typeof result.data === 'object'
  ? { status: 'OK', data: result.data }
  : { status: statusFromCode(result?.code), message: result?.message || '' }

function readDashboard(data, definition) {
  if (definition.id === 'riskStudents') {
    const direct = finite(data?.riskSummary?.openStudentCount)
    if (direct !== null) return direct
  }
  const rows = Array.isArray(data?.summaryCards) ? data.summaryCards.filter(item => item?.key === definition.field) : []
  return rows.length === 1 ? finite(rows[0]?.value) : null
}

function readDomain(data, definition) {
  const rows = Array.isArray(data?.domains) ? data.domains.filter(item => item?.key === definition.key) : []
  if (rows.length > 1) return { value: null, status: 'INVALID' }
  const item = rows.length === 1 ? rows[0] : data?.domainsByKey?.[definition.key]
  if (!item) return { value: null, status: 'MISSING' }
  if (item.status !== 'OK') return { value: null, status: ['ERROR', 'RESTRICTED', 'NO_SCOPE'].includes(item.status) ? item.status : 'MISSING', message: item.message || '' }
  const value = definition.field === 'total' ? finite(item.metrics?.total ?? item.total) : finite(item.metrics?.[definition.field])
  return { value, status: value === null ? 'MISSING' : 'OK' }
}

export function projectStudentAffairsWall({ dashboard, cockpit, leaveTypes, context, receivedAt = '' } = {}) {
  const noScope = [dashboard?.data?.scopeMode, context?.dataScope?.scopeType, context?.dataScope?.scopeMode].some(mode => String(mode || '').toUpperCase() === 'NONE')
  const gate = noScope ? 'NO_SCOPE' : ''
  const metrics = {}
  WALL_METRICS.forEach(definition => {
    const source = definition.source === 'dashboard' ? dashboard : cockpit
    if (gate) metrics[definition.id] = { ...definition, value: null, status: gate }
    else if (!source || source.status !== 'OK') metrics[definition.id] = { ...definition, value: null, status: source?.status || 'MISSING', message: source?.message || '' }
    else if (definition.source === 'dashboard') {
      const value = readDashboard(source.data, definition)
      metrics[definition.id] = { ...definition, value, status: value === null ? 'MISSING' : 'OK' }
    } else metrics[definition.id] = { ...definition, ...readDomain(source.data, definition) }
  })
  const derive = (id, label, unit, dependencies, calculate, route, note) => {
    const dep = dependencies.map(key => metrics[key])
    const inherited = gate || dep.find(item => item?.status !== 'OK')?.status
    const value = inherited ? null : calculate(...dep.map(item => item.value))
    metrics[id] = { id, label, unit, route, note, value, status: inherited || (value === null ? 'INVALID' : 'OK') }
  }
  derive('riskClosed', '已关闭风险记录', '条', ['riskTotal', 'riskOpen'], (total, open) => open <= total ? total - open : null, 'risk', '同范围风险记录总量减未关闭记录')
  derive('riskRate', '风险记录关闭占比', '%', ['riskTotal', 'riskClosed'], (total, closed) => total > 0 ? closed / total * 100 : null, 'risk', '存量构成，不是本月绩效指标')
  derive('occupancy', '床位入住率', '%', ['beds', 'occupied'], (total, occupied) => total > 0 && occupied <= total ? occupied / total * 100 : null, 'dorm', '已入住床位除以总床位')
  if (metrics.riskTotal?.status === 'OK' && metrics.riskTotal.value === 0) metrics.riskRate.status = 'EMPTY'
  if (metrics.beds?.status === 'OK' && metrics.beds.value === 0) metrics.occupancy.status = 'EMPTY'

  let breakdown = []
  let breakdownStatus = gate || leaveTypes?.status || 'MISSING'
  if (breakdownStatus === 'OK') {
    const raw = leaveTypes.data?.breakdown
    if (!Array.isArray(raw) || leaveTypes.data?.groupBy !== 'TYPE') breakdownStatus = 'INVALID'
    else {
      breakdown = raw.map(row => ({ label: String(row?.label || '未命名类型').slice(0, 32), value: finite(row?.count) }))
      if (breakdown.some(row => row.value === null)) { breakdown = []; breakdownStatus = 'INVALID' }
    }
  }
  return {
    metrics, breakdown, breakdownStatus,
    scope: String(dashboard?.data?.scopeLabel || context?.dataScope?.scopeLabel || context?.dataScope?.scopeName || '当前授权范围'),
    brand: String(context?.tenantBrandConfig?.schoolName || '学工中心').slice(0, 40),
    receivedAt,
    sourceTimes: { dashboard: dashboard?.data?.updatedAt || '', cockpit: cockpit?.data?.updatedAt || '' },
    reconcile: cockpit?.data?.disciplineReconcileConsistent ?? null
  }
}

export function formatWallMetric(metric, digits = 0) {
  if (!metric || metric.status !== 'OK' || metric.value === null) return '—'
  return metric.unit === '%' ? metric.value.toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: 1 }) : metric.value.toLocaleString('zh-CN')
}
