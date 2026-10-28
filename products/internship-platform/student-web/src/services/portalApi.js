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

const intentionPath = '/mobile/internship/context/intention'
function intentionView(data, context) {
  if (!context?.batchId || !context?.internshipId || data?.hasData !== true
    || String(data.batchId) !== String(context.batchId) || String(data.internshipId) !== String(context.internshipId)) {
    throw new Error('意向不属于当前实习，请重新读取')
  }
  const row = data.intention
  if (row && (!/^\d+$/.test(String(row.id || '')) || String(row.recordId) !== String(context.internshipId)
    || String(row.batchId) !== String(context.batchId) || !Number.isInteger(row.version) || row.version < 0)) {
    throw new Error('意向原单或版本不完整，请重新读取')
  }
  const labels = { DRAFT: '草稿', SUBMITTED: '已提交', WITHDRAWN: '已撤回' }
  const known = !row || Object.hasOwn(labels, row.status)
  return { ...data,
    intention: row ? { ...row, statusLabel: labels[row.status] || '状态待学校核对' } : null,
    canEdit: known && data.canEdit === true, canSubmit: known && data.canSubmit === true,
    canWithdraw: known && data.canWithdraw === true, canCreateNew: known && data.canCreateNew === true,
    readOnlyReason: data.readOnlyReason === '' ? '' : /[\u4e00-\u9fff]/.test(data.readOnlyReason || '') ? data.readOnlyReason : '当前暂不能办理，请重新读取或联系学校核对。' }
}
async function intentionRequest(path, options, context) {
  try { return intentionView(await request(path, options), context) }
  catch (error) {
    const code = error?.bizCode || error?.code
    const message = code === 'DATA_CONFLICT' ? '意向版本或办理条件已变化，未提交内容已保留，请重新读取并核对。'
      : code === 'NO_PERMISSION' || error?.status === 403 ? '当前账号无权办理此意向，请联系学校核对。'
        : code === 'VALIDATION_ERROR' ? '意向内容或所选岗位不符合要求，请核对后重试。'
          : '意向暂时无法读取或保存，未提交内容仍保留，请重试。'
    throw Object.assign(new Error(message), error, { message })
  }
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
  messages: (params = {}) => request('/mobile/me/messages' + q(params)),
  messageCount: () => request('/mobile/me/messages/count'),
  messageDetail: (id) => request('/mobile/me/messages/' + encodeURIComponent(String(id))),
  readMessage: (id) => request('/mobile/me/messages/' + encodeURIComponent(String(id)) + '/read', { method: 'POST' }),

  internshipMy: (batchId = '') =>
    request('/portal/internship/my' + q({ batchId })),
  internshipAgreementPrint: (body) =>
    request('/portal/internship/agreement/print', { method: 'POST', body }),
  internshipScoreAppealStatus: (params = {}) =>
    request('/portal/internship/score/appeal' + q(params)),
  internshipScoreAppeal: (body) =>
    request('/portal/internship/score/appeal', { method: 'POST', body }),
  internshipCheckin: (body) =>
    request('/mobile/internship/checkin' + q({ batchId: body.batchId }), { method: 'POST', body }),
  internshipIntentionMy: (context) =>
    intentionRequest(intentionPath + q(context), {}, context),
  internshipIntentionSave: (body) =>
    intentionRequest(intentionPath, { method: 'PUT', body }, body),
  internshipIntentionSubmit: (body) =>
    intentionRequest(intentionPath + '/submit', { method: 'POST', body }, body),
  internshipIntentionWithdraw: (body) =>
    intentionRequest(intentionPath + '/withdraw', { method: 'POST', body }, body),
  internshipHelpMy: (context) =>
    request('/mobile/internship/context/help' + q(context)),
  internshipHelp: (body) =>
    request('/mobile/internship/context/help', { method: 'POST', body })
}

export default portalApi
