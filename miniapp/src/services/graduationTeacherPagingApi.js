import { realRequest } from './request'

const PAGE_SIZE = 20

function pagePath(path, page = 1, pageSize = PAGE_SIZE) {
  const p = Math.max(1, Number(page) || 1)
  const size = Math.min(100, Math.max(1, Number(pageSize) || PAGE_SIZE))
  return `${path}?page=${p}&pageSize=${size}`
}

export const graduationTeacherPagingApi = {
  midtermQueue: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/midterm/queue', page, pageSize)),
  gradeQueue: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/grade/queue', page, pageSize)),
  taskbooks: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/taskbooks', page, pageSize))
}

export { PAGE_SIZE as GRADUATION_TEACHER_PAGE_SIZE }
export default graduationTeacherPagingApi
