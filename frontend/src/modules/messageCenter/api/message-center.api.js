/**
 * 消息中心 API（管理端收件面）。
 * 后端：/api/v1/admin/messages*
 * request() 已解包 data；失败如实抛错，页面显示错误态。
 */
import { request } from '@/services/http'

export function fetchMessages(params = {}) {
  return request('/admin/messages', { params })
}

export function fetchMessageCount() {
  return request('/admin/messages/count')
}

export function fetchMessageCategories() {
  return request('/admin/messages/categories')
}

export function fetchMessageDetail(messageId) {
  return request(`/admin/messages/${messageId}`)
}

export function markMessageRead(messageId) {
  return request(`/admin/messages/${messageId}/read`, { method: 'POST' })
}

export function markMessagesReadAll(params = {}) {
  return request('/admin/messages/read-all', { method: 'POST', params })
}

export function ackMessage(messageId) {
  return request(`/admin/messages/${messageId}/receipt`, { method: 'POST' })
}
