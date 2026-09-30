// Only a business identifier crosses login; arbitrary return URLs are never accepted.
export function dormLoginReturn(entry, id) {
  const value = String(id || '')
  if (!/^[1-9]\d*$/.test(value)) return ''
  if (entry === 'student') return `/pages/student/affairs/dorm?rectificationId=${value}`
  if (entry === 'teacher') return `/pages/teacher/dorm-review/index?tab=recheck&recordId=${value}`
  return ''
}
