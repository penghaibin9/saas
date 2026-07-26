import { realRequest } from './request'

/** 教师小程序：服务端权限 + 本人数据范围内批次上下文。 */
export const teacherInternshipContext = () =>
  realRequest('/mobile/teacher/internship/context')

/** 教师小程序：本人当前批次实习学生。batchId 为强制业务上下文。 */
export const teacherInternshipMyStudents = (batchId) => {
  const value = String(batchId || '').trim()
  if (!value) {
    return Promise.reject({ code: 'BATCH_REQUIRED', biz: true, message: '请先选择实习批次' })
  }
  return realRequest(`/mobile/teacher/internship/my-students?batchId=${encodeURIComponent(value)}`)
}

/** 学生本人：后端唯一合规事实源，学生端禁止自行重新计算。 */
export const studentInternshipCompliance = (operation = 'ONBOARD', batchId = '') => {
  const query = [`operation=${encodeURIComponent(operation || 'ONBOARD')}`]
  if (batchId) query.push(`batchId=${encodeURIComponent(batchId)}`)
  return realRequest(`/mobile/internship/compliance/my?${query.join('&')}`)
}

/** 学生知情确认：列表、正文、阅读、确认、拒绝。 */
export const studentInternshipConsents = () =>
  realRequest('/mobile/internship/consents')
export const studentInternshipConsentDetail = (consentId) =>
  realRequest(`/mobile/internship/consents/${consentId}`)
export const studentInternshipConsentView = (consentId) =>
  realRequest(`/mobile/internship/consents/${consentId}/view`, { method: 'POST' })
export const studentInternshipConsentConfirm = (consentId, body) =>
  realRequest(`/mobile/internship/consents/${consentId}/confirm`, { method: 'POST', data: body || {} })
export const studentInternshipConsentReject = (consentId, body) =>
  realRequest(`/mobile/internship/consents/${consentId}/reject`, { method: 'POST', data: body || {} })

/** 学生安全教育：课程、详情、开始、提交、承诺。 */
export const studentInternshipSafetyCourses = () =>
  realRequest('/mobile/internship/safety/courses')
export const studentInternshipSafetyCompletions = () =>
  realRequest('/mobile/internship/safety/completions')
export const studentInternshipSafetyCourseDetail = (courseId) =>
  realRequest(`/mobile/internship/safety/courses/${courseId}/detail`)
export const studentInternshipSafetyStart = (courseId) =>
  realRequest(`/mobile/internship/safety/courses/${courseId}/start`, { method: 'POST' })
export const studentInternshipSafetySubmit = (courseId, body) =>
  realRequest(`/mobile/internship/safety/courses/${courseId}/submit`, { method: 'POST', data: body || {} })
export const studentInternshipSafetyCommit = (completionId, body) =>
  realRequest(`/mobile/internship/safety/completions/${completionId}/commit`, { method: 'POST', data: body || {} })
