import { getTeacherGraduationBatch, realRequest, setTeacherGraduationBatch } from './request'

function parseQuery(raw = '') {
  const query = String(raw || '').replace(/^.*?\?/, '')
  if (!query || query === raw && !String(raw).includes('?')) return {}
  return query.split('&').reduce((result, part) => {
    const [key, ...rest] = part.split('=')
    if (!key) return result
    try { result[decodeURIComponent(key)] = decodeURIComponent(rest.join('=') || '') } catch { result[key] = rest.join('=') || '' }
    return result
  }, {})
}

function currentPageOptions() {
  try {
    const getPages = globalThis.getCurrentPages
    if (typeof getPages === 'function') {
      const pages = getPages()
      const page = pages && pages[pages.length - 1]
      const options = page?.options || page?.$page?.options
      if (options && Object.keys(options).length) return options
    }
    return parseQuery(globalThis.location?.hash || globalThis.location?.search || '')
  } catch {
    return {}
  }
}

function normalizeTaskContext(options = {}) {
  const route = currentPageOptions()
  return {
    batchId: String(options.batchId || route.batchId || ''),
    kind: String(options.kind || route.kind || '').toLowerCase(),
    gdStudentId: String(options.gdStudentId || route.gdStudentId || ''),
    recordId: String(options.recordId || route.recordId || ''),
    materialVersion: String(options.materialVersion || route.materialVersion || ''),
    fileVersionId: String(options.fileVersionId || route.fileVersionId || '')
  }
}

function exactQueue(rows, context, idKey) {
  if (!context.recordId && !context.gdStudentId) return rows
  return rows.filter((row) => {
    if (context.recordId && String(row[idKey] || '') !== context.recordId) return false
    if (context.gdStudentId && String(row.gdStudentId || '') !== context.gdStudentId) return false
    return true
  })
}

/**
 * 教师小程序毕业设计跨端计数真值。
 *
 * - batchId 来自显式批次或当前页面精确任务深链；
 * - proposalTotal/finalTotal 是服务端 authoritative count；
 * - 精确任务同时锁定 kind/gdStudentId/recordId/materialVersion/fileVersionId；
 * - 找不到精确任务时 fail-closed，不漂移到队列第一条；
 * - 不允许 mock 回退，也不在客户端重算 total。
 */
export async function graduationTeacherCountTruth(options = {}) {
  const context = normalizeTaskContext(options)
  if (context.batchId) {
    const selected = getTeacherGraduationBatch()
    if (String(selected?.id || '') !== context.batchId) {
      setTeacherGraduationBatch({ id: context.batchId, name: options.batchName || '', status: options.batchStatus || '' })
    }
  }

  const selected = getTeacherGraduationBatch()
  if (!selected?.id) throw { code: 422001, biz: true, message: '请先选择毕业设计批次' }
  const d = await realRequest('/mobile/teacher/graduation')
  const responseBatchId = String(d.batchId || selected.id || '')
  if (responseBatchId !== String(selected.id)) {
    throw { code: 409001, biz: true, message: '教师小程序返回的毕业设计批次与当前选择不一致，请重新进入任务' }
  }

  const list = (d.students || []).map((s) => ({
    id: String(s.id || ''), name: s.name || s.studentName || '', className: s.className || '',
    topic: s.topicTitle || s.topic || '（未选题）', node: s.stage || '毕设',
    status: s.status || 'PROCESSING', deadline: s.deadline || ''
  }))
  const proposalRows = (d.reviewDetail || [])
    .filter((p) => (p.status || 'PENDING_REVIEW') === 'PENDING_REVIEW' && /^\d+$/.test(String(p.id || '')))
    .map((p) => ({
      proposalId: String(p.id), gdStudentId: String(p.projectId || p.gdStudentId || ''),
      studentName: p.studentName || p.name || '', className: p.className || '',
      topicTitle: p.topicTitle || '', submitAt: p.submitAt || p.submittedAt || '',
      version: p.version || '', isResubmit: !!p.isResubmit
    }))
  const finalRows = (d.finalDetail || [])
    .filter((f) => (f.status || 'PENDING_REVIEW') === 'PENDING_REVIEW' && /^\d+$/.test(String(f.id || '')))
    .map((f) => ({
      finalId: String(f.id), gdStudentId: String(f.projectId || f.gdStudentId || ''),
      studentName: f.studentName || f.name || '', className: f.className || '',
      topicTitle: f.topicTitle || '', submitAt: f.submitAt || '', type: f.type || '',
      version: f.version || '', plagiarismRate: f.plagiarismRate || '—'
    }))

  const reviewQueue = context.kind === 'proposal' ? exactQueue(proposalRows, context, 'proposalId') : proposalRows
  const finalQueue = context.kind === 'final' ? exactQueue(finalRows, context, 'finalId') : finalRows
  const exactMode = Boolean(context.kind && (context.recordId || context.gdStudentId))
  const targetQueue = context.kind === 'final' ? finalQueue : context.kind === 'proposal' ? reviewQueue : null
  if (exactMode && !targetQueue?.length) {
    throw { code: 404001, biz: true, message: '指定的毕业设计待办不在当前批次或当前角色数据范围内' }
  }

  return {
    list,
    reviewQueue,
    finalQueue,
    proposalTotal: Number(d.proposalTotal || 0),
    finalTotal: Number(d.finalTotal || 0),
    batchId: responseBatchId,
    taskContext: context,
    _real: true
  }
}

export default graduationTeacherCountTruth
