/**
 * 消息中心发布端 API。
 */
import { request } from '@/services/http'

export function createCampaign(body) {
  return request('/admin/message-campaigns', { method: 'POST', body })
}

export function fetchCampaigns(params = {}) {
  return request('/admin/message-campaigns', { params })
}

export function fetchCampaign(campaignId) {
  return request(`/admin/message-campaigns/${campaignId}`)
}

export function previewAudience(body) {
  return request('/admin/message-campaigns/audience-preview', { method: 'POST', body })
}

export function publishCampaign(campaignId, body) {
  return request(`/admin/message-campaigns/${campaignId}/publish`, { method: 'POST', body })
}

export function withdrawCampaign(campaignId, body) {
  return request(`/admin/message-campaigns/${campaignId}/withdraw`, { method: 'POST', body })
}

export function approveCampaign(campaignId, body) {
  return request(`/admin/message-campaigns/${campaignId}/approve`, { method: 'POST', body })
}

export function returnCampaign(campaignId, body) {
  return request(`/admin/message-campaigns/${campaignId}/return`, { method: 'POST', body })
}

export function fetchCampaignStatistics(params = {}) {
  return request('/admin/message-campaigns/statistics', { params })
}

export function fetchMessageTemplates(params = {}) {
  return request('/admin/message-campaigns/templates', { params })
}

export function fetchMessageSettings() {
  return request('/admin/message-campaigns/settings')
}

export function fetchActionKeys() {
  return request('/admin/message-campaigns/action-keys')
}

export function setMessagePreference(body) {
  return request('/admin/message-campaigns/settings/preference', { method: 'POST', body })
}

export function fetchDeadLetters(params = {}) {
  return request('/admin/message-campaigns/ops/dead-letters', { params })
}

export function retryDeadLetter(id, body = {}) {
  return request(`/admin/message-campaigns/ops/dead-letters/${id}/retry`, { method: 'POST', body })
}

export function fetchReconcile() {
  return request('/admin/message-campaigns/ops/reconcile')
}

export function fetchCampaignRecipients(campaignId, params = {}) {
  return request(`/admin/message-campaigns/${campaignId}/recipients`, { params })
}

export function exportCampaignRecipients(campaignId, body = {}) {
  return request(`/admin/message-campaigns/${campaignId}/export-recipients`, { method: 'POST', body })
}

export function addCampaignAttachment(campaignId, body) {
  return request(`/admin/message-campaigns/${campaignId}/attachments`, { method: 'POST', body })
}

export function createMessageTemplate(body) {
  return request('/admin/message-campaigns/templates', { method: 'POST', body })
}

export function updateMessageTemplate(templateId, body) {
  return request(`/admin/message-campaigns/templates/${templateId}`, { method: 'PATCH', body })
}

export function sendCampaignChannel(campaignId, channel) {
  return request(`/admin/message-campaigns/${campaignId}/channels/${channel}/send`, { method: 'POST' })
}
