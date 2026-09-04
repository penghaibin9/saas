import { getTeacherGraduationBatch, realRequest, setTeacherGraduationBatch } from './request'

function normalizeTaskContext(options = {}) {
  return {
    batchId: String(options.batchId || ''),
    kind: String(options.kind || '').toLowerCase(),
    gdStudentId: String(options.gdStudentId || ''),
    recordId: String(options.recordId || '')
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
 * - batchId 必须来自当前显式批次或精确任务深链；
 * - queue 只承载服务端当前页可操作记录；
 * - proposalTotal/finalTotal 是服务端 authoritative count；
 * - 精确任务模式同时锁定 kind + gdStudentId + recordId，找不到时 fail-closed；
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

  const reviewQueue = context.kind === 'final' ? proposalRows : exactQueue(proposalRows, context, 'proposalId')
  const finalQueue = context.kind === 'proposal' ? finalRows : exactQueue(finalRows, context, 'finalId')
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
