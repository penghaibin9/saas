/**
 * PR #24 + #26 最终移动性能适配。
 * 页面继续调用原 studentApi/teacherApi，实际只走统一高频接口。
 */
import { studentApi } from './studentApi'
import { teacherApi } from './teacherApi'
import { mockRequest, realFirstStrict, realRequest } from './request'
import * as M from '@/mock'

const enc = (value) => encodeURIComponent(String(value ?? ''))

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

studentApi.getMessagesPage = (tab = 'todo', page = 1, pageSize = 20) =>
  realFirstStrict(
    'student.messages.performance',
    () => realRequest(
      `/mobile/performance/student/messages-page?tab=${enc(tab)}&page=${page}&pageSize=${pageSize}`
    ),
    () => mockRequest({ tabs: M.studentMessageTabs, groups: M.studentMessages })
  )

let queuedIds = new Set()
let queuedWaiters = []
let flushScheduled = false

function flushReadBatch() {
  flushScheduled = false
  const messageIds = [...queuedIds]
  const waiters = queuedWaiters
  queuedIds = new Set()
  queuedWaiters = []
  if (!messageIds.length) {
    waiters.forEach(({ resolve }) => resolve({ affectedCount: 0 }))
    return
  }
  realRequest('/mobile/performance/student/messages/read-batch', {
    method: 'POST',
    data: { messageIds }
  }).then(
    (result) => waiters.forEach(({ resolve }) => resolve(result)),
    (error) => waiters.forEach(({ reject }) => reject(error))
  )
}

/**
 * 同一个事件循环里的逐条“已读”调用合并成一次批量请求。
 * 因此列表“全部已读”只产生一次HTTP写请求，打开单条消息仍只更新该条。
 */
studentApi.markMessageRead = (messageId) => {
  const raw = String(messageId || '').replace('msg-', '').trim()
  if (!/^\d+$/.test(raw)) return Promise.resolve({ affectedCount: 0 })
  queuedIds.add(raw)
  const pending = new Promise((resolve, reject) => {
    queuedWaiters.push({ resolve, reject })
  })
  if (!flushScheduled) {
    flushScheduled = true
    Promise.resolve().then(flushReadBatch)
  }
  return pending
}
