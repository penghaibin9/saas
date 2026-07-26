import { realRequest } from './request'

function requireBatch(batchId) {
  const value = String(batchId || '').trim()
  if (!value) throw { code: 'BATCH_REQUIRED', biz: true, message: '请先选择实习批次' }
  return value
}

function optionalBatch(path, batchId) {
  const value = String(batchId || '').trim()
  return value ? `${path}${path.includes('?') ? '&' : '?'}batchId=${encodeURIComponent(value)}` : path
}

/** 教师小程序：服务端权限 + 本人数据范围内批次上下文。 */
export const teacherInternshipContext = () =>
  realRequest('/mobile/teacher/internship/context')

/** 教师小程序：本人当前批次实习学生。 */
export const teacherInternshipMyStudents = (batchId) => {
  try {
    const value = requireBatch(batchId)
    return realRequest(`/mobile/teacher/internship/my-students?batchId=${encodeURIComponent(value)}`)
  } catch (e) { return Promise.reject(e) }
}

/** 教师小程序：显式批次成绩列表，禁止后端猜默认批次。 */
export const teacherInternshipScores = (batchId) => {
  try {
    const value = requireBatch(batchId)
    return realRequest(`/mobile/teacher/internship/context/scores?batchId=${encodeURIComponent(value)}`)
  } catch (e) { return Promise.reject(e) }
}

/** 教师小程序：当前批次企业评价；创建绑定真实附件，审核与重交必须携带版本。 */
export const teacherInternshipEnterpriseEvals = (batchId) => {
  try {
    const value = requireBatch(batchId)
    return realRequest(`/mobile/teacher/internship/context/enterprise-evals?batchId=${encodeURIComponent(value)}`)
  } catch (e) { return Promise.reject(e) }
}
export const teacherInternshipEnterpriseEvalCreate = (body) =>
  realRequest('/mobile/teacher/internship/context/enterprise-evals', { method: 'POST', data: body || {} })
export const teacherInternshipEnterpriseEvalResubmit = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/enterprise-evals/${evalId}/resubmit`, { method: 'POST', data: body || {} })
export const teacherInternshipEnterpriseEvalReview = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/enterprise-evals/${evalId}/review`, { method: 'POST', data: body || {} })

/** 学生本人：所选批次实习摘要；多条进行中记录时禁止服务端猜测。 */
export const studentInternshipDashboard = (batchId = '') =>
  realRequest(optionalBatch('/mobile/internship/context/my', batchId))

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

/** 学生安全教育：所选批次课程、详情、开始、提交、承诺。 */
export const studentInternshipSafetyCourses = (batchId = '') =>
  realRequest(optionalBatch('/mobile/internship/context/safety/courses', batchId))
export const studentInternshipSafetyCompletions = (batchId = '') =>
  realRequest(optionalBatch('/mobile/internship/context/safety/completions', batchId))
export const studentInternshipSafetyCourseDetail = (courseId) =>
  realRequest(`/mobile/internship/safety/courses/${courseId}/detail`)
export const studentInternshipSafetyStart = (courseId) =>
  realRequest(`/mobile/internship/safety/courses/${courseId}/start`, { method: 'POST' })
export const studentInternshipSafetySubmit = (courseId, body) =>
  realRequest(`/mobile/internship/safety/courses/${courseId}/submit`, { method: 'POST', data: body || {} })
export const studentInternshipSafetyCommit = (completionId, body) =>
  realRequest(`/mobile/internship/safety/completions/${completionId}/commit`, { method: 'POST', data: body || {} })
