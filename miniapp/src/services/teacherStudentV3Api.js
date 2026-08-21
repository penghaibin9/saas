import { realRequest } from './request'

const PAGE_SIZE = 20

function normalizePageSize(value) {
  return Math.min(100, Math.max(1, Number(value) || PAGE_SIZE))
}

function buildQuery({ classId = '', keyword = '', cursor = '', pageSize = PAGE_SIZE } = {}) {
  const params = [`pageSize=${normalizePageSize(pageSize)}`]
  const normalizedClassId = String(classId || '').trim()
  const normalizedKeyword = String(keyword || '').trim()
  const normalizedCursor = String(cursor || '').trim()
  if (normalizedClassId) params.push(`classId=${encodeURIComponent(normalizedClassId)}`)
  if (normalizedKeyword) params.push(`keyword=${encodeURIComponent(normalizedKeyword)}`)
  if (normalizedCursor) params.push(`cursor=${encodeURIComponent(normalizedCursor)}`)
  return params.join('&')
}

export const teacherStudentV3Api = {
  list: (params = {}) => realRequest(`/teacher-mobile/students?${buildQuery(params)}`)
}

export { PAGE_SIZE as TEACHER_STUDENT_PAGE_SIZE }
export default teacherStudentV3Api
