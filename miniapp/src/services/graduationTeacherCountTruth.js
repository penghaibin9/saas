import { getTeacherGraduationBatch, realRequest, setTeacherGraduationBatch } from './request'

const DEFAULT_PAGE_SIZE = 20

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
  const rawRecordId = String(options.recordId || options.proposalId || options.finalId || route.recordId || route.proposalId || route.finalId || '')
  return {
    batchId: String(options.batchId || route.batchId || ''),
    kind: String(options.kind || route.kind || '').toLowerCase(),
    gdStudentId: String(options.gdStudentId || route.gdStudentId || ''),
    recordId: /^\d+$/.test(rawRecordId) ? rawRecordId : '',
    materialVersion: String(options.materialVersion || route.materialVersion || ''),
    fileVersionId: String(options.fileVersionId || route.fileVersionId || '')
  }
}

function pageNumber(value, fallback = 1) {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

function pageSize(value) {
  return Math.min(100, Math.max(1, pageNumber(value, DEFAULT_PAGE_SIZE)))
}

function workbenchPath(options = {}) {
  const size = pageSize(options.pageSize)
  const query = [
    ['page', pageNumber(options.page)],
    ['pageSize', size],
    ['studentPage', pageNumber(options.studentPage)],
    ['proposalPage', pageNumber(options.proposalPage)],
    ['finalPage', pageNumber(options.finalPage)]
  ]
  return `/mobile/teacher/graduation?${query.map(([key, value]) => `${key}=${encodeURIComponent(value)}`).join('&')}`
}

function exactQueue(rows, context, idKey) {
  if (!context.recordId && !context.gdStudentId) return rows
  return rows.filter((row) => {
    if (context.recordId && String(row[idKey] || '') !== context.recordId) return false
    if (context.gdStudentId && String(row.gdStudentId || '') !== context.gdStudentId) return false
    return true
  })
}

function proposalRow(detail = {}) {
  return {
    proposalId: String(detail.id || ''), gdStudentId: String(detail.gdStudentId || detail.projectId || ''),
    studentName: detail.studentName || detail.name || '', className: detail.className || '',
    topicTitle: detail.topicTitle || '', submitAt: detail.submitAt || detail.submittedAt || '',
    version: detail.version || '', isResubmit: !!detail.isResubmit
  }
}

function finalRow(detail = {}) {
  return {
    finalId: String(detail.id || ''), gdStudentId: String(detail.gdStudentId || detail.projectId || ''),
    studentName: detail.studentName || detail.name || '', className: detail.className || '',
    topicTitle: detail.topicTitle || '', submitAt: detail.submitAt || detail.submittedAt || '',
    type: detail.type || '', version: detail.version || '', plagiarismRate: detail.plagiarismRate || '—'
  }
}

async function resolveExactPendingRow(kind, rows, context) {
  if (context.kind !== kind || !context.recordId) return rows
  const idKey = kind === 'proposal' ? 'proposalId' : 'finalId'
  const focused = exactQueue(rows, context, idKey)
  if (focused.length) return focused

  // 深链中的对象可能在第 2 页以后。直接读取受 batch + teacher scope 保护的详情，
  // 而不是为了找一条记录把所有待办页下载到手机。
  const path = kind === 'proposal'
    ? `/mobile/teacher/graduation/proposal/${encodeURIComponent(context.recordId)}`
    : `/mobile/teacher/graduation/final/${encodeURIComponent(context.recordId)}`
  const detail = await realRequest(path)
  if (!detail || String(detail.id || '') !== context.recordId || String(detail.status || '') !== 'PENDING_REVIEW') {
    throw { code: 409001, biz: true, message: '该毕业设计待办已处理或状态已变化，请返回工作台刷新' }
  }
  if (context.gdStudentId && String(detail.gdStudentId || detail.projectId || '') !== context.gdStudentId) {
    throw { code: 404001, biz: true, message: '指定毕业设计待办与学生信息不一致，已拒绝打开' }
  }
  return [kind === 'proposal' ? proposalRow(detail) : finalRow(detail)]
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
  const d = await realRequest(workbenchPath(options))
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

  const reviewQueue = await resolveExactPendingRow('proposal', proposalRows, context)
  const finalQueue = await resolveExactPendingRow('final', finalRows, context)
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
    studentPage: Number(d.studentPage || 1), studentTotal: Number(d.studentTotal || list.length),
    studentHasMore: !!d.studentHasMore,
    proposalPage: Number(d.proposalPage || 1), proposalHasMore: !!d.proposalHasMore,
    finalPage: Number(d.finalPage || 1), finalHasMore: !!d.finalHasMore,
    pageSize: Number(d.pageSize || DEFAULT_PAGE_SIZE),
    batchId: responseBatchId,
    taskContext: context,
    _real: true
  }
}

export default graduationTeacherCountTruth
