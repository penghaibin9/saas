/** Teacher Miniapp V3 T9: real-only message inbox API. */
import { realRequest } from './request'

function query(params = {}) {
  const parts = []
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
  })
  return parts.length ? `?${parts.join('&')}` : ''
}

export const getTeacherMessagesPage = ({ tab = 'system', cursor = '', pageSize = 20, q = '' } = {}) =>
  realRequest('/mobile/performance/teacher/messages-page' + query({ tab, cursor, pageSize, q }))

export const getTeacherMessageBadges = () =>
  realRequest('/mobile/performance/teacher/messages-badges')

export const getTeacherMessageDetail = (messageId) =>
  realRequest('/mobile/performance/teacher/messages/' + encodeURIComponent(String(messageId || '')))

export const markTeacherMessageRead = (messageId) =>
  realRequest('/mobile/teacher/messages/' + encodeURIComponent(String(messageId || '')) + '/read', { method: 'POST' })

export const ackTeacherMessageReceipt = (messageId) =>
  realRequest('/mobile/performance/teacher/messages/' + encodeURIComponent(String(messageId || '')) + '/receipt', { method: 'POST' })
