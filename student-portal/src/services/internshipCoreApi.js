/** 学生 PC 岗位实习核心写流程独立门面。 */
import { request, uploadFile } from './request'

const encode = (value) => encodeURIComponent(String(value ?? ''))

export const internshipCoreApi = {
  applications() {
    return request('/portal/internship/context/applications')
  },
  saveApplication(body) {
    return request('/portal/internship/context/applications', { method: 'PUT', body })
  },
  submitApplication(id, expectedVersion) {
    return request(`/portal/internship/context/applications/${encode(id)}/submit`, {
      method: 'POST', body: { expectedVersion }
    })
  },
  withdrawApplication(id, expectedVersion) {
    return request(`/portal/internship/context/applications/${encode(id)}/withdraw`, {
      method: 'POST', body: { expectedVersion }
    })
  },
  leaves() {
    return request('/portal/internship/context/leaves')
  },
  applyLeave(body) {
    return request('/portal/internship/context/leaves', { method: 'POST', body })
  },
  withdrawLeave(id, expectedVersion) {
    return request(`/portal/internship/context/leaves/${encode(id)}/withdraw`, {
      method: 'POST', body: { expectedVersion }
    })
  },
  returnLeave(id, body) {
    return request(`/portal/internship/context/leaves/${encode(id)}/return`, {
      method: 'POST', body
    })
  },
  makeups() {
    return request('/portal/internship/context/makeups')
  },
  applyMakeup(body) {
    return request('/portal/internship/context/makeups', { method: 'POST', body })
  },
  withdrawMakeup(id, expectedVersion) {
    return request(`/portal/internship/context/makeups/${encode(id)}/withdraw`, {
      method: 'POST', body: { expectedVersion }
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
  acknowledgePlan(planVersion, expectedVersion) {
    return request('/portal/internship/context/plan/acknowledge', {
      method: 'POST', body: { planVersion, expectedVersion }
    })
  },
  positions(city = '') {
    const query = city ? `?city=${encode(city)}` : ''
    return request(`/portal/internship/enterprises${query}`)
  },
  uploadApplicationEvidence(file) {
    return uploadFile('/files/upload?bizType=INTERNSHIP_APPLICATION_EVIDENCE', file)
  },
  uploadInsurancePolicy(file) {
    return uploadFile('/files/upload?bizType=INTERNSHIP_INSURANCE_POLICY', file)
  },
  insurance() {
    return request('/portal/internship/insurance')
  },
  saveInsurance(body) {
    return request('/portal/internship/insurance', { method: 'POST', body })
  },
  selfEval() {
    return request('/portal/internship/self-eval')
  },
  submitSelfEval(body) {
    return request('/portal/internship/self-eval', { method: 'POST', body })
  }
}

export default internshipCoreApi
