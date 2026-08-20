import { realRequest } from './request'

const PAGE_SIZE = 20

function normalizePageSize(value) {
  return Math.min(100, Math.max(1, Number(value) || PAGE_SIZE))
}

function buildQuery({ group = 'all', cursor = '', pageSize = PAGE_SIZE } = {}) {
  const params = [
    `group=${encodeURIComponent(String(group || 'all'))}`,
    `pageSize=${normalizePageSize(pageSize)}`
  ]
  const normalizedCursor = String(cursor || '').trim()
  if (normalizedCursor) params.push(`cursor=${encodeURIComponent(normalizedCursor)}`)
  return params.join('&')
}

export const teacherTodoT8Api = {
  list: (params = {}) => realRequest(`/teacher-mobile/todos/grouped-continuous?${buildQuery(params)}`)
}

export { PAGE_SIZE as TEACHER_TODO_PAGE_SIZE }
export default teacherTodoT8Api
