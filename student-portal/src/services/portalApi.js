/**
 * 学生 PC 门户 · API 门面。只暴露门户允许调用的接口（严格边界）。
 * 允许：/auth/login、/mobile/me/portal-config、/mobile/me/{overview,profile,todos,messages}、/mobile/{domain}/my。
 * 禁止：/admin/*、/students、/students/{id}、/approvals/*、/todos 全量、/auth/mock-login。
 */
import { request } from './request'

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
  domainMy: (domain) => request(`/mobile/${domain}/my`)
}

export default portalApi
