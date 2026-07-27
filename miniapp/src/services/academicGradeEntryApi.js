import { realRequest } from './request'

/** V2 R5 教师微信成绩录入补充接口：只走真实后端，不允许 mock 冒充保存成功。 */
export const academicGradeEntryApi = {
  batchSave(taskId, rows) {
    return realRequest(`/mobile/teacher/academic/grade-tasks/${taskId}/batch-save`, {
      method: 'POST',
      data: { rows: rows || [] }
    })
  },
  qualityReport(taskId) {
    return realRequest(`/mobile/teacher/academic/grade-tasks/${taskId}/quality-report`)
  }
}

export default academicGradeEntryApi
