import { realRequest } from './request'

const enc = encodeURIComponent

export const teacherEmploymentV3Api = {
  overview() {
    return realRequest('/teacher-mobile/employment/overview')
  },
  recommend(studentId, body) {
    return realRequest(`/teacher-mobile/employment/students/${enc(String(studentId || ''))}/recommendations`, {
      method: 'POST', data: body
    })
  },
  verification(studentId) {
    return realRequest(`/teacher-mobile/employment/students/${enc(String(studentId || ''))}/verification`)
  },
  bindMaterialEvidence(materialId, body) {
    return realRequest(`/teacher-mobile/employment/materials/${enc(String(materialId || ''))}/evidence`, {
      method: 'POST', data: body
    })
  },
  reviewVerification(verificationId, body) {
    return realRequest(`/teacher-mobile/employment/verifications/${enc(String(verificationId || ''))}/review`, {
      method: 'POST', data: body
    })
  }
}

export default teacherEmploymentV3Api
