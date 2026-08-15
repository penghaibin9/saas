import { realRequest } from './request'

/**
 * U12 · 教师小程序毕业设计跨端计数真值。
 *
 * 只消费 batch-aware /mobile/teacher/graduation 的同一份服务端响应：
 * - queue 只承载当前页可操作记录；
 * - proposalTotal/finalTotal 才是服务端 authoritative count；
 * - batchId 由 request.js 的 withTeacherGraduationContext() 从既有批次上下文注入。
 *
 * 不允许 mock 回退，也不在客户端重算 total。
 */
export async function graduationTeacherCountTruth() {
  const d = await realRequest('/mobile/teacher/graduation')
  const list = (d.students || []).map((s) => ({
    id: String(s.id || ''), name: s.name || s.studentName || '', className: s.className || '',
    topic: s.topicTitle || s.topic || '（未选题）', node: s.stage || '毕设',
    status: s.status || 'PROCESSING', deadline: s.deadline || ''
  }))
  const reviewQueue = (d.reviewDetail || [])
    .filter((p) => (p.status || 'PENDING_REVIEW') === 'PENDING_REVIEW' && /^\d+$/.test(String(p.id || '')))
    .map((p) => ({
      proposalId: String(p.id), gdStudentId: String(p.projectId || p.gdStudentId || ''),
      studentName: p.studentName || p.name || '', className: p.className || '',
      topicTitle: p.topicTitle || '', submitAt: p.submitAt || p.submittedAt || '',
      version: p.version || '', isResubmit: !!p.isResubmit
    }))
  const finalQueue = (d.finalDetail || [])
    .filter((f) => (f.status || 'PENDING_REVIEW') === 'PENDING_REVIEW' && /^\d+$/.test(String(f.id || '')))
    .map((f) => ({
      finalId: String(f.id), gdStudentId: String(f.projectId || f.gdStudentId || ''),
      studentName: f.studentName || f.name || '', className: f.className || '',
      topicTitle: f.topicTitle || '', submitAt: f.submitAt || '', type: f.type || '',
      version: f.version || '', plagiarismRate: f.plagiarismRate || '—'
    }))
  return {
    list,
    reviewQueue,
    finalQueue,
    proposalTotal: Number(d.proposalTotal || 0),
    finalTotal: Number(d.finalTotal || 0),
    batchId: String(d.batchId || ''),
    _real: true
  }
}

export default graduationTeacherCountTruth
