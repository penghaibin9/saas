import { request } from '@/services/http/client'

const BASE = '/academic-affairs'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  return {
    code: error?.code || 503001,
    httpStatus: error?.httpStatus,
    data: null,
    message: error?.message || '教学任务工作台加载失败'
  }
}

export const teachingTaskWorkbenchApi = {
  async getFormationProof(programCourseId) {
    try { return ok(await request(`${BASE}/programs/courses/${encodeURIComponent(String(programCourseId))}/formation-proof`, { timeoutMs: 15000 })) } catch (error) { return fail(error) }
  },
  async confirmFormationProof(programCourseId, body) {
    try { return ok(await request(`${BASE}/programs/courses/${encodeURIComponent(String(programCourseId))}/formation-proof`, { method: 'POST', body, timeoutMs: 15000 })) } catch (error) { return fail(error) }
  },
  async getSourceReview(taskId, otherTaskId) {
    try {
      return ok(await request(`${BASE}/teaching-tasks/${encodeURIComponent(String(taskId))}/source-review`, { params: { otherTaskId: String(otherTaskId) }, timeoutMs: 15000 }))
    } catch (error) {
      return fail(error)
    }
  },
  async confirmSourceHandoff(executionTaskId, body) {
    try { return ok(await request(`${BASE}/teaching-tasks/${encodeURIComponent(String(executionTaskId))}/source-handoff`, { method: 'POST', body, timeoutMs: 15000 })) } catch (error) { return fail(error) }
  },
  async getBatch(batchId) {
    try {
      return ok(await request(`${BASE}/teaching-task-batches/${batchId}/workbench`))
    } catch (error) {
      return fail(error)
    }
  }
}
