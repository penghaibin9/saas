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
