import { realRequest } from './request'
import { formatDateTime } from '../utils/format.js'

// T5 keeps the optimistic-lock version captured with the exact queue snapshot in memory only.
// No local storage and no second workflow authority: writes still delegate to canonical backend
// commands. Reloading the queue replaces the map, so a 409 refresh cannot accidentally reuse a
// stale version from an older snapshot.
const exceptionVersions = new Map()
let queueEpoch = 0

function rememberExceptionVersion(id, rawVersion) {
  const key = String(id || '')
  const version = Number(rawVersion)
  if (key && Number.isInteger(version) && version >= 0) exceptionVersions.set(key, version)
  else if (key) exceptionVersions.delete(key)
  return Number.isInteger(version) && version >= 0 ? version : null
}

export async function getInternshipReviewQueue({
  batchId = '', focusReportId = '', focusExceptionId = '', weeklyPage = 1, exceptionPage = 1, pageSize = 20, append = false
} = {}) {
  const epoch = ++queueEpoch
  if (!append) exceptionVersions.clear()
  const queryParts = [
    `weeklyPage=${encodeURIComponent(weeklyPage)}`,
    `exceptionPage=${encodeURIComponent(exceptionPage)}`,
    `pageSize=${encodeURIComponent(pageSize)}`
  ]
  // 普通进入由教师已选批次驱动；统一待办只传 recordId，后端会在范围校验后
  // 解析对应批次。小程序不从 recordId 推导或缓存任何跨学生业务上下文。
  if (String(batchId || '').trim()) queryParts.push(`batchId=${encodeURIComponent(String(batchId).trim())}`)
  if (String(focusReportId || '').trim()) queryParts.push(`recordId=${encodeURIComponent(String(focusReportId).trim())}`)
  if (String(focusExceptionId || '').trim()) queryParts.push(`exceptionId=${encodeURIComponent(String(focusExceptionId).trim())}`)
  const query = queryParts.join('&')
  const d = await realRequest(`/mobile/teacher/internship?${query}`)
  // A late queue must not replace the lock versions used by the visible batch.
  if (epoch !== queueEpoch) throw { code: 'STALE_READ', staleRead: true, message: '请以当前批次为准' }
  const reports = (d.weeklyReports || []).map((r) => ({
    id: String(r.id || r.reportId || ''), student: r.studentName || r.name || '',
    className: r.className || '', week: r.weekNumber ? ('第 ' + r.weekNumber + ' 周') : (r.week || ''),
    company: r.enterpriseName || r.company || '', post: r.positionName || r.post || '',
    submitTime: formatDateTime(r.submittedAt || r.submitAt || r.submitTime), status: r.status,
    riskFlag: r.riskFlag || '', wordCount: r.wordCount, isResubmit: r.isResubmit === true,
    statusLabel: r.statusLabel || '', expectedVersion: Number(r.version),
    version: Number(String(r.reportVersion || '').replace(/^v/i, '')) || 1,
    overdue: r.status === 'OVERDUE', tasks: r.workContent || '', gain: r.harvestContent || '',
    problem: r.planContent || ''
  }))
  const abnormal = (d.abnormalCheckins || []).map((e) => {
    const id = String(e.id || '')
    const expectedVersion = rememberExceptionVersion(id, e.version)
    return {
      id, student: e.studentName || e.name || '',
      className: e.className || '', company: e.enterpriseName || '', post: e.positionName || '',
      internshipId: String(e.internId || e.internshipId || ''),
      time: formatDateTime(e.exceptionDate || e.date), type: e.exceptionType || e.type || '',
      typeLabel: /[\u4e00-\u9fff]/.test(e.typeLabel || '') ? e.typeLabel : ({ OUT_OF_RANGE:'超范围', NO_LOCATION:'无定位', LOW_ACCURACY:'定位精度不足', LOCATION_UNCERTAIN:'定位待核实', MOCK_LOCATION:'模拟定位', MISSING:'缺卡' })[e.exceptionType || e.type] || '异常类型待核对',
      distance: String(e.distance || '—').replace(/\bkm\b/g,'千米'), note: e.note || '', status: e.status || 'PENDING_HANDLE',
      accuracy: String(e.accuracy || '—').replace(/\bm\b/g,'米'), address: e.address || '',
      deviceRisk: ({ normal:'未提示设备风险', mock:'疑似模拟定位', rooted:'设备安全信号异常', not_available:'未提供设备信号', '—':'未提供设备信号' })[String(e.deviceRisk || 'not_available').toLowerCase()] || '设备风险信号待核对',
      streak: e.streak || '', appealStatus: e.appealStatus || '', appealNote: e.appealNote || '',
      appealStatusLabel: ({ PENDING:'待核实申诉', ACCEPTED:'申诉已采纳', REJECTED:'申诉未采纳' })[e.appealStatus] || '申诉状态待核对',
      statusLabel: e.statusLabel || '', expectedVersion,
      decisionFactsComplete: e.decisionFactsComplete === true,
      missingDecisionFacts: Array.isArray(e.missingDecisionFacts) ? e.missingDecisionFacts : []
    }
  })
  return { reports, abnormal, batchId: String(d.batchId || ''), focusReportId: String(d.focusReportId || ''), focusExceptionId: String(d.focusExceptionId || ''), available: d.available !== false,
    errors: Array.isArray(d.errors) ? d.errors : [], pagination: d.pagination || {
    weeklyPage, exceptionPage, pageSize, weeklyHasMore: false, exceptionHasMore: false
  }, _real: true }
}

export function handleCheckin(id, action, comment, riskLevel = null) {
  const key = String(id || '')
  const expectedVersion = exceptionVersions.get(key)
  if (!key || !Number.isInteger(expectedVersion) || expectedVersion < 0) {
    const error = new Error('打卡异常版本已失效，请刷新后重试')
    error.code = 'DATA_CONFLICT'
    error.statusCode = 409
    return Promise.reject(error)
  }
  if (action === 'TO_RISK' && riskLevel !== 'HIGH') {
    const error = new Error('转风险必须明确确认高风险等级')
    error.code = 'VALIDATION_ERROR'
    return Promise.reject(error)
  }
  const url = `/internship/exceptions/${encodeURIComponent(key)}/handle`
  const finish = (result) => {
    // The queue page reloads authoritative truth after success. Drop this snapshot immediately so
    // a double tap or a future accidental reuse cannot issue a second command with the old version.
    exceptionVersions.delete(key)
    return result
  }
  if (!riskLevel) {
    return realRequest(url, {
      method: 'POST',
      data: { action, comment: comment || '', expectedVersion }
    }).then(finish)
  }
  return realRequest(url, {
    method: 'POST',
    data: { action, comment: comment || '', expectedVersion, riskLevel }
  }).then(finish)
}
