/** 学生 PC 岗位实习核心写流程独立门面。 */
import { request, uploadFile } from './request'

const encode = (value) => encodeURIComponent(String(value ?? ''))
const contextQuery = ({ batchId, internshipId }) =>
  `?batchId=${encode(batchId)}&internshipId=${encode(internshipId)}`

function decorateLeaveReviewFeedback(data) {
  const decorate = (item) => {
    if (!item || item.status !== 'REJECTED') return item
    const reviewComment = String(item.reviewComment || '').trim()
    if (!reviewComment) return item
    const reason = String(item.reason || '').trim()
    return {
      ...item,
      reason: `${reason}${reason ? ' · ' : ''}驳回原因：${reviewComment}`
    }
  }
  if (Array.isArray(data)) return data.map(decorate)
  if (Array.isArray(data?.items)) return { ...data, items: data.items.map(decorate) }
  if (Array.isArray(data?.list)) return { ...data, list: data.list.map(decorate) }
  return data
}

export const internshipCoreApi = {
  applications(context) {
    return request(`/portal/internship/context/applications${contextQuery(context)}`)
  },
  saveApplication(body) {
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
  async leaves(context) {
    const data = await request(`/portal/internship/context/leaves${contextQuery(context)}`)
    return decorateLeaveReviewFeedback(data)
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
  agreements() {
    return request('/portal/internship/context/agreements')
  },
  agreement(id) {
    return request(`/portal/internship/context/agreements/${encode(id)}`)
  },
  confirmAgreement(id, body) {
    return request(`/portal/internship/context/agreements/${encode(id)}/confirm`, {
      method: 'POST', body
    })
  },
  plan() {
    return request('/portal/internship/context/plan')
  },
  acknowledgePlan(body) {
    return request('/portal/internship/context/plan/acknowledge', {
      method: 'POST', body
    })
  },
  changes(context) {
    return request(`/portal/internship/context/changes${contextQuery(context)}`)
  },
  applyChange(body) {
    return request('/portal/internship/context/changes', { method: 'POST', body })
  },
  withdrawChange(id, body) {
    return request(`/portal/internship/context/changes/${encode(id)}/withdraw`, {
      method: 'POST', body
    })
  },
  reports(context) {
    return request(`/portal/internship/context/reports${contextQuery(context)}`)
  },
  submitReport(body) {
    return request('/portal/internship/context/reports', { method: 'POST', body })
  },
  weeklyReports(context) {
    return request(`/portal/internship/context/weekly-reports${contextQuery(context)}`)
  },
  submitWeeklyReport(body) {
    return request('/portal/internship/context/weekly-reports', { method: 'POST', body })
  },
  positions(city = '') {
    const query = city ? `?city=${encode(city)}` : ''
    return request(`/portal/internship/enterprises${query}`)
  },
  uploadApplicationEvidence(file) {
    return uploadFile('/files?bizType=INTERNSHIP_APPLICATION_EVIDENCE', file)
  },
  uploadInsurancePolicy(file) {
    return uploadFile('/files?bizType=INTERNSHIP_INSURANCE_POLICY', file)
  },
  insurance() {
    return request('/portal/internship/insurance')
  },
  saveInsurance(body) {
    return request('/portal/internship/insurance', { method: 'POST', body })
  },
  selfEval() {
    return request('/portal/internship/context/self-eval')
  },
  submitSelfEval(body) {
    return request('/portal/internship/context/self-eval', { method: 'POST', body })
  }
}

export default internshipCoreApi
