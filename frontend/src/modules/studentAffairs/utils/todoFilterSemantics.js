/**
 * 学工待办 / 首页下钻公共筛选语义。
 * URL 可用 PENDING/OPEN/DONE/OVERDUE/NEAR；页面映射到真实业务状态，禁止回落无筛选总表。
 */

export const COMMON_FILTERS = Object.freeze({
  PENDING: 'PENDING',
  OPEN: 'OPEN',
  DONE: 'DONE',
  OVERDUE: 'OVERDUE',
  NEAR: 'NEAR'
})

const AID_REVIEW = ['CLASS_REVIEW', 'COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'SCHOOL_REVIEW']
const FUND_REVIEW = ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'SCHOOL_REVIEW']
const DISC_REVIEW = ['COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW', 'SCHOOL_REVIEW']
const RISK_OPEN = ['NEW', 'ASSIGNED', 'PROCESSING', 'FOLLOWING', 'ESCALATED', 'TRANSFERRED', 'REOPENED']
const LEAVE_PENDING = ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW']
const DORM_TRANSFER_PENDING = ['PENDING', 'SUBMITTED', 'COUNSELOR_REVIEW', 'DORM_REVIEW', 'DORM_MANAGER_REVIEW']

/**
 * 将 URL 公共语义解析为页面 activeStatus（单值或聚合 key）。
 * @param {string} domain aid|funding|discipline|risk|leave|dormTransfer|dormException|talk
 * @param {string} raw query.status
 * @returns {{ activeKey: string, matchStatuses: string[]|null, label: string }}
 */
export function resolveTodoStatus(domain, raw) {
  const s = String(raw || '').trim()
  if (!s) return { activeKey: 'ALL', matchStatuses: null, label: '' }

  const aliases = {
    aid: {
      PENDING: { activeKey: 'REVIEW', matchStatuses: AID_REVIEW, label: '待审' },
      REVIEW: { activeKey: 'REVIEW', matchStatuses: AID_REVIEW, label: '评审中' },
      ADJUST_PENDING: { activeKey: 'ADJUST_REVIEW', matchStatuses: ['ADJUST_REVIEW'], label: '调整待审' },
      OPEN: { activeKey: 'REVIEW', matchStatuses: [...AID_REVIEW, 'PUBLICITY', 'ADJUST_REVIEW'], label: '未关闭' },
      DONE: { activeKey: 'APPROVED', matchStatuses: ['APPROVED', 'ARCHIVED'], label: '已完成' },
      OVERDUE: { activeKey: 'PUBLICITY', matchStatuses: ['PUBLICITY'], label: '公示中' }
    },
    funding: {
      PENDING: { activeKey: 'REVIEW', matchStatuses: FUND_REVIEW, label: '待审' },
      REVIEW: { activeKey: 'REVIEW', matchStatuses: FUND_REVIEW, label: '评审中' },
      OPEN: { activeKey: 'REVIEW', matchStatuses: [...FUND_REVIEW, 'PUBLICITY', 'RETURNED'], label: '未关闭' },
      DONE: { activeKey: 'GRANTED', matchStatuses: ['GRANTED', 'ARCHIVED'], label: '已完成' },
      OVERDUE: { activeKey: 'PUBLICITY', matchStatuses: ['PUBLICITY'], label: '公示中' }
    },
    discipline: {
      PENDING: { activeKey: 'REVIEW', matchStatuses: DISC_REVIEW, label: '待审' },
      REVIEW: { activeKey: 'REVIEW', matchStatuses: DISC_REVIEW, label: '审批中' },
      REMOVE_PENDING: { activeKey: 'REMOVE_REVIEW', matchStatuses: ['REMOVE_REVIEW'], label: '解除待审' },
      OPEN: {
        activeKey: 'REVIEW',
        matchStatuses: [...DISC_REVIEW, 'REGISTERED', 'RETURNED', 'REMOVE_REVIEW'],
        label: '未关闭'
      },
      DONE: { activeKey: 'EFFECTIVE', matchStatuses: ['EFFECTIVE', 'REMOVED', 'CANCELLED'], label: '已完成' }
    },
    risk: {
      PENDING: { activeKey: 'PENDING', matchStatuses: ['NEW', 'ASSIGNED', 'REOPENED', 'TRANSFERRED'], label: '待处置' },
      OPEN: { activeKey: 'OPEN', matchStatuses: RISK_OPEN, label: '未关闭' },
      DONE: { activeKey: 'CLOSED', matchStatuses: ['CLOSED'], label: '已关闭' },
      OVERDUE: { activeKey: 'ESCALATED', matchStatuses: ['ESCALATED'], label: '已升级/超时' },
      NEAR: { activeKey: 'PENDING', matchStatuses: ['NEW', 'ASSIGNED'], label: '临近超时' }
    },
    leave: {
      PENDING: { activeKey: 'PENDING', matchStatuses: LEAVE_PENDING, label: '待审批' },
      CANCEL_PENDING: { activeKey: 'WAIT_CANCEL_LEAVE', matchStatuses: ['WAIT_CANCEL_LEAVE'], label: '销假待确认' },
      OPEN: {
        activeKey: 'OPEN',
        matchStatuses: [...LEAVE_PENDING, 'APPROVED', 'OVERDUE', 'WAIT_CANCEL_LEAVE'],
        label: '未关闭'
      },
      DONE: { activeKey: 'CLOSED', matchStatuses: ['CLOSED', 'REJECTED', 'CANCELLED'], label: '已完成' },
      OVERDUE: { activeKey: 'OVERDUE', matchStatuses: ['OVERDUE'], label: '逾期' }
    },
    dormTransfer: {
      PENDING: { activeKey: 'PENDING', matchStatuses: DORM_TRANSFER_PENDING, label: '待审批' },
      OPEN: { activeKey: 'PENDING', matchStatuses: DORM_TRANSFER_PENDING, label: '未关闭' },
      DONE: { activeKey: 'DONE', matchStatuses: ['APPROVED', 'REJECTED', 'EXECUTED'], label: '已完成' }
    },
    dormException: {
      PENDING: { activeKey: 'PENDING_HANDLE', matchStatuses: ['PENDING_HANDLE', 'OPEN'], label: '待处置' },
      PENDING_HANDLE: { activeKey: 'PENDING_HANDLE', matchStatuses: ['PENDING_HANDLE', 'OPEN'], label: '待处置' },
      OPEN: { activeKey: 'PENDING_HANDLE', matchStatuses: ['PENDING_HANDLE', 'OPEN'], label: '未关闭' },
      DONE: { activeKey: 'HANDLED', matchStatuses: ['HANDLED', 'CLOSED'], label: '已处置' },
      OVERDUE: { activeKey: 'PENDING_HANDLE', matchStatuses: ['PENDING_HANDLE'], label: '待处置' }
    },
    talk: {
      PENDING: { activeKey: 'PLANNED', matchStatuses: ['PLANNED', 'SCHEDULED', 'FOLLOW_UP'], label: '待办' },
      OPEN: { activeKey: 'OPEN', matchStatuses: ['PLANNED', 'SCHEDULED', 'FOLLOW_UP', 'IN_PROGRESS'], label: '未关闭' },
      DONE: { activeKey: 'CLOSED', matchStatuses: ['COMPLETED', 'CLOSED'], label: '已完成' }
    }
  }

  const map = aliases[domain] || {}
  if (map[s]) return map[s]
  // 已是具体业务状态：按精确匹配
  return { activeKey: s, matchStatuses: [s], label: s }
}

/** 列表行是否命中解析结果 */
export function rowMatchesTodoStatus(rowStatus, resolved) {
  if (!resolved || !resolved.matchStatuses) return true
  return resolved.matchStatuses.includes(rowStatus)
}

/** 从路由读取学生筛选 */
export function readStudentFilter(query = {}) {
  const studentId = query.studentId != null && query.studentId !== '' ? String(query.studentId) : ''
  const studentNo = query.studentNo != null && query.studentNo !== '' ? String(query.studentNo) : ''
  const studentName = query.studentName != null && query.studentName !== '' ? String(query.studentName) : ''
  return { studentId, studentNo, studentName }
}
