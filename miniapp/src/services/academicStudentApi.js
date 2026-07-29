import { studentApi as baseStudentApi } from './studentApi'
import { realRequest } from './request'

/**
 * 教务学生端专用 API 覆盖。
 *
 * 共享 studentApi 保持当前 main 原样，教务考试页面只在本模块切换到
 * 时区安全、本人名单校验的 v2 接口，避免与岗位实习、毕业设计后续改动冲突。
 */
export const academicStudentApi = {
  ...baseStudentApi,
  getMyExamSchedule: () => realRequest('/mobile/academic/exam-v2/my'),
  getMyDeferOptions: () => realRequest('/mobile/academic/exam-v2/defer-options'),
  applyDefer: (examCourseId, reasonType, reason) =>
    realRequest('/mobile/academic/exam-v2/defer/apply', {
      method: 'POST',
      data: { examCourseId, reasonType, reason }
    })
}

export default academicStudentApi
