export function academicErrorKind(error) {
  const status = Number(error?.status || 0)
  const codes = [error?.bizCode, error?.code].map((value) => String(value || '').toUpperCase())
  const code = codes.join(' ')
  if (status === 403 || codes.some((value) => value.startsWith('403') || value.includes('FORBIDDEN') || value.includes('PERMISSION'))) return 'forbidden'
  if (status === 409 || codes.some((value) => value.startsWith('409') || value.includes('CONFLICT') || value.includes('VERSION'))) return 'conflict'
  const message = String(error?.message || '')
  if (error?.network === true || error?.name === 'AbortError' || error instanceof TypeError || code.includes('TIMEOUT') || /网络|超时|timeout|failed to fetch|networkerror|load failed|aborted/i.test(message)) return 'network'
  return 'error'
}

export function academicErrorMessage(error, fallback = '读取失败，请稍后重试') {
  const kind = academicErrorKind(error)
  if (kind === 'forbidden') return '当前账号已无权查看这项本人教务数据，页面已清除先前内容。'
  if (kind === 'conflict') return `${error?.message || '业务事实已变化'}；已保留当前填写内容，请重新核对最新状态后办理。`
  if (kind === 'network') return '网络连接失败，未把本次结果当作“暂无数据”。请恢复网络后重新核对。'
  return error?.message || fallback
}

export function academicReceipt({ title, object, status, operatedAt, next, relatedTo = '/academic', relatedLabel = '返回学业工作台' }) {
  return {
    title: title || '办理结果已记录',
    object: object || '当前教务事项',
    status: status || '状态待确认',
    operatedAt: operatedAt || '学校未提供办理时间',
    next: next || '请回到当前页面核对服务器最新记录。',
    relatedTo,
    relatedLabel
  }
}

export function markStudentAcademicFormClean() {
  if (typeof window !== 'undefined') window.dispatchEvent(new CustomEvent('student-portal-form-clean'))
}
