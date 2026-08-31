import { realRequest } from './request'

// T5 keeps the optimistic-lock version captured with the exact queue snapshot in memory only.
// No local storage and no second workflow authority: writes still delegate to canonical backend
// commands. Reloading the queue replaces the map, so a 409 refresh cannot accidentally reuse a
// stale version from an older snapshot.
const exceptionVersions = new Map()

function rememberExceptionVersion(id, rawVersion) {
  const key = String(id || '')
  const version = Number(rawVersion)
  if (key && Number.isInteger(version) && version >= 0) exceptionVersions.set(key, version)
  else if (key) exceptionVersions.delete(key)
  return Number.isInteger(version) && version >= 0 ? version : null
}

export async function getInternshipReviewQueue({
  weeklyPage = 1, exceptionPage = 1, pageSize = 20, append = false
} = {}) {
  if (!append) exceptionVersions.clear()
  const query = `weeklyPage=${weeklyPage}&exceptionPage=${exceptionPage}&pageSize=${pageSize}`
  const d = await realRequest(`/mobile/teacher/internship?${query}`)
  const reports = (d.weeklyReports || []).map((r) => ({
    id: String(r.id || r.reportId || ''), student: r.studentName || r.name || '',
    className: r.className || '', week: r.weekNumber ? ('第 ' + r.weekNumber + ' 周') : (r.week || ''),
    company: r.enterpriseName || r.company || '', post: r.positionName || r.post || '',
    submitTime: r.submittedAt || r.submitTime || '—', status: r.status,
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
      time: e.exceptionDate || e.date || '', type: e.typeLabel || e.exceptionType || e.type || '异常',
      distance: e.distance || '—', note: e.note || '', status: e.status || 'PENDING_HANDLE',
      accuracy: e.accuracy || '—', address: e.address || '', deviceRisk: e.deviceRisk || '—',
      streak: e.streak || '', appealStatus: e.appealStatus || '', appealNote: e.appealNote || '',
      statusLabel: e.statusLabel || '', expectedVersion,
      decisionFactsComplete: e.decisionFactsComplete === true,
      missingDecisionFacts: Array.isArray(e.missingDecisionFacts) ? e.missingDecisionFacts : []
    }
  })
  return { reports, abnormal, pagination: d.pagination || {
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
  const url = `/teacher-mobile/internship/exceptions/${encodeURIComponent(key)}/handle`
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
