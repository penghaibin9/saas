import { request, setToken } from './request'

export const guardianApi = {
  requestOtp(phone) {
    return request('/portal/guardian/otp', {
      method: 'POST', auth: false, body: { phone }
    })
  },
  async login(phone, code) {
    const data = await request('/portal/guardian/login', {
      method: 'POST', auth: false, body: { phone, code }
    })
    const token = data?.accessToken || data?.token || ''
    if (!token) throw new Error('家长登录响应缺少访问令牌')
    setToken(token)
    return data
  },
  students() {
    return request('/portal/guardian/students')
  },
  studentOverview(linkId) {
    return request(`/portal/guardian/students/${encodeURIComponent(linkId)}/overview`)
  },
  consents() {
    return request('/portal/guardian/internship/consents')
  },
  consentDetail(consentId, token) {
    return request(
      `/portal/guardian/internship/consents/${encodeURIComponent(consentId)}?token=${encodeURIComponent(token)}`
    )
  },
  confirmConsent(consentId, body) {
    return request(`/portal/guardian/internship/consents/${encodeURIComponent(consentId)}/confirm`, {
      method: 'POST', body
    })
  }
}

export default guardianApi
