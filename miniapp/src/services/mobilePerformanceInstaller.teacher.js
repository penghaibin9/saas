/**
 * 教师端移动高频接口适配（PR #24 + #26 能力，V3 从全局 bootstrap 拆出）。
 *
 * V3 S1.5 Bootstrap De-hoist：以前这些补丁写在 main.js 静态导入的
 * mobilePerformanceInstaller 里，任何一个学生用户冷启动也会连带装配教师 API 与
 * 教师 mock 图。现在改成教师分包页面首次进入时显式安装，学生侧运行期不再触碰。
 *
 * 页面继续调用原 teacherApi.*，实际只走统一高频接口。
 */
import { teacherApi } from './teacherApi'
import { mockRequest, realFirstStrict, realRequest } from './request'
import * as M from '@/mock'

const enc = (value) => encodeURIComponent(String(value ?? ''))

let installed = false

/** 幂等：教师分包页面可以放心重复调用。 */
export function ensureTeacherPerformanceApi() {
  if (installed) return teacherApi
  installed = true

  teacherApi.getWorkbench = (roleKey) =>
    realFirstStrict(
      'teacher.workbench.performance',
      () => realRequest('/mobile/performance/teacher/workbench?pageSize=8'),
      () => mockRequest(M.workbenchByRole[roleKey] || M.workbenchByRole.counselor)
    )

  teacherApi.getTodosPage = (group = 'all', page = 1, pageSize = 20) =>
    realFirstStrict(
      'teacher.todos.performance',
      () => realRequest(
        `/mobile/performance/teacher/todos-page?group=${enc(group)}&page=${page}&pageSize=${pageSize}`
      ),
      () => mockRequest({ filters: M.todoFilters, list: M.teacherTodos })
    )

  teacherApi.getRiskStudentsPage = (level = 'all', page = 1, pageSize = 20) =>
    realFirstStrict(
      'teacher.risk.performance',
      () => realRequest(
        `/mobile/performance/teacher/risk-students-page?level=${enc(level)}&page=${page}&pageSize=${pageSize}`
      ),
      () => mockRequest({
        list: M.students.filter((student) => student.risk === 'HIGH' || student.risk === 'MEDIUM')
      })
    )

  return teacherApi
}

export default ensureTeacherPerformanceApi
