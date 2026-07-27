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

function batchPath(path, batchId) {
  const value = requireBatch(batchId)
  return `${path}${path.includes('?') ? '&' : '?'}batchId=${encodeURIComponent(value)}`
}

const enc = (value) => encodeURIComponent(String(value ?? ''))

// ── 教师岗位实习：权限与批次上下文 ──
export const teacherInternshipContext = () => realRequest('/mobile/teacher/internship/context')
export const teacherInternshipMyStudents = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/my-students', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipScores = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/scores', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipAgreements = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/agreements', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipEnterpriseEvals = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/enterprise-evals', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipEnterpriseEvalCreate = (body) =>
  realRequest('/mobile/teacher/internship/context/enterprise-evals', { method: 'POST', data: body || {} })
export const teacherInternshipEnterpriseEvalResubmit = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/enterprise-evals/${enc(evalId)}/resubmit`, { method: 'POST', data: body || {} })
export const teacherInternshipEnterpriseEvalReview = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/enterprise-evals/${enc(evalId)}/review`, { method: 'POST', data: body || {} })

export const teacherInternshipStudentEvals = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/student-evals', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipStudentEvalDetail = (evalId) =>
  realRequest(`/mobile/teacher/internship/context/student-evals/${enc(evalId)}`)
export const teacherInternshipStudentEvalAdvisorComment = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/student-evals/${enc(evalId)}/advisor-comment`, { method: 'POST', data: body || {} })
export const teacherInternshipStudentEvalReview = (evalId, body) =>
  realRequest(`/mobile/teacher/internship/context/student-evals/${enc(evalId)}/review`, { method: 'POST', data: body || {} })

export const teacherInternshipMakeups = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/makeups', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipMakeupEvidenceViewed = (makeupId) =>
  realRequest(`/mobile/teacher/internship/context/makeups/${enc(makeupId)}/evidence-viewed`, { method: 'POST' })
export const teacherInternshipMakeupReview = (makeupId, body) =>
  realRequest(`/mobile/teacher/internship/context/makeups/${enc(makeupId)}/review`, { method: 'POST', data: body || {} })

export const teacherInternshipLeaves = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/leaves', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipLeaveEvidenceViewed = (leaveId) =>
  realRequest(`/mobile/teacher/internship/context/leaves/${enc(leaveId)}/evidence-viewed`, { method: 'POST' })
export const teacherInternshipLeaveReview = (leaveId, body) =>
  realRequest(`/mobile/teacher/internship/context/leaves/${enc(leaveId)}/review`, { method: 'POST', data: body || {} })

export const teacherInternshipProcessReports = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/process-reports', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipProcessReportDetail = (reportId) =>
  realRequest(`/mobile/teacher/internship/context/process-reports/${enc(reportId)}`)
export const teacherInternshipProcessReportReview = (reportId, body) =>
  realRequest(`/mobile/teacher/internship/context/process-reports/${enc(reportId)}/review`, { method: 'POST', data: body || {} })

export const teacherInternshipPlanTasks = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/plan-tasks', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipPlanTaskReview = (progressId, body) =>
  realRequest(`/mobile/teacher/internship/context/plan-tasks/${enc(progressId)}/review`, { method: 'POST', data: body || {} })

export const teacherInternshipApplications = (batchId) => {
  try { return realRequest(batchPath('/mobile/teacher/internship/context/applications', batchId)) }
  catch (e) { return Promise.reject(e) }
}
export const teacherInternshipApplicationReview = (applicationId, body) =>
  realRequest(`/mobile/teacher/internship/context/applications/${enc(applicationId)}/review`, { method: 'POST', data: body || {} })

/** 教师保险核验直接复用学校 PC 正式接口，权限、范围、版本契约完全同源。 */
export const teacherInternshipInsurancePending = (batchId) => {
  try {
    const value = requireBatch(batchId)
    return realRequest(`/internship/insurances?page=1&pageSize=100&status=PENDING_VERIFY&batchId=${encodeURIComponent(value)}`)
  } catch (e) { return Promise.reject(e) }
}
export const teacherInternshipInsuranceVerify = (insuranceId, body) =>
  realRequest(`/internship/insurances/${enc(insuranceId)}/verify`, { method: 'POST', data: body || {} })

// ── 学生岗位实习：当前批次权威流程 ──
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
  realRequest(`/mobile/internship/consents/${enc(consentId)}`)
export const studentInternshipConsentView = (consentId) =>
  realRequest(`/mobile/internship/consents/${enc(consentId)}/view`, { method: 'POST' })
export const studentInternshipConsentConfirm = (consentId, body) =>
  realRequest(`/mobile/internship/consents/${enc(consentId)}/confirm`, { method: 'POST', data: body || {} })
export const studentInternshipConsentReject = (consentId, body) =>
  realRequest(`/mobile/internship/consents/${enc(consentId)}/reject`, { method: 'POST', data: body || {} })

export const studentInternshipSafetyCourses = (batchId = '') =>
  realRequest(optionalBatch('/mobile/internship/context/safety/courses', batchId))
export const studentInternshipSafetyCompletions = (batchId = '') =>
  realRequest(optionalBatch('/mobile/internship/context/safety/completions', batchId))
export const studentInternshipSafetyCourseDetail = (courseId) =>
  realRequest(`/mobile/internship/safety/courses/${enc(courseId)}/detail`)
export const studentInternshipSafetyStart = (courseId) =>
  realRequest(`/mobile/internship/safety/courses/${enc(courseId)}/start`, { method: 'POST' })
export const studentInternshipSafetySubmit = (courseId, body) =>
  realRequest(`/mobile/internship/safety/courses/${enc(courseId)}/submit`, { method: 'POST', data: body || {} })
export const studentInternshipSafetyCommit = (completionId, body) =>
  realRequest(`/mobile/internship/safety/completions/${enc(completionId)}/commit`, { method: 'POST', data: body || {} })

export const studentInternshipApplications = () =>
  realRequest('/mobile/internship/context/applications')
export const studentInternshipApplicationSave = (body) =>
  realRequest('/mobile/internship/context/applications', { method: 'PUT', data: body || {} })
export const studentInternshipApplicationSubmit = (applicationId, expectedVersion) =>
  realRequest(`/mobile/internship/context/applications/${enc(applicationId)}/submit`, {
    method: 'POST', data: { expectedVersion }
  })
export const studentInternshipApplicationWithdraw = (applicationId, expectedVersion) =>
  realRequest(`/mobile/internship/context/applications/${enc(applicationId)}/withdraw`, {
    method: 'POST', data: { expectedVersion }
  })

export const studentInternshipLeaves = () =>
  realRequest('/mobile/internship/context/leaves')
export const studentInternshipLeaveApply = (body) =>
  realRequest('/mobile/internship/context/leaves', { method: 'POST', data: body || {} })
export const studentInternshipLeaveWithdraw = (leaveId, expectedVersion) =>
  realRequest(`/mobile/internship/context/leaves/${enc(leaveId)}/withdraw`, {
    method: 'POST', data: { expectedVersion }
  })
export const studentInternshipLeaveReturn = (leaveId, body) =>
  realRequest(`/mobile/internship/context/leaves/${enc(leaveId)}/return`, { method: 'POST', data: body || {} })

export const studentInternshipMakeups = () =>
  realRequest('/mobile/internship/context/makeups')
export const studentInternshipMakeupApply = (body) =>
  realRequest('/mobile/internship/context/makeups', { method: 'POST', data: body || {} })
export const studentInternshipMakeupWithdraw = (makeupId, expectedVersion) =>
  realRequest(`/mobile/internship/context/makeups/${enc(makeupId)}/withdraw`, {
    method: 'POST', data: { expectedVersion }
  })

export const studentInternshipPlan = () =>
  realRequest('/mobile/internship/context/plan')
export const studentInternshipPlanAcknowledge = (body) =>
  realRequest('/mobile/internship/context/plan/acknowledge', { method: 'POST', data: body || {} })
export const studentInternshipPlanTasks = () =>
  realRequest('/mobile/internship/context/plan/tasks')
export const studentInternshipPlanTaskSubmit = (sortOrder, body) =>
  realRequest(`/mobile/internship/context/plan/tasks/${enc(sortOrder)}/submit`, { method: 'POST', data: body || {} })

export const studentInternshipAgreements = () =>
  realRequest('/mobile/internship/context/agreements')
export const studentInternshipAgreementDetail = (agreementId) =>
  realRequest(`/mobile/internship/context/agreements/${enc(agreementId)}`)
export const studentInternshipAgreementConfirm = (agreementId, body) =>
  realRequest(`/mobile/internship/context/agreements/${enc(agreementId)}/confirm`, { method: 'POST', data: body || {} })
