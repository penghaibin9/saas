// Names follow academic_affairs_status_service.STATUSES and CHANGE_FLOW.
export const ACADEMIC_STUDENT_STATUS_LABELS = Object.freeze({
  NORMAL: '正常在籍', REGISTERED: '在籍注册', PENDING_REGISTER: '待注册', UNREGISTERED: '未注册',
  SUSPENDED: '休学', PRESERVED: '保留学籍', RETAINED: '留级', WITHDRAWN: '退学',
  TRANSFER_SCHOOL: '转学', GRADUATED: '毕业', COMPLETED: '结业', INCOMPLETE: '肄业',
  MERGED: '已合并', RECYCLED: '已回收'
})

export const ACADEMIC_STATUS_CHANGE_LABELS = Object.freeze({
  ENROLL_REGISTER: '入学注册', ANNUAL_REGISTER: '学年注册', SEMESTER_REGISTER: '学期注册',
  SUSPEND: '休学', WITHDRAW: '退学', RESUME: '复学', PRESERVE: '保留学籍',
  RETAIN: '留级', TRANSFER_MAJOR: '转专业', TRANSFER_CLASS: '转班'
})
