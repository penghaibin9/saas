// Presentation only: server status, actions and timeline order stay authoritative.
const LEAVE_TYPES = { SICK: '病假', PERSONAL: '事假', HOME: '探亲假', HOSPITAL: '住院假', GOOUT: '外出', OTHER: '其他' }
const NODE_LABELS = {
  COUNSELOR_REVIEW: '辅导员审核', COLLEGE_REVIEW: '学院审核',
  SCHOOL_REVIEW: '学校审核', TEACHER_CONFIRM: '任课教师确认',
  ACADEMIC_FINAL: '教务终审', DORM_MANAGER_REVIEW: '宿管审核'
}

export function receiptTitle(title) {
  return String(title || '').replace(/^学生请假（([A-Z_]+)）$/, (original, type) =>
    LEAVE_TYPES[type] ? `学生请假（${LEAVE_TYPES[type]}）` : original)
}

export function receiptNodeTitle(node) {
  const label = node.label || node.nodeCode || ''
  return NODE_LABELS[label] || label || '办理节点'
}
