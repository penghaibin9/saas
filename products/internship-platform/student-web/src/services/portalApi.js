/** Standalone 学生 PC 岗位实习专用 API。禁止引入教务/学工/毕设业务。 */
import { request } from './request'

const q = (obj = {}) => {
  const params = new URLSearchParams()
  Object.entries(obj).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value))
  })
  const text = params.toString()
  return text ? '?' + text : ''
}

export const portalApi = {
  login: (loginName, password, tenantCode, challenge = {}) =>
    request('/auth/login', {
      method: 'POST',
      auth: false,
      body: {
        ...(challenge.identifierType
          ? { identifierType: challenge.identifierType, identifier: loginName }
          : { loginName }),
        password,
        ...(tenantCode ? { tenantCode } : {}),
        clientType: 'PC',
        captchaId: challenge.captchaId || undefined,
        captchaCode: challenge.captchaCode || undefined,
        clientNonce: challenge.clientNonce || undefined
      }
    }),
  me: () => request('/auth/me'),
  portalConfig: () => request('/mobile/me/portal-config'),

  internshipMy: (batchId = '') =>
    request('/portal/internship/my' + q({ batchId })),
  internshipAgreementPrint: (body) =>
    request('/portal/internship/agreement/print', { method: 'POST', body }),
  internshipScoreAppealStatus: (params = {}) =>
    request('/portal/internship/score/appeal' + q(params)),
  internshipScoreAppeal: (body) =>
    request('/portal/internship/score/appeal', { method: 'POST', body }),
  internshipCheckin: (body) =>
    request('/portal/internship/checkin', { method: 'POST', body }),
  internshipIntentionMy: () =>
    request('/portal/internship/intention'),
  internshipIntentionSave: (body) =>
    request('/portal/internship/intention', { method: 'POST', body }),
  internshipIntentionSubmit: () =>
    request('/portal/internship/intention/submit', { method: 'POST' }),
  internshipIntentionWithdraw: () =>
    request('/portal/internship/intention/withdraw', { method: 'POST' }),
  internshipEnterprises: (city = '') =>
    request('/portal/internship/enterprises' + (city ? q({ city }) : '')),
  internshipHelp: (body) =>
    request('/portal/internship/help', { method: 'POST', body })
}

export default portalApi
