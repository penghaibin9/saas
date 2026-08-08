import { realRequest } from './request'

const enc = (value) => encodeURIComponent(String(value ?? ''))

function mapReport(r) {
  return {
    id: String(r.id || r.reportId || ''),
    student: r.studentName || r.name || '',
    className: r.className || '',
    week: r.week || (r.weekNumber ? `第 ${r.weekNumber} 周` : ''),
    company: r.enterpriseName || r.company || '',
    post: r.positionName || r.post || '',
    submitTime: r.submitAt || r.submittedAt || r.submitTime || '—',
    status: r.status,
    statusLabel: r.statusLabel || '',
    version: Number(r.version ?? 0),
    reportVersion: r.reportVersion || '',
    isResubmit: !!r.isResubmit,
    wordCount: Number(r.wordCount || 0),
    riskFlag: r.riskFlag || '',
    overdue: r.status === 'OVERDUE',
    tasks: r.workContent || '',
    gain: r.harvestContent || '',
    problem: r.planContent || ''
  }
}

function mapException(e) {
  return {
    id: String(e.id || ''),
    student: e.studentName || e.name || '',
    time: e.exceptionDate || e.date || '',
    type: e.exceptionType || e.type || e.typeLabel || '异常',
    distance: e.distance || '—',
    note: e.note || e.studentNote || '',
    status: e.status || 'PENDING_HANDLE',
    statusLabel: e.statusLabel || ''
  }
}

/**
 * 教师周报批阅工作区：先读取权威实习上下文，再显式锁定当前批次。
 * 后端禁止无 batchId 静默扫全历史，所以这里不能再直接 GET /mobile/teacher/internship。
 */
export async function loadWeeklyReviewQueue() {
  const context = await realRequest('/mobile/teacher/internship/context')
  const batchId = String((context && context.defaultBatchId) || '').trim()
  if (!batchId) {
    return {
      reports: [], abnormal: [], batchId: '', batches: (context && context.batches) || [],
      _real: true
    }
  }
  const data = await realRequest(`/mobile/teacher/internship?batchId=${enc(batchId)}`)
  return {
    reports: ((data && data.weeklyReports) || []).map(mapReport),
    abnormal: ((data && data.abnormalCheckins) || []).map(mapException),
    batchId,
    batches: (context && context.batches) || [],
    _real: true
  }
}

/** 列表看到的 version 必须原样提交，服务端才能拒绝 stale-client 并发覆盖。 */
export const reviewWeeklyVersioned = (reportId, action, comment, expectedVersion) =>
  realRequest(`/mobile/teacher/internship/weekly/${enc(reportId)}/review`, {
    method: 'POST',
    data: { action, comment: comment || '', expectedVersion }
  })
