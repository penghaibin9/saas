import { CHANGE_FLOW_NODES } from '../../constants/status-change.js'

export function decisionVersion(row) {
  const value = row?.decisionVersion
  if (value === null || value === undefined || value === '' || typeof value === 'boolean') return null
  const version = Number(value)
  return Number.isSafeInteger(version) && version >= 0 ? version : null
}

export function nodePermission(row) {
  if (!['SUBMITTED', 'IN_REVIEW'].includes(row?.status)) return ''
  if (!(CHANGE_FLOW_NODES[row.changeType] || []).includes(row.currentNode)) return ''
  return ({ COUNSELOR_REVIEW: 'counselorReview', COLLEGE_REVIEW: 'collegeReview',
    OUT_COLLEGE_REVIEW: 'collegeReview', IN_COLLEGE_REVIEW: 'collegeReview',
    COLLEGE_ASSIGN_CLASS: 'collegeReview', AA_OFFICE_FINAL: 'officeReview' })[row.currentNode] || ''
}

const sourceKeys = ['changeId', 'studentId', 'changeType', 'fromStatus', 'toStatus', 'reason',
  'effectiveDate', 'expireDate', 'toClassId', 'toMajorId', 'expectedStudentVersion']
const immutableSourceKeys = sourceKeys.filter(key => key !== 'effectiveDate')
export function sameChangeSource(a, b) {
  return !!a && !!b && sourceKeys.every(key => String(a[key] ?? '') === String(b[key] ?? ''))
}
function sameImmutableChangeSource(a, b) {
  return !!a && !!b && immutableSourceKeys.every(key => String(a[key] ?? '') === String(b[key] ?? ''))
}
export function sameDecision(a, b) {
  return sameChangeSource(a, b) && decisionVersion(a) !== null && decisionVersion(a) === decisionVersion(b)
    && ['status', 'currentNode', 'currentTaskId', 'version'].every(key => String(a[key] ?? '') === String(b[key] ?? ''))
}
export function sameDecisionOutcome(a, b) {
  return sameImmutableChangeSource(a, b) && decisionVersion(a) !== null && decisionVersion(a) === decisionVersion(b)
    && ['status', 'currentNode', 'currentTaskId', 'version'].every(key => String(a[key] ?? '') === String(b[key] ?? ''))
}

// Only checks a returned formal outcome against the frozen decision. Does not choose server actions.
export function matchesDecisionResult(before, action, after) {
  if (!sameImmutableChangeSource(before, after) || decisionVersion(before) === null
    || decisionVersion(after) !== decisionVersion(before) + 1) return false
  if (action === 'RETURN' || action === 'REJECT') {
    return after.status === (action === 'RETURN' ? 'RETURNED' : 'REJECTED') && !after.currentTaskId
      && String(after.effectiveDate ?? '') === String(before.effectiveDate ?? '')
  }
  if (action !== 'APPROVE') return false
  const nodes = CHANGE_FLOW_NODES[before.changeType] || [], index = nodes.indexOf(before.currentNode)
  if (index < 0) return false
  if (index < nodes.length - 1) return after.status === 'IN_REVIEW' && after.currentNode === nodes[index + 1]
    && !!after.currentTaskId && String(after.currentTaskId) !== String(before.currentTaskId)
    && String(after.effectiveDate ?? '') === String(before.effectiveDate ?? '')
  return ['EFFECTIVE', 'APPROVED_PENDING_EFFECTIVE'].includes(after.status) && !after.currentTaskId
    && (after.status !== 'EFFECTIVE' || !!after.effectiveDate)
}
