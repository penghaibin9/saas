import { realRequest } from './request'

const PAGE_SIZE = 20

function pagePath(path, page = 1, pageSize = PAGE_SIZE) {
  const p = Math.max(1, Number(page) || 1)
  const size = Math.min(100, Math.max(1, Number(pageSize) || PAGE_SIZE))
  return `${path}?page=${p}&pageSize=${size}`
}

export const graduationTeacherPagingApi = {
  choices: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/choices/pending', page, pageSize)),
  changes: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/change-requests/pending', page, pageSize)),
  students: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/my-students', page, pageSize)),
  reviews: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/reviews/my', page, pageSize)),
  defenses: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/defense/arrangements', page, pageSize)),
  defenseScores: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/defense/pending', page, pageSize)),
  midtermQueue: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/midterm/queue', page, pageSize)),
  gradeQueue: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/grade/queue', page, pageSize)),
  taskbooks: (page = 1, pageSize = PAGE_SIZE) =>
    realRequest(pagePath('/mobile/teacher/graduation/taskbooks', page, pageSize))
}

export { PAGE_SIZE as GRADUATION_TEACHER_PAGE_SIZE }
export default graduationTeacherPagingApi
