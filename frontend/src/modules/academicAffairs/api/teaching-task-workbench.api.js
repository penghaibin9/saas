import { request } from '@/services/http/client'

const BASE = '/academic-affairs'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  return {
    code: error?.code || 503001,
    data: null,
    message: error?.message || '教学任务工作台加载失败'
  }
}

export const teachingTaskWorkbenchApi = {
  async getSourceReview(taskId, otherTaskId) {
    try {
      return ok(await request(`${BASE}/teaching-tasks/${encodeURIComponent(String(taskId))}/source-review`, { params: { otherTaskId: String(otherTaskId) }, timeoutMs: 15000 }))
    } catch (error) {
      return fail(error)
    }
  },
  async getBatch(batchId) {
    try {
      return ok(await request(`${BASE}/teaching-task-batches/${batchId}/workbench`))
    } catch (error) {
      return fail(error)
    }
  }
}
