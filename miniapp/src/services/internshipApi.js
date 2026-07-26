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

export const teacherInternshipContext = () => realRequest('/mobile/teacher/internship/context')
export const teacherInternshipMyStudents = (batchId) => {
  try { const value = requireBatch(batchId); return realRequest(`/mobile/teacher/internship/my-students?batchId=${encodeURIComponent(value)}`) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipScores = (batchId) => {
  try { const value = requireBatch(batchId); return realRequest(`/mobile/teacher/internship/context/scores?batchId=${encodeURIComponent(value)}`) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipEnterpriseEvals = (batchId) => {
  try { const value = requireBatch(batchId); return realRequest(`/mobile/teacher/internship/context/enterprise-evals?batchId=${encodeURIComponent(value)}`) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipEnterpriseEvalCreate = (body) =>
  realRequest('/mobile/teacher/internship/context/enterprise-evals', { method: 'POST', data: body || {} })
export const teacherInternshipEnterpriseEvalResubmit = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/enterprise-evals/${evalId}/resubmit`, { method: 'POST', data: body || {} })
export const teacherInternshipEnterpriseEvalReview = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/enterprise-evals/${evalId}/review`, { method: 'POST', data: body || {} })

export const teacherInternshipStudentEvals = (batchId) => {
  try { const value = requireBatch(batchId); return realRequest(`/mobile/teacher/internship/context/student-evals?batchId=${encodeURIComponent(value)}`) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipStudentEvalDetail = (evalId) =>
  realRequest(`/mobile/teacher/internship/context/student-evals/${evalId}`)
export const teacherInternshipStudentEvalAdvisorComment = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/student-evals/${evalId}/advisor-comment`, { method: 'POST', data: body || {} })
export const teacherInternshipStudentEvalReview = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/student-evals/${evalId}/review`, { method: 'POST', data: body || {} })

/** 教师保险核验直接复用学校 PC 正式接口，权限、范围、版本契约完全同源。 */
export const teacherInternshipInsurancePending = (batchId) => {
  try {
    const value = requireBatch(batchId)
    return realRequest(`/internship/insurances?page=1&pageSize=100&status=PENDING_VERIFY&batchId=${encodeURIComponent(value)}`)
  } catch (e) { return Promise.reject(e) }
}
export const teacherInternshipInsuranceVerify = (insuranceId, body) =>
  realRequest(`/internship/insurances/${insuranceId}/verify`, { method: 'POST', data: body || {} })

export const studentInternshipDashboard = (batchId = '') =>
  realRequest(optionalBatch('/mobile/internship/context/my', batchId))
export const studentInternshipCompliance = (operation = 'ONBOARD', batchId = '') => {
  const query = [`operation=${encodeURIComponent(operation || 'ONBOARD')}`]
  if (batchId) query.push(`batchId=${encodeURIComponent(batchId)}`)
  return realRequest(`/mobile/internship/compliance/my?${query.join('&')}`)
}
export const studentInternshipConsents = (batchId = '') =>
  realRequest(optionalBatch('/mobile/internship/context/consents', batchId))
export const studentInternshipConsentDetail = (consentId) =>
  realRequest(`/mobile/internship/consents/${consentId}`)
export const studentInternshipConsentView = (consentId) =>
  realRequest(`/mobile/internship/consents/${consentId}/view`, { method: 'POST' })
export const studentInternshipConsentConfirm = (consentId, body) =>
  realRequest(`/mobile/internship/consents/${consentId}/confirm`, { method: 'POST', data: body || {} })
export const studentInternshipConsentReject = (consentId, body) =>
  realRequest(`/mobile/internship/consents/${consentId}/reject`, { method: 'POST', data: body || {} })

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

/** 学生正式实习申请：列表、草稿、提交、撤回全部使用显式版本。 */
export const studentInternshipApplications = () =>
  realRequest('/mobile/internship/context/applications')
export const studentInternshipApplicationSave = (body) =>
  realRequest('/mobile/internship/context/applications', { method: 'PUT', data: body || {} })
export const studentInternshipApplicationSubmit = (applicationId, expectedVersion) =>
  realRequest(`/mobile/internship/context/applications/${applicationId}/submit`, {
    method: 'POST', data: { expectedVersion }
  })
export const studentInternshipApplicationWithdraw = (applicationId, expectedVersion) =>
  realRequest(`/mobile/internship/context/applications/${applicationId}/withdraw`, {
    method: 'POST', data: { expectedVersion }
  })
