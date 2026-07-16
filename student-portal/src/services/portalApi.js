/**
 * 学生 PC 门户 · API 门面。只暴露门户允许调用的接口（严格边界）。
 * 允许：/auth/login、/mobile/me/portal-config、/mobile/me/{overview,profile,todos,messages}、/mobile/{domain}/my。
 * 禁止：/admin/*、/students、/students/{id}、/approvals/*、/todos 全量、/auth/mock-login。
 */
import { downloadFile, request, uploadFile } from './request'

export const portalApi = {
  // 账号密码登录（与小程序同一套后端账号；返回 accessToken + user + currentRole）
  login: (loginName, password) =>
    request('/auth/login', { method: 'POST', auth: false, body: { loginName, password } }),

  portalConfig: () => request('/mobile/me/portal-config'),
  overview: () => request('/mobile/me/overview'),
  profile: () => request('/mobile/me/profile'),
  todos: () => request('/mobile/me/todos'),
  messages: () => request('/mobile/me/messages'),

  // 各业务域「我的」数据（本人）：orientation/campus-service/academic/internship/graduation/employment
  domainMy: (domain) => request(`/mobile/${domain}/my`),

  // 毕业设计学生工作台：均为 /mobile/graduation 下的「本人」接口。
  graduationTaskbook: () => request('/mobile/graduation/taskbook'),
  confirmGraduationTaskbook: () => request('/mobile/graduation/taskbook/confirm', { method: 'POST' }),
  graduationProposal: () => request('/mobile/graduation/proposal'),
  submitGraduationProposal: (body) => request('/mobile/graduation/proposal', { method: 'POST', body }),
  graduationMidterm: () => request('/mobile/graduation/midterm'),
  rectifyGraduationMidterm: (content) => request('/mobile/graduation/midterm/rectify', { method: 'POST', body: { content } }),
  graduationFinal: () => request('/mobile/graduation/final'),
  submitGraduationFinal: (body) => request('/mobile/graduation/final', { method: 'POST', body }),
  graduationDefense: () => request('/mobile/graduation/defense'),
  graduationGrade: () => request('/mobile/graduation/grade'),
  graduationArchive: () => request('/mobile/graduation/archive'),
  graduationActiveRound: () => request('/mobile/graduation/active-round'),
  graduationTopics: (batchId) => request(`/mobile/graduation/topics${batchId ? `?batchId=${encodeURIComponent(batchId)}` : ''}`),
  submitGraduationChoices: (roundId, choices) => request('/mobile/graduation/choices', { method: 'POST', body: { roundId, choices } }),
  uploadGraduationMaterial: (file) => uploadFile('/files/upload?bizType=GRADUATION_MATERIAL', file),
  downloadGraduationMaterial: (fileId, fileName) => downloadFile(`/mobile/graduation/materials/${encodeURIComponent(fileId)}/download`, fileName)
}

export default portalApi
