import { realRequest } from './request'

/** C-W5 教师微信成绩录入：统一走 live-owner execution 入口，不允许 mock 冒充保存成功。 */
const base = '/mobile/teacher/academic/grade-execution/tasks'

export const academicGradeEntryApi = {
  tasks(status) {
    const query = status ? `?status=${encodeURIComponent(status)}` : ''
    return realRequest(`${base}${query}`)
  },
  roster(taskId) {
    return realRequest(`${base}/${encodeURIComponent(taskId)}/roster`)
  },
  enterScore(taskId, body) {
    return realRequest(`${base}/${encodeURIComponent(taskId)}/scores`, {
      method: 'POST',
      data: body || {}
    })
  },
  batchSave(taskId, rows) {
    return realRequest(`${base}/${encodeURIComponent(taskId)}/batch-save`, {
      method: 'POST',
      data: { rows: rows || [] }
    })
  },
  qualityReport(taskId) {
    return realRequest(`${base}/${encodeURIComponent(taskId)}/quality-report`)
  },
  submit(taskId) {
    return realRequest(`${base}/${encodeURIComponent(taskId)}/submit`, {
      method: 'POST'
    })
  }
}

export default academicGradeEntryApi
