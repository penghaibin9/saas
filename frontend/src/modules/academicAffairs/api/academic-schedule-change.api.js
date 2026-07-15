/**
 * 教务中心 · 调停课 API（13B-R2 / SM-08；生产级：仅走真实后端，不回退 mock）。
 * 后端契约：/api/v1/academic-affairs/schedule-change/*（AC-072~076）。
 * envelope：{ code, data, message }，code=0 成功；错误经 http/client 抛出后统一转 fail。
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

const BASE = '/academic-affairs/schedule-change'

export const CHANGE_TYPES = [
  { value: 'ADJUST', label: '调课' },
  { value: 'STOP', label: '停课' },
  { value: 'MAKEUP', label: '补课' }
]

export const CHANGE_STATUS = [
  { value: 'SUBMITTED', label: '待学院审', tone: 'info' },
  { value: 'COLLEGE_REVIEW', label: '待教务处审', tone: 'processing' },
  { value: 'ACADEMIC_REVIEW', label: '教务处审核中', tone: 'processing' },
  { value: 'APPROVED', label: '已通过', tone: 'success' },
  { value: 'APPLIED', label: '已生效', tone: 'success' },
  { value: 'REJECTED', label: '已驳回', tone: 'danger' },
  { value: 'CANCELLED', label: '已撤销', tone: 'default' }
]

export const scheduleChangeApi = {
  /** 台账/列表（范围过滤：教务处全量 / 学院按班级 / 教师按本人课位） */
  list(params = {}) {
    return callList(BASE, params)
  },
  /** 归档检索（仅终态：已生效/已驳回/已撤销；服务层强制过滤，不依赖前端默认参数） */
  archive(params = {}) {
    return callList(`${BASE}/archive`, params)
  },
  /** 统计（按类型/状态/学院/教师聚合） */
  stats(params = {}) {
    return call(() => request(`${BASE}/stats`, { params }))
  },
  /** 冲突预检（只读，不落库；提交前 UX 反馈，复用与提交同一冲突检测算法） */
  conflictCheck(body) {
    return call(() => request(`${BASE}/conflict-check`, { method: 'POST', body }))
  },
  /** 详情（含通知单打印数据） */
  detail(id) {
    return call(() => request(`${BASE}/${id}`))
  },
  /** 教师发起（提交即目标冲突预检；冲突则后端 409 单据不落库） */
  submit(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  /** 审批通过（学院/教务处；终审通过即改写课表 → APPLIED） */
  approve(id, comment = '') {
    return call(() => request(`${BASE}/${id}/approve`, { method: 'POST', body: { action: 'APPROVE', comment } }))
  },
  /** 驳回（原因≥5 字） */
  reject(id, comment) {
    return call(() => request(`${BASE}/${id}/reject`, { method: 'POST', body: { action: 'REJECT', comment } }))
  },
  /** 撤销（仅 SUBMITTED/COLLEGE_REVIEW；APPROVED 后 409） */
  cancel(id, reason = '') {
    return call(() => request(`${BASE}/${id}/cancel`, { method: 'POST', body: { reason } }))
  }
}

export default scheduleChangeApi
