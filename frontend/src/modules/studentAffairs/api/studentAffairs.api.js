/**
 * 13A 学工中心 API（生产级：真实对接 /api/v1/student-affairs/*，业务数据不回退 mock）。
 *
 * 本轮范围 = 学工首页（dashboard 三角色视图 + 9 统计卡 + 13 模块卡）。
 * 契约：所有方法返回 Promise<{ code, data, message }>，code=0 成功；业务错误透出后端 message。
 * 后端已就绪（backend/app/api/v1/student_affairs.py），数据全部真实按数据范围聚合。
 */
import { request } from '@/services/http/client'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function toErr(e) {
  // e.biz=true 表示后端返回的业务错误码（403/409/422 等），透出其 message；否则归为接口不可用。
  if (e?.biz) return { code: e.code || 1, data: null, message: e.message }
  return { code: e?.code || 503001, data: null, message: e?.message || '真实接口不可用' }
}

async function callStrict(fn) {
  try {
    return { code: 0, data: await fn(), message: 'ok' }
  } catch (e) {
    return toErr(e)
  }
}

/**
 * 门户壳兜底品牌（仅当共享端点 /tenant/brand 不可达时使用，保证布局壳不崩）。
 * 非业务假数据：学生数/待办等真实指标一律来自 dashboard 后端。
 */
const FALLBACK_BRAND = {
  schoolName: '学工中心',
  platformDisplayName: '高校学生全生命周期管理平台',
  watermarkText: ''
}

export const studentAffairsApi = {
  /**
   * 门户上下文：品牌 + 当前角色 + 数据范围，全部来自真实共享端点
   * （/tenant/brand、/rbac/current-context）。任一端点不可达时静默回退，
   * 保证学工首页壳可渲染；三角色视图与统计仍由 dashboard 后端按登录身份裁定。
   */
  async getContext() {
    let brand = { ...FALLBACK_BRAND }
    let currentRole = { roleCode: '', roleName: '', userName: '' }
    let dataScope = { scopeName: '' }
    try {
      const b = await request('/tenant/brand')
      brand = {
        ...brand,
        ...b,
        schoolName: b.schoolName || brand.schoolName,
        platformDisplayName: b.platformDisplayName || brand.platformDisplayName
      }
    } catch {
      /* 离线/未登录静默回退品牌兜底 */
    }
    try {
      const ctx = await request('/rbac/current-context')
      if (ctx.currentRole) currentRole = { ...currentRole, ...ctx.currentRole }
      if (ctx.dataScope) {
        dataScope = {
          ...dataScope,
          ...ctx.dataScope,
          scopeName: ctx.dataScope.scopeName || ctx.dataScope.scopeLabel || ''
        }
      }
    } catch {
      /* 静默回退，dashboard 仍会返回真实 viewLabel/scopeMode */
    }
    return ok({ tenantBrandConfig: brand, currentRole, dataScope })
  },

  /**
   * 学工首页：三角色视图（学工处/学院学工/辅导员）+ 9 张统计卡 + 13 张业务模块卡。
   * 真实聚合、按数据范围过滤；返回体形如
   * { view, viewLabel, scopeMode, updatedAt, summaryCards:[{key,label,value,unit}], moduleCards:[{key,label,status,empty,emptyHint}] }
   */
  getDashboard() {
    return callStrict(() => request('/student-affairs/dashboard'))
  },

  // ─────────────── 班级（供选择器/代录用） ───────────────

  /** 班级列表（按数据范围）。 */
  getClasses() {
    return callStrict(() => request('/student-affairs/classes'))
  },

  /** 班干部列表（某班级）。 */
  getClassCadres(classId) {
    return callStrict(() => request(`/student-affairs/classes/${classId}/cadres`))
  },

  /** 任命班干部。body: { studentId, position, termCode? }（同班同职务在任 → 409）。 */
  appointCadre(classId, body) {
    return callStrict(() => request(`/student-affairs/classes/${classId}/cadres`, { method: 'POST', body }))
  },

  /** 免去班干部。 */
  dismissCadre(cadreId) {
    return callStrict(() => request(`/student-affairs/classes/cadres/${cadreId}`, { method: 'DELETE' }))
  },

  /**
   * 学生搜索（供 AppStudentPicker remoteSearch 注入）：真实 /students 端点，按数据范围返回。
   * 返回 [{ label, value, desc }]，label=姓名+学号，value=学生 id。
   */
  async searchStudents(keyword) {
    const d = await request('/students', { params: { keyword, page: 1, pageSize: 20 } })
    return (d.items || []).map((s) => ({
      value: String(s.id),
      label: `${s.realName}（${s.studentNo}）`,
      desc: s.className || s.grade || ''
    }))
  },

  // ─────────────── 请假闭环（P3 · /student-affairs/leave/*） ───────────────

  /** 待审批请假队列（按数据范围；仅返回三个审批节点态）。 */
  getPendingLeaves({ page = 1, pageSize = 50 } = {}) {
    return callStrict(() => request('/student-affairs/leave/pending', { params: { page, pageSize } }))
  },

  /** 请假详情（任意状态可查，供动作后刷新详情面板）。 */
  getLeaveDetail(id) {
    return callStrict(() => request(`/student-affairs/leave/${id}`))
  },

  /** 代录请假（教师代学生发起）。body: { studentId, leaveType, startTime, endTime, reason } */
  applyLeave(body) {
    return callStrict(() => request('/student-affairs/leave', { method: 'POST', body }))
  },

  /** 审批通过（多级逐节点推进；comment 可选）。 */
  approveLeave(id, comment = '') {
    return callStrict(() => request(`/student-affairs/leave/${id}/approve`, { method: 'POST', body: { comment } }))
  },

  /** 驳回（终态，原因≥5字）。 */
  rejectLeave(id, reason) {
    return callStrict(() => request(`/student-affairs/leave/${id}/reject`, { method: 'POST', body: { reason } }))
  },

  /** 退回重提（原因≥5字）。 */
  returnLeave(id, reason) {
    return callStrict(() => request(`/student-affairs/leave/${id}/return`, { method: 'POST', body: { reason } }))
  },

  /** 退回后重新提交。 */
  resubmitLeave(id) {
    return callStrict(() => request(`/student-affairs/leave/${id}/resubmit`, { method: 'POST', body: {} }))
  },

  /** 发起销假（APPROVED/OVERDUE 可发起）。 */
  cancelLeave(id, proofNote = '') {
    return callStrict(() => request(`/student-affairs/leave/${id}/cancel`, { method: 'POST', body: { proofNote } }))
  },

  /** 销假确认（辅导员）→ CLOSED 进 360。 */
  confirmCancelLeave(id, note = '') {
    return callStrict(() => request(`/student-affairs/leave/${id}/cancel-confirm`, { method: 'POST', body: { note } }))
  },

  /** 发起续假（newEnd 必须晚于原结束）。 */
  extendLeave(id, newEnd, reason = '') {
    return callStrict(() => request(`/student-affairs/leave/${id}/extension`, { method: 'POST', body: { newEnd, reason } }))
  },

  /** 续假审批通过。 */
  approveExtension(id) {
    return callStrict(() => request(`/student-affairs/leave/${id}/extension-approve`, { method: 'POST', body: {} }))
  },

  /** 逾期扫描（幂等，返回 { count }）。 */
  scanOverdueLeaves() {
    return callStrict(() => request('/student-affairs/leave/scan-overdue', { method: 'POST', body: {} }))
  },

  // ─────────────── 风险预警（P5 · /student-affairs/risk/*） ───────────────

  /** 风险列表（服务端支持 source/status/riskLevel 过滤；心理来源明细按角色脱敏）。 */
  getRisks({ source = '', status = '', riskLevel = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (source) params.source = source
    if (status) params.status = status
    if (riskLevel) params.riskLevel = riskLevel
    return callStrict(() => request('/student-affairs/risk/records', { params }))
  },

  /** 风险详情。 */
  getRiskDetail(id) {
    return callStrict(() => request(`/student-affairs/risk/records/${id}`))
  },

  /** 建风险单。body: { studentId, source, riskLevel, title, detail, sourceRefId? }（同来源单据去重 409）。 */
  createRisk(body) {
    return callStrict(() => request('/student-affairs/risk/records', { method: 'POST', body }))
  },

  /** 分派责任人（NEW/REOPENED/TRANSFERRED → ASSIGNED）。 */
  assignRisk(id, ownerId) {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/assign`, { method: 'POST', body: { ownerId: String(ownerId) } }))
  },

  /** 处置（内容≥5字；ASSIGNED/PROCESSING → PROCESSING）。 */
  processRisk(id, content) {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/process`, { method: 'POST', body: { content } }))
  },

  /** 转持续跟进（PROCESSING/FOLLOWING → FOLLOWING）。 */
  followRisk(id, content = '') {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/follow`, { method: 'POST', body: { content } }))
  },

  /** 转办（换责任人；PROCESSING/FOLLOWING → ASSIGNED）。 */
  transferRisk(id, newOwnerId, reason = '') {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/transfer`, { method: 'POST', body: { newOwnerId: String(newOwnerId), reason } }))
  },

  /** 升级（等级+1；PROCESSING/FOLLOWING → ESCALATED）。 */
  escalateRisk(id, reason = '') {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/escalate`, { method: 'POST', body: { reason } }))
  },

  /** 上级接管（ESCALATED → PROCESSING）。 */
  takeoverRisk(id, content = '') {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/takeover`, { method: 'POST', body: { content } }))
  },

  /** 关闭（结论≥5字，需≥1条处置记录；→ CLOSED 进360）。 */
  closeRisk(id, conclusion) {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/close`, { method: 'POST', body: { conclusion } }))
  },

  /** 复发重开（CLOSED → REOPENED）。 */
  reopenRisk(id, reason = '') {
    return callStrict(() => request(`/student-affairs/risk/records/${id}/reopen`, { method: 'POST', body: { reason } }))
  },

  /** 风险超时扫描（幂等，返回 { escalated, assigned }）。 */
  scanRiskTimeout() {
    return callStrict(() => request('/student-affairs/risk/scan-timeout', { method: 'POST', body: {} }))
  },

  // ─────────────── 违纪处分（P5 · /student-affairs/discipline/*） ───────────────

  /** 处分列表（服务端支持 status/discType 过滤）。 */
  getDisciplineCases({ status = '', discType = '', page = 1, pageSize = 200 } = {}) {
    const params = { page, pageSize }
    if (status) params.status = status
    if (discType) params.discType = discType
    return callStrict(() => request('/student-affairs/discipline/cases', { params }))
  },

  /** 处分详情。 */
  getDisciplineDetail(id) {
    return callStrict(() => request(`/student-affairs/discipline/cases/${id}`))
  },

  /** 投影一致性对账（EFFECTIVE case 数 == ACTIVE 投影行数）。 */
  reconcileDiscipline() {
    return callStrict(() => request('/student-affairs/discipline/reconcile'))
  },

  /** 登记违纪处分。body: { studentId, discType, reason(≥5), docNo? } */
  registerDiscipline(body) {
    return callStrict(() => request('/student-affairs/discipline/cases', { method: 'POST', body }))
  },

  /** 提交学院初审（REGISTERED/RETURNED → COLLEGE_REVIEW）。 */
  submitDiscipline(id) {
    return callStrict(() => request(`/student-affairs/discipline/cases/${id}/submit`, { method: 'POST', body: {} }))
  },

  /** 撤销登记（REGISTERED/RETURNED → CANCELLED）。 */
  cancelDiscipline(id) {
    return callStrict(() => request(`/student-affairs/discipline/cases/${id}/cancel`, { method: 'POST', body: {} }))
  },

  /** 处分审批。action: APPROVE / REJECT / RETURN（REJECT/RETURN 原因≥5字）。 */
  reviewDiscipline(id, action, reason = '') {
    return callStrict(() => request(`/student-affairs/discipline/cases/${id}/review`, { method: 'POST', body: { action, reason } }))
  },

  /** 发起处分解除（EFFECTIVE → REMOVE_REVIEW；理由≥5字）。 */
  submitRemoveDiscipline(id, reason) {
    return callStrict(() => request(`/student-affairs/discipline/cases/${id}/remove`, { method: 'POST', body: { reason } }))
  },

  /** 处分解除审批（辅→院→处三节点）。action: APPROVE / REJECT（REJECT 原因≥5字）。 */
  reviewRemoveDiscipline(id, action, reason = '') {
    return callStrict(() => request(`/student-affairs/discipline/cases/${id}/remove-review`, { method: 'POST', body: { action, reason } }))
  },

  // ─────────────── 困难认定（P4 · /student-affairs/aid/*，含强敏感家庭经济） ───────────────

  /** 认定批次列表。 */
  getAidBatches({ schoolYear = '', status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (schoolYear) params.schoolYear = schoolYear
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/aid/batches', { params }))
  },

  /** 建/发布认定批次。body: { batchName, schoolYear, applyStart?, applyEnd?, publicityDays?, publish } */
  createAidBatch(body) {
    return callStrict(() => request('/student-affairs/aid/batches', { method: 'POST', body }))
  },

  /** 认定申请列表（家庭经济默认脱敏）。 */
  getAidApplications({ batchId = '', status = '', level = '', page = 1, pageSize = 200 } = {}) {
    const params = { page, pageSize }
    if (batchId) params.batchId = batchId
    if (status) params.status = status
    if (level) params.level = level
    return callStrict(() => request('/student-affairs/aid/applications', { params }))
  },

  /** 受理困难认定申请（直达班级评议）。body 含 batchId/studentId/applyLevel/statement(10-500)/家庭经济。 */
  applyAid(body) {
    return callStrict(() => request('/student-affairs/aid/applications', { method: 'POST', body }))
  },

  /** 认定申请详情（家庭经济脱敏）。 */
  getAidDetail(id) {
    return callStrict(() => request(`/student-affairs/aid/applications/${id}`))
  },

  /** 各级评审。action: APPROVE / REJECT / RETURN；level 用于初审建议/终审核定等级。 */
  reviewAid(id, action, level = null, reason = '') {
    const body = { action, reason }
    if (level) body.level = level
    return callStrict(() => request(`/student-affairs/aid/applications/${id}/review`, { method: 'POST', body }))
  },

  /** 退回后重新提交。 */
  resubmitAid(id) {
    return callStrict(() => request(`/student-affairs/aid/applications/${id}/resubmit`, { method: 'POST', body: {} }))
  },

  /** 人工确认公示期满 → 通过（进困难库 + 360）。 */
  confirmAidPublicity(id) {
    return callStrict(() => request(`/student-affairs/aid/applications/${id}/publicity-confirm`, { method: 'POST', body: {} }))
  },

  /** 公示期满扫描（幂等，返回 { count }）。 */
  scanAidPublicity() {
    return callStrict(() => request('/student-affairs/aid/scan-publicity', { method: 'POST', body: {} }))
  },

  /** 发起困难等级动态调整（仅 APPROVED；原因≥5字）。 */
  adjustAid(id, targetLevel, reason) {
    return callStrict(() => request(`/student-affairs/aid/applications/${id}/adjust`, { method: 'POST', body: { targetLevel, reason } }))
  },

  /** 动态调整审批。action: APPROVE / REJECT。 */
  approveAidAdjust(id, action = 'APPROVE') {
    return callStrict(() => request(`/student-affairs/aid/applications/${id}/adjust-approve`, { method: 'POST', body: { action } }))
  },

  /**
   * 查看完整家庭经济（强敏感）：sensitiveView 鉴权 + 强制 SENSITIVE 审计。
   * 非授权角色返回 403；reason 落审计。返回 { familyEconomy: { annualIncome, debt, familyMembers, ... } }。
   */
  revealAidFamily(id, reason = '') {
    return callStrict(() => request(`/student-affairs/aid/applications/${id}/reveal`, { method: 'POST', body: { reason } }))
  },

  /** 对公示中申请提异议（理由≥5字）。body: { reason, objectorName? } */
  submitAidObjection(applyId, body) {
    return callStrict(() => request(`/student-affairs/aid/applications/${applyId}/objection`, { method: 'POST', body }))
  },
  /** 学工统计驾驶舱（各域概览+下钻）。 */
  getStatsCockpit() {
    return callStrict(() => request('/student-affairs/stats/cockpit'))
  },

  // ─────────────── 辅导员考评（D 包 · /counselor-eval） ───────────────
  getEvalIndicators() {
    return callStrict(() => request('/student-affairs/counselor-eval/indicators'))
  },
  /** 建指标。body: { name, category?, weight?, maxScore?, sortOrder? } */
  createEvalIndicator(body) {
    return callStrict(() => request('/student-affairs/counselor-eval/indicators', { method: 'POST', body }))
  },
  getCounselorEvals({ periodCode = '', status = '', page = 1, pageSize = 200 } = {}) {
    const params = { page, pageSize }
    if (periodCode) params.periodCode = periodCode
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/counselor-eval/evals', { params }))
  },
  /** 录/改评分。body: { periodCode, counselorKey, counselorName?, scores, remark? } */
  upsertCounselorEval(body) {
    return callStrict(() => request('/student-affairs/counselor-eval/evals', { method: 'POST', body }))
  },
  publishCounselorEval(evalId) {
    return callStrict(() => request(`/student-affairs/counselor-eval/evals/${evalId}/publish`, { method: 'POST', body: {} }))
  },
  /** 考评申诉复核。body: { result, opinion, scores? } */
  reviewEvalAppeal(evalId, body) {
    return callStrict(() => request(`/student-affairs/counselor-eval/evals/${evalId}/appeal-review`, { method: 'POST', body }))
  },
  /** 困难认定异议列表。 */
  getAidObjections({ status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/aid/objections', { params }))
  },
  /** 异议复核。result: SUSTAINED/OVERRULED；opinion≥5。 */
  reviewAidObjection(objectionId, result, opinion) {
    return callStrict(() => request(`/student-affairs/aid/objections/${objectionId}/review`, { method: 'POST', body: { result, opinion } }))
  },

  /** 困难学生库（APPROVED 最新等级聚合）。 */
  getDifficultStudents({ level = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (level) params.level = level
    return callStrict(() => request('/student-affairs/aid/difficult-students', { params }))
  },

  /** 困难认定统计（按状态/等级聚合）。 */
  getAidStats() {
    return callStrict(() => request('/student-affairs/aid/stats'))
  },

  /** 奖助统计（按状态/项目类型聚合，计数口径）。 */
  getFundingStats() {
    return callStrict(() => request('/student-affairs/funding/stats'))
  },
  /** 资助发放台账（金额脱敏，不含卡全号）。 */
  getFundingDisbursements({ batchId = '', bankStatus = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (batchId) params.batchId = batchId
    if (bankStatus) params.bankStatus = bankStatus
    return callStrict(() => request('/student-affairs/funding/disbursements', { params }))
  },
  /** 按批次生成发放台账（GRANTED→PENDING，幂等）。 */
  generateDisbursements(batchId) {
    return callStrict(() => request(`/student-affairs/funding/batches/${batchId}/disbursements/generate`, { method: 'POST', body: {} }))
  },
  /** 标记已发放。body: { disburseNo?, bankLast4? } */
  issueDisbursement(id, body = {}) {
    return callStrict(() => request(`/student-affairs/funding/disbursements/${id}/issue`, { method: 'POST', body }))
  },
  /** 标记发放失败（原因≥5字）。 */
  failDisbursement(id, reason) {
    return callStrict(() => request(`/student-affairs/funding/disbursements/${id}/fail`, { method: 'POST', body: { reason } }))
  },
  /** 发放概览。 */
  getDisbursementStats() {
    return callStrict(() => request('/student-affairs/funding/disbursements/stats'))
  },

  // ─────────────── 奖助扩展：勤工/贷款/减免（/work-study /loans /fee-reductions） ───────────────
  getWorkStudyPosts({ status = '' } = {}) {
    const params = {}; if (status) params.status = status
    return callStrict(() => request('/student-affairs/work-study/posts', { params }))
  },
  createWorkStudyPost(body) {
    return callStrict(() => request('/student-affairs/work-study/posts', { method: 'POST', body }))
  },
  getWorkStudyRecords({ postId = '', status = '' } = {}) {
    const params = {}; if (postId) params.postId = postId; if (status) params.status = status
    return callStrict(() => request('/student-affairs/work-study/records', { params }))
  },
  applyWorkStudy(postId, studentId) {
    return callStrict(() => request(`/student-affairs/work-study/posts/${postId}/apply`, { method: 'POST', body: { studentId } }))
  },
  actWorkStudy(recordId, action, reason = '') {
    return callStrict(() => request(`/student-affairs/work-study/records/${recordId}/action`, { method: 'POST', body: { action, reason } }))
  },
  getLoans({ status = '' } = {}) {
    const params = {}; if (status) params.status = status
    return callStrict(() => request('/student-affairs/loans', { params }))
  },
  registerLoan(body) {
    return callStrict(() => request('/student-affairs/loans', { method: 'POST', body }))
  },
  advanceLoan(loanId) {
    return callStrict(() => request(`/student-affairs/loans/${loanId}/advance`, { method: 'POST', body: {} }))
  },
  getFeeReductions({ itemType = '', status = '' } = {}) {
    const params = {}; if (itemType) params.itemType = itemType; if (status) params.status = status
    return callStrict(() => request('/student-affairs/fee-reductions', { params }))
  },
  submitFeeReduction(body) {
    return callStrict(() => request('/student-affairs/fee-reductions', { method: 'POST', body }))
  },
  reviewFeeReduction(feeId, action, opinion = '') {
    return callStrict(() => request(`/student-affairs/fee-reductions/${feeId}/review`, { method: 'POST', body: { action, opinion } }))
  },
  issueFeeReduction(feeId) {
    return callStrict(() => request(`/student-affairs/fee-reductions/${feeId}/issue`, { method: 'POST', body: {} }))
  },

  /** 违纪处分统计（按类型/状态聚合 + 投影对账）。 */
  getDisciplineStats() {
    return callStrict(() => request('/student-affairs/discipline/stats'))
  },
  /** 登记决定书送达（仅已生效）。body: { method, remark? } */
  deliverDiscipline(caseId, body) {
    return callStrict(() => request(`/student-affairs/discipline/cases/${caseId}/deliver`, { method: 'POST', body }))
  },
  /** 提起处分申诉（已生效后，理由≥5）。 */
  submitDisciplineAppeal(caseId, reason) {
    return callStrict(() => request(`/student-affairs/discipline/cases/${caseId}/appeal`, { method: 'POST', body: { reason } }))
  },
  /** 处分申诉列表。 */
  getDisciplineAppeals({ status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/discipline/appeals', { params }))
  },
  /** 申诉复核。result: UPHELD/REVISED/REVOKED；opinion≥5。 */
  reviewDisciplineAppeal(appealId, result, opinion) {
    return callStrict(() => request(`/student-affairs/discipline/appeals/${appealId}/review`, { method: 'POST', body: { result, opinion } }))
  },

  // ─────────────── 谈心谈话（P6 · /student-affairs/talks/*） ───────────────

  /** 谈话列表（心理类明细按角色脱敏；服务端 talkType/status/studentId 过滤）。 */
  getTalks({ talkType = '', status = '', studentId = '', page = 1, pageSize = 200 } = {}) {
    const params = { page, pageSize }
    if (talkType) params.talkType = talkType
    if (status) params.status = status
    if (studentId) params.studentId = studentId
    return callStrict(() => request('/student-affairs/talks', { params }))
  },

  /** 建谈话计划（批量圈定学生，每生一条）。body: { studentIds[], talkType, topic, scheduledAt? }。返回 { planId, talkIds }。 */
  createTalk(body) {
    return callStrict(() => request('/student-affairs/talks', { method: 'POST', body }))
  },

  /** 谈话详情。 */
  getTalkDetail(id) {
    return callStrict(() => request(`/student-affairs/talks/${id}`))
  },

  /** 填写谈话记录（内容≥20字；needFollowUp=true→跟进中，否则已谈话；进360）。 */
  recordTalk(id, content, result = '', needFollowUp = false) {
    return callStrict(() => request(`/student-affairs/talks/${id}/record`, { method: 'POST', body: { content, result, needFollowUp } }))
  },

  /** 跟进/办结/转风险/转家校。action: FOLLOW / CLOSE / TO_RISK / TO_HOME_SCHOOL。 */
  followUpTalk(id, action, content = '') {
    return callStrict(() => request(`/student-affairs/talks/${id}/follow-up`, { method: 'POST', body: { action, content } }))
  },

  /** 谈话工作量统计（完成率）。 */
  getTalkStats(groupBy = 'TYPE') {
    return callStrict(() => request('/student-affairs/talks/stats', { params: { groupBy } }))
  },

  // ─────────────── 学生画像 360（P6 · /student-affairs/students/{id}/*） ───────────────

  /** 学工画像（各域沉淀汇总：请假/困难认定/奖助/处分/风险/心理/谈话）。处分/心理按角色权限。 */
  getStudentProfile(studentId) {
    return callStrict(() => request(`/student-affairs/students/${studentId}/profile`))
  },

  /** 成长时间线（360，各域进360事件倒序）。eventType 按 module 过滤（leave/aid/funding/discipline/risk/talk）。 */
  getStudentTimeline(studentId, { eventType = '', page = 1, pageSize = 50 } = {}) {
    const params = { page, pageSize }
    if (eventType) params.eventType = eventType
    return callStrict(() => request(`/student-affairs/students/${studentId}/timeline`, { params }))
  },

  // ─────────────── 奖助管理（P4 · /student-affairs/funding/*，含资格硬校验） ───────────────

  /** 资助项目列表（SCHOLARSHIP 奖学金 / GRANT 助学金）。 */
  getFundingProjects({ projectType = '', status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (projectType) params.projectType = projectType
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/funding/projects', { params }))
  },

  /** 建资助项目。body: { projectName, projectType, amount?, quota? } */
  createFundingProject(body) {
    return callStrict(() => request('/student-affairs/funding/projects', { method: 'POST', body }))
  },

  /** 资助批次列表。 */
  getFundingBatches({ projectId = '', status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (projectId) params.projectId = projectId
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/funding/batches', { params }))
  },

  /** 建/发布资助批次。body: { projectId, schoolYear, publicityDays?, quota?, publish } */
  createFundingBatch(body) {
    return callStrict(() => request('/student-affairs/funding/batches', { method: 'POST', body }))
  },

  /** 资助申请列表（金额按角色脱敏）。 */
  getFundingApplications({ batchId = '', projectType = '', status = '', page = 1, pageSize = 200 } = {}) {
    const params = { page, pageSize }
    if (batchId) params.batchId = batchId
    if (projectType) params.projectType = projectType
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/funding/applications', { params }))
  },

  /**
   * 发起资助申请（含资格硬校验：助学金需在困难库，奖学金需学籍正常/无未解除处分/无挂科）。
   * 资格不通过后端 409 拦截并透出原因。body: { batchId, studentId, applySource?, amount?, statement? }。
   */
  applyFunding(body) {
    return callStrict(() => request('/student-affairs/funding/applications', { method: 'POST', body }))
  },

  /** 资助申请详情（含资格校验快照）。 */
  getFundingDetail(id) {
    return callStrict(() => request(`/student-affairs/funding/applications/${id}`))
  },

  /** 各级评审。action: APPROVE / REJECT / RETURN（REJECT/RETURN 原因≥5字）。 */
  reviewFunding(id, action, reason = '') {
    return callStrict(() => request(`/student-affairs/funding/applications/${id}/review`, { method: 'POST', body: { action, reason } }))
  },

  /** 确认公示期满 → 获资助（进360）。 */
  confirmFundingPublicity(id) {
    return callStrict(() => request(`/student-affairs/funding/applications/${id}/publicity-confirm`, { method: 'POST', body: {} }))
  },

  /** 资助公示扫描（幂等）。 */
  scanFundingPublicity() {
    return callStrict(() => request('/student-affairs/funding/scan-publicity', { method: 'POST', body: {} }))
  },

  // ─────────────── 家校联系（P6 · /student-affairs/students/{id}/family-contacts） ───────────────

  /** 家校联系记录列表（append-only）。 */
  getFamilyContacts(studentId, { page = 1, pageSize = 100 } = {}) {
    return callStrict(() => request(`/student-affairs/students/${studentId}/family-contacts`, { params: { page, pageSize } }))
  },

  /**
   * 登记家校联系。body: { contactType PHONE/WECHAT/VISIT/MESSAGE, reason, result, fullPhoneView, viewReason }。
   * 查看完整号码(fullPhoneView=true)需 viewReason≥5字，后端落 SENSITIVE 审计。
   */
  createFamilyContact(studentId, body) {
    return callStrict(() => request(`/student-affairs/students/${studentId}/family-contacts`, { method: 'POST', body }))
  },
  /** 全局家校联系记录（可按回执状态筛）。 */
  getFamilyContactsAll({ receiptStatus = '', page = 1, pageSize = 200 } = {}) {
    const params = { page, pageSize }
    if (receiptStatus) params.receiptStatus = receiptStatus
    return callStrict(() => request('/student-affairs/family-contacts', { params }))
  },
  /** 登记家长回执。 */
  markFamilyReceipt(contactId, note = '') {
    return callStrict(() => request(`/student-affairs/family-contacts/${contactId}/receipt`, { method: 'POST', body: { note } }))
  },

  // ─────────────── 宿舍管理（P7 · /student-affairs/dorm/*） ───────────────

  /** 楼栋列表（gender 过滤）。 */
  getBuildings({ gender = '', page = 1, pageSize = 50 } = {}) {
    const params = { page, pageSize }
    if (gender) params.gender = gender
    return callStrict(() => request('/student-affairs/dorm/buildings', { params }))
  },

  /** 新建楼栋（带 floors/roomsPerFloor/bedsPerRoom 则一键铺满床位）。 */
  createBuilding(body) {
    return callStrict(() => request('/student-affairs/dorm/buildings', { method: 'POST', body }))
  },

  /** 铺房+床（层数×每层房数×每间床位）。 */
  generateLayout(buildingId, { floors, roomsPerFloor, bedsPerRoom }) {
    return callStrict(() => request(`/student-affairs/dorm/buildings/${buildingId}/generate`, { method: 'POST', body: { floors, roomsPerFloor, bedsPerRoom } }))
  },

  /** 房间列表（floor 过滤，带空床数）。 */
  getRooms(buildingId, { floor = '', page = 1, pageSize = 200 } = {}) {
    const params = { page, pageSize }
    if (floor) params.floor = floor
    return callStrict(() => request(`/student-affairs/dorm/buildings/${buildingId}/rooms`, { params }))
  },

  /** 床位列表（标空/已住）。 */
  getBeds(roomId) {
    return callStrict(() => request(`/student-affairs/dorm/rooms/${roomId}/beds`))
  },

  /** 宿舍入住率统计。 */
  getOccupancy() {
    return callStrict(() => request('/student-affairs/dorm/occupancy'))
  },

  /** 学生入住某床（回写我的宿舍）。 */
  checkinBed(bedId, studentId) {
    return callStrict(() => request(`/student-affairs/dorm/beds/${bedId}/checkin`, { method: 'POST', body: { studentId: String(studentId) } }))
  },

  /** 退宿（释放床位）。 */
  checkoutBed(bedId) {
    return callStrict(() => request(`/student-affairs/dorm/beds/${bedId}/checkout`, { method: 'POST', body: {} }))
  },

  /** 发起调宿（原床释放/新床占用走审批）。body: { studentId, toBedId, reason } */
  submitDormTransfer(body) {
    return callStrict(() => request('/student-affairs/dorm/transfers', { method: 'POST', body }))
  },

  /** 调宿审批（辅导员→宿管→执行）。action: APPROVE / REJECT（REJECT 原因≥5字）。 */
  reviewDormTransfer(transferId, action, reason = '') {
    return callStrict(() => request(`/student-affairs/dorm/transfers/${transferId}/review`, { method: 'POST', body: { action, reason } }))
  },

  /** 建宿舍检查任务。body: { taskName, buildingId?, checkType HYGIENE/SAFETY/CONTRABAND/NIGHT_ABSENCE, checkerKey? } */
  createDormCheckTask(body) {
    return callStrict(() => request('/student-affairs/dorm/check-tasks', { method: 'POST', body }))
  },

  /** 录检查结果（ABNORMAL 异常说明≥5字 → 回写异常表 + 生成风险单）。body: { roomId?, result NORMAL/ABNORMAL, issueType?, detail } */
  submitDormCheckRecord(taskId, body) {
    return callStrict(() => request(`/student-affairs/dorm/check-tasks/${taskId}/records`, { method: 'POST', body }))
  },

  // ─────────────── 学工归档（P7 · /student-affairs/archive/*） ───────────────

  /** 归档批次列表（含各批档案包计数；可按 status 筛选）。 */
  getArchiveBatches({ status = '', page = 1, pageSize = 50 } = {}) {
    const params = { page, pageSize }
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/archive/batches', { params }))
  },

  /** 建归档批次。body: { batchName, yearCode?, scope? } */
  createArchiveBatch(body) {
    return callStrict(() => request('/student-affairs/archive/batches', { method: 'POST', body }))
  },

  /** 归档批次详情（含档案包清单）。 */
  getArchiveBatch(batchId) {
    return callStrict(() => request(`/student-affairs/archive/batches/${batchId}`))
  },

  /** 圈定学生生成档案包（批次 → COLLECTING）。studentIds: 学生 id 数组。 */
  collectArchive(batchId, studentIds) {
    return callStrict(() => request(`/student-affairs/archive/batches/${batchId}/collect`, { method: 'POST', body: { studentIds: studentIds.map(String) } }))
  },

  /** 批次流转（COLLECTING→COLLEGE_REVIEW→SA_CONFIRM→ARCHIVED；归档登记水印包）。 */
  advanceArchive(batchId, action = 'APPROVE') {
    return callStrict(() => request(`/student-affairs/archive/batches/${batchId}/advance`, { method: 'POST', body: { action } }))
  },

  // ─────────────── 学生活动与第二课堂（D 包波次1 · /activities /second-class） ───────────────

  /** 活动列表（type/status 过滤）。 */
  getActivities({ activityType = '', status = '', page = 1, pageSize = 50 } = {}) {
    const params = { page, pageSize }
    if (activityType) params.activityType = activityType
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/activities', { params }))
  },
  /** 建活动（草稿）。body: { activityName, activityType, startAt?, endAt?, enrollDeadline?, quota?, creditType?, creditValue?, categoryCode?, location?, description? } */
  createActivity(body) {
    return callStrict(() => request('/student-affairs/activities', { method: 'POST', body }))
  },
  /** 发布/取消活动。action: PUBLISH/CANCEL；取消需 reason≥5。 */
  publishActivity(id, action = 'PUBLISH', reason = '') {
    return callStrict(() => request(`/student-affairs/activities/${id}/publish`, { method: 'POST', body: { action, reason } }))
  },
  /** 流转：ENROLL_CLOSE/START/FINISH。 */
  transitionActivity(id, action) {
    return callStrict(() => request(`/student-affairs/activities/${id}/transition`, { method: 'POST', body: { action } }))
  },
  /** 活动名单。 */
  getActivityParticipants(id) {
    return callStrict(() => request(`/student-affairs/activities/${id}/participants`))
  },
  /** 确认名单+生成学时/积分→进360。 */
  confirmActivity(id) {
    return callStrict(() => request(`/student-affairs/activities/${id}/confirm`, { method: 'POST', body: {} }))
  },
  /** 撤销确认（reason≥5）。 */
  unconfirmActivity(id, reason) {
    return callStrict(() => request(`/student-affairs/activities/${id}/unconfirm`, { method: 'POST', body: { reason } }))
  },
  /** 归档活动。 */
  archiveActivity(id) {
    return callStrict(() => request(`/student-affairs/activities/${id}/archive`, { method: 'POST', body: {} }))
  },
  /** 二课积分台账（creditType 过滤，数据范围）。 */
  getSecondClassLedger({ creditType = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (creditType) params.creditType = creditType
    return callStrict(() => request('/student-affairs/second-class/ledger', { params }))
  },
  /** 个人第二课堂成绩单。 */
  getSecondClassReport(studentId) {
    return callStrict(() => request(`/student-affairs/second-class/students/${studentId}/report`))
  },
  /** 二课积分类目列表。 */
  getCreditCategories() {
    return callStrict(() => request('/student-affairs/second-class/categories'))
  },
  /** 建二课积分类目。body: { categoryCode, categoryName, creditType?, description? } */
  createCreditCategory(body) {
    return callStrict(() => request('/student-affairs/second-class/categories', { method: 'POST', body }))
  },
  /** 活动与第二课堂统计（仅聚合）。 */
  getActivityStats() {
    return callStrict(() => request('/student-affairs/activity-stats'))
  },
  /** 第二课堂积分申诉列表。 */
  getCreditAppeals({ status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/second-class/appeals', { params }))
  },
  /** 提交积分申诉。body: { studentId, appealType?, claimCreditType?, claimValue?, activityId?, reason } */
  submitCreditAppeal(body) {
    return callStrict(() => request('/student-affairs/second-class/appeals', { method: 'POST', body }))
  },
  /** 积分申诉审核。action: APPROVE/REJECT。 */
  reviewCreditAppeal(appealId, action, opinion = '') {
    return callStrict(() => request(`/student-affairs/second-class/appeals/${appealId}/review`, { method: 'POST', body: { action, opinion } }))
  },
  /** 志愿时长补录列表。 */
  getVolunteerRecords({ status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/volunteer/records', { params }))
  },
  /** 补录志愿时长。body: { studentId, serviceName, hours, orgName?, serviceDate? } */
  createVolunteerRecord(body) {
    return callStrict(() => request('/student-affairs/volunteer/records', { method: 'POST', body }))
  },
  /** 认定志愿时长→生成学分。 */
  confirmVolunteerRecord(id) {
    return callStrict(() => request(`/student-affairs/volunteer/records/${id}/confirm`, { method: 'POST', body: {} }))
  },
  /** 驳回志愿时长补录（原因≥5字）。 */
  rejectVolunteerRecord(id, reason) {
    return callStrict(() => request(`/student-affairs/volunteer/records/${id}/reject`, { method: 'POST', body: { reason } }))
  },

  // ─────────────── 社团管理（05 卡 · /clubs） ───────────────
  getClubs({ status = '', clubType = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (status) params.status = status
    if (clubType) params.clubType = clubType
    return callStrict(() => request('/student-affairs/clubs', { params }))
  },
  /** 建社团。body: { clubName, clubType?, collegeId?, advisorName?, presidentStudentId? } */
  createClub(body) {
    return callStrict(() => request('/student-affairs/clubs', { method: 'POST', body }))
  },
  /** 社团审批。action: APPROVE/REJECT（REJECT 需 reason≥5）。 */
  reviewClub(id, action = 'APPROVE', reason = '') {
    return callStrict(() => request(`/student-affairs/clubs/${id}/review`, { method: 'POST', body: { action, reason } }))
  },
  /** 注销社团（reason≥5）。 */
  disbandClub(id, reason) {
    return callStrict(() => request(`/student-affairs/clubs/${id}/disband`, { method: 'POST', body: { reason } }))
  },
  getClubMembers(id) {
    return callStrict(() => request(`/student-affairs/clubs/${id}/members`))
  },
  /** 增补成员。body: { studentId, role? } */
  addClubMember(id, body) {
    return callStrict(() => request(`/student-affairs/clubs/${id}/members`, { method: 'POST', body }))
  },
  removeClubMember(memberId) {
    return callStrict(() => request(`/student-affairs/clubs/members/${memberId}/remove`, { method: 'POST', body: {} }))
  },
  getClubAnnualReviews(id) {
    return callStrict(() => request(`/student-affairs/clubs/${id}/annual-reviews`))
  },
  /** 年审。body: { reviewYear, result?, activityCount?, comment? } */
  createClubAnnualReview(id, body) {
    return callStrict(() => request(`/student-affairs/clubs/${id}/annual-reviews`, { method: 'POST', body }))
  },

  // ─────────────── 学生干部与组织（06 卡 · /organizations） ───────────────
  getOrganizations({ level = '', status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (level) params.level = level
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/organizations', { params }))
  },
  /** 建组织。body: { orgName, orgType?, level?, collegeId?, advisorName? } */
  createOrganization(body) {
    return callStrict(() => request('/student-affairs/organizations', { method: 'POST', body }))
  },
  getOrgPositions(orgId) {
    return callStrict(() => request(`/student-affairs/organizations/${orgId}/positions`))
  },
  /** 任命。body: { studentId, position, termCode? } */
  appointOrgPosition(orgId, body) {
    return callStrict(() => request(`/student-affairs/organizations/${orgId}/positions`, { method: 'POST', body }))
  },
  dismissOrgPosition(positionId) {
    return callStrict(() => request(`/student-affairs/organizations/positions/${positionId}/dismiss`, { method: 'POST', body: {} }))
  },
  /** 学生干部履历（组织任职+班级班干部）。 */
  getCadreResume(studentId) {
    return callStrict(() => request(`/student-affairs/students/${studentId}/cadre-resume`))
  },

  // ─────────────── 党团建设（07 卡 · /party-league，材料脱敏） ───────────────
  getLeagueDev({ devType = '', stage = '', status = '', page = 1, pageSize = 100 } = {}) {
    const params = { page, pageSize }
    if (devType) params.devType = devType
    if (stage) params.stage = stage
    if (status) params.status = status
    return callStrict(() => request('/student-affairs/party-league/dev', { params }))
  },
  /** 建发展台账。body: { studentId, devType?, branchName? } */
  createLeagueDev(body) {
    return callStrict(() => request('/student-affairs/party-league/dev', { method: 'POST', body }))
  },
  /** 推进阶段。body: { toStage, materialFileId?, remark? } */
  advanceLeagueStage(devId, body) {
    return callStrict(() => request(`/student-affairs/party-league/dev/${devId}/advance`, { method: 'POST', body }))
  },
  terminateLeagueDev(devId, reason) {
    return callStrict(() => request(`/student-affairs/party-league/dev/${devId}/terminate`, { method: 'POST', body: { reason } }))
  },
  getLeagueStages(devId) {
    return callStrict(() => request(`/student-affairs/party-league/dev/${devId}/stages`))
  }
}

export default studentAffairsApi
