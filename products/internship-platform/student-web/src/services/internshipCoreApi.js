/** 学生 PC 岗位实习核心写流程独立门面。 */
import { downloadFile, request, uploadFile } from './request'

const encode = (value) => encodeURIComponent(String(value ?? ''))
const contextQuery = ({ batchId, internshipId }) =>
  `?batchId=${encode(batchId)}&internshipId=${encode(internshipId)}`

export const internshipCoreApi = {
  materialRequirements(context) {
    return request(`/mobile/internship/context/material-requirements${contextQuery(context)}`)
  },
  submitMaterial(id, body) {
    return request(`/mobile/internship/context/material-requirements/${encode(id)}/submit`, { method: 'POST', body })
  },
  materialTemplate(context, id, filename, templateVersionId) {
    return downloadFile(`/mobile/internship/context/material-requirements/${encode(id)}/template/download${contextQuery(context)}&templateVersionId=${encode(templateVersionId)}`,filename)
  },
  formalDocuments(context) {
    const batchId = String(context?.batchId || '').trim()
    const internshipId = String(context?.internshipId || '').trim()
    if (!batchId || !internshipId) return Promise.reject(new Error('实习上下文不完整'))
    return request(`/portal/internship/context/formal-documents?batchId=${encode(batchId)}&internshipId=${encode(internshipId)}`)
  },
  generateFormalDocument(context, documentType) {
    return request('/portal/internship/context/formal-documents/generate', {
      method: 'POST',
      body: { ...context, documentType }
    })
  },
  formalDocumentPdf(context, documentId) {
    const batchId = String(context?.batchId || '').trim()
    const internshipId = String(context?.internshipId || '').trim()
    if (!batchId || !internshipId) return Promise.reject(new Error('实习上下文不完整'))
    return request(
      `/portal/internship/context/formal-documents/${encode(documentId)}/pdf?batchId=${encode(batchId)}&internshipId=${encode(internshipId)}`
    )
  },
  attendance(context, timezoneName = '') {
    const batchId = String(context?.batchId || '').trim()
    if (!batchId) return Promise.reject(new Error('请先选择实习批次'))
    const params = new URLSearchParams({ batchId })
    if (timezoneName) params.set('timezoneName', timezoneName)
    return request(`/portal/internship/context/attendance?${params.toString()}`)
  },
  attendancePdf(context, timezoneName = '') {
    const batchId = String(context?.batchId || '').trim()
    if (!batchId) return Promise.reject(new Error('请先选择实习批次'))
    const params = new URLSearchParams({ batchId })
    if (timezoneName) params.set('timezoneName', timezoneName)
    return request(`/portal/internship/context/attendance/pdf?${params.toString()}`)
  },
  notices(context) {
    const batchId = String(context?.batchId || '').trim()
    if (!batchId) return Promise.reject(new Error('请先选择实习批次'))
    return request(`/portal/internship/context/notices?batchId=${encode(batchId)}`)
  },
  async applications(context) {
    return request(`/portal/internship/context/applications${contextQuery(context)}`)
  },
  async saveApplication(body) {
    return request('/portal/internship/context/applications', { method: 'PUT', body })
  },
  submitApplication(id, body) {
    return request(`/portal/internship/context/applications/${encode(id)}/submit`, {
      method: 'POST', body
    })
  },
  withdrawApplication(id, body) {
    return request(`/portal/internship/context/applications/${encode(id)}/withdraw`, {
      method: 'POST', body
    })
  },
  leaves(context) {
    return request(`/portal/internship/context/leaves${contextQuery(context)}`)
  },
  leaveDetail(context, id) {
    return request(`/portal/internship/context/leaves/${encode(id)}${contextQuery(context)}`)
  },
  resubmitLeave(id, body) {
    return request(`/portal/internship/context/leaves/${encode(id)}/resubmit`, { method: 'POST', body })
  },
  applyLeave(body) {
    return request('/portal/internship/context/leaves', { method: 'POST', body })
  },
  withdrawLeave(id, body) {
    return request(`/portal/internship/context/leaves/${encode(id)}/withdraw`, {
      method: 'POST', body
    })
  },
  returnLeave(id, body) {
    return request(`/portal/internship/context/leaves/${encode(id)}/return`, {
      method: 'POST', body
    })
  },
  makeups(context) {
    return request(`/portal/internship/context/makeups${contextQuery(context)}`)
  },
  applyMakeup(body) {
    return request('/portal/internship/context/makeups', { method: 'POST', body })
  },
  withdrawMakeup(id, body) {
    return request(`/portal/internship/context/makeups/${encode(id)}/withdraw`, {
      method: 'POST', body
    })
  },
  agreements(context) {
    return request(`/portal/internship/context/agreements${contextQuery(context)}`)
  },
  agreement(id) {
    return request(`/portal/internship/context/agreements/${encode(id)}`)
  },
  confirmAgreement(id, body) {
    return request(`/portal/internship/context/agreements/${encode(id)}/confirm`, {
      method: 'POST', body
    })
  },
  agreementPdf(id, body) {
    return request(`/portal/internship/context/agreements/${encode(id)}/pdf`, {
      method: 'POST', body
    })
  },
  plans(context) {
    return request('/portal/internship/context/plans' + (context ? contextQuery(context) : ''))
  },
  plan(planId = '', context) {
    return request('/portal/internship/context/plan' + (context ? contextQuery(context) : '') + (planId ? `${context ? '&' : '?'}planId=${encode(planId)}` : ''))
  },
  planTasks(planId = '', context) {
    return request('/portal/internship/context/plan/tasks' + (context ? contextQuery(context) : '') + (planId ? `${context ? '&' : '?'}planId=${encode(planId)}` : ''))
  },
  acknowledgePlan(body) {
    return request('/portal/internship/context/plan/acknowledge', {
      method: 'POST', body
    })
  },
  submitPlanTask(sortOrder, body) {
    return request(`/portal/internship/context/plan/tasks/${encode(sortOrder)}/submit`, {
      method: 'POST', body
    })
  },
  uploadPlanTaskEvidence(file) {
    return uploadFile('/files?bizType=INTERNSHIP_PLAN_TASK', file)
  },
  changes(context, page = 1) {
    return request(`/portal/internship/context/changes${contextQuery(context)}&page=${encode(page)}&pageSize=20`)
  },
  changeTargets(context, changeType, keyword = '', page = 1) {
    return request(`/portal/internship/context/changes/target-positions${contextQuery(context)}&changeType=${encode(changeType)}&keyword=${encode(keyword)}&page=${encode(page)}&pageSize=20`)
  },
  applyChange(body) {
    return request('/portal/internship/context/changes', { method: 'POST', body })
  },
  resubmitChange(id, body) {
    return request(`/portal/internship/context/changes/${encode(id)}/resubmit`, { method: 'POST', body })
  },
  withdrawChange(id, body) {
    return request(`/portal/internship/context/changes/${encode(id)}/withdraw`, {
      method: 'POST', body
    })
  },
  reportPdf(context, reportKind, reportId) {
    const batchId = String(context?.batchId || '').trim()
    const internshipId = String(context?.internshipId || '').trim()
    if (!batchId || !internshipId) return Promise.reject(new Error('实习上下文不完整'))
    return request(
      `/portal/internship/context/reports/${encode(reportKind)}/${encode(reportId)}/pdf?batchId=${encode(batchId)}&internshipId=${encode(internshipId)}`
    )
  },
  reports(context, page = 1, pageSize = 20, reportType = '', focusReportId = '') {
    const params = new URLSearchParams({ page, pageSize })
    if (reportType) params.set('reportType', reportType)
    if (focusReportId) params.set('focusReportId', String(focusReportId))
    return request(`/portal/internship/context/reports${contextQuery(context)}&${params}`)
  },
  processReportDetail(context, id) {
    return request(`/portal/internship/context/reports/${encode(id)}${contextQuery(context)}`)
  },
  submitReport(body) {
    return request('/portal/internship/context/reports', { method: 'POST', body })
  },
  weeklyReports(context, page = 1, pageSize = 20, focusReportId = '') {
    const params = new URLSearchParams({ page, pageSize })
    if (focusReportId) params.set('focusReportId', String(focusReportId))
    return request(`/portal/internship/context/weekly-reports${contextQuery(context)}&${params}`)
  },
  weeklyReportDetail(context, id) {
    return request(`/portal/internship/context/weekly-reports/${encode(id)}${contextQuery(context)}`)
  },
  submitWeeklyReport(body) {
    return request('/portal/internship/context/weekly-reports', { method: 'POST', body })
  },
  positions(context, page = 1, keyword = '') {
    return request(`/portal/internship/context/applications/positions${contextQuery(context)}&page=${encode(page)}&pageSize=20&keyword=${encode(keyword)}`)
  },
  uploadApplicationEvidence(file) {
    return uploadFile('/files?bizType=INTERNSHIP_APPLICATION_EVIDENCE', file)
  },
  uploadInsurancePolicy(file) {
    return uploadFile('/files?bizType=INTERNSHIP_INSURANCE_POLICY', file)
  },
  uploadMakeupEvidence(file) {
    return uploadFile('/files?bizType=INTERNSHIP', file)
  },
  uploadLeaveEvidence(file) {
    return uploadFile('/files?bizType=INTERNSHIP', file)
  },
  insurance(params) {
    return request('/portal/internship/insurance' + contextQuery(params))
  },
  saveInsurance(body) {
    return request('/portal/internship/insurance', { method: 'POST', body })
  },
  selfEval(params = {}) {
    const query = new URLSearchParams(params).toString()
    return request(`/portal/internship/context/self-eval${query ? `?${query}` : ''}`)
  },
  submitSelfEval(body) {
    return request('/portal/internship/context/self-eval', { method: 'POST', body })
  }
}

export default internshipCoreApi
