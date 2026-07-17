/**
 * 学工中心 · 请假销假（销假/续假/台账/统计）API —— 生产级只走真实后端 /student-affairs/leave/*。
 * 后端在既有 t_cs_leave（affairs_status 14 态）上闭环；owner + 数据范围 + 审批留痕由后端强校验。
 * 契约见 docs/03-业务模块设计/学工中心/13A-学工中心API契约草案.md §5。
 */
import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const B = '/student-affairs'

export const leaveApi = {
  /** 请假台账 / 后续处理列表（全状态；followupOnly=只取延期销假可处理活动态） */
  ledger(params = {}) { return callList(`${B}/leave`, params) },
  /** 初审待办队列（仅本人身份轮到审批的节点：COUNSELOR_REVIEW/COLLEGE_REVIEW/STUDENT_AFFAIRS_REVIEW） */
  pending(params = {}) { return callList(`${B}/leave/pending`, params) },
  /** 请假详情（含销假/续假记录 + 审批留痕） */
  detail(id) { return call(() => request(`${B}/leave/${id}`)) },
  /** 请假统计（groupBy=CLASS/TYPE/STATUS） */
  stats(params = {}) { return call(() => request(`${B}/leave/stats`, { params })) },
  /** 初审通过（多级逐节点推进，comment 可选） */
  approve(id, body) { return call(() => request(`${B}/leave/${id}/approve`, { method: 'POST', body })) },
  /** 初审驳回（终态，reason≥5字） */
  reject(id, body) { return call(() => request(`${B}/leave/${id}/reject`, { method: 'POST', body })) },
  /** 初审退回重提（reason≥5字，学生可修改后重新提交） */
  returnForResubmit(id, body) { return call(() => request(`${B}/leave/${id}/return`, { method: 'POST', body })) },

  /** 辅导员代登记销假 → WAIT_CANCEL_LEAVE */
  proxyCancel(id, body) { return call(() => request(`${B}/leave/${id}/proxy-cancel`, { method: 'POST', body })) },
  /** 销假确认(CONFIRM→CLOSED) / 销假退回(RETURN→APPROVED) */
  cancelConfirm(id, body) { return call(() => request(`${B}/leave/${id}/cancel-confirm`, { method: 'POST', body })) },
  /** 发起续假（辅导员代发起 → EXTENSION_REVIEW） */
  applyExtension(id, body) { return call(() => request(`${B}/leave/${id}/extension`, { method: 'POST', body })) },
  /** 续假审批（APPROVE→更新结束时间 / REJECT→维持原假期） */
  extensionReview(id, body) { return call(() => request(`${B}/leave/${id}/extension-approve`, { method: 'POST', body })) },
  /** 逾期处置登记（CONTACT/TO_HOME_SCHOOL/CLOSE） */
  overdueHandle(id, body) { return call(() => request(`${B}/leave/${id}/overdue-handle`, { method: 'POST', body })) },
  /** 逾期扫描（手动触发，幂等） */
  scanOverdue() { return call(() => request(`${B}/leave/scan-overdue`, { method: 'POST' })) },
  /** 请假台账导出（xlsx 水印 + 导出留痕），返回 { filename, contentBase64, mediaType, rowCount } */
  exportLedger(params = {}) { return call(() => request(`${B}/leave/export`, { method: 'POST', params })) }
}

export default leaveApi
