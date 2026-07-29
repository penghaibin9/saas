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
  async getBatch(batchId) {
    try {
      return ok(await request(`${BASE}/teaching-task-batches/${batchId}/workbench`))
    } catch (error) {
      return fail(error)
    }
  }
}
