/**
 * Workflow Provider —— 页面唯一数据门面。
 * 数据流：页面 → 本 provider → api(mock|real) → contract。
 * 当前默认 mock；接真实后端时仅将 impl 换为 workflow.api.real.example 的实现，页面零改动。
 */
import * as mockApi from '../api/workflow.api.mock'

const impl = mockApi

export function getWorkflowOverview() {
  return impl.getWorkflowOverview()
}
export function getProcessTemplates(params) {
  return impl.getProcessTemplates(params)
}
export function getProcessTemplateDetail(id) {
  return impl.getProcessTemplateDetail(id)
}
export function updateProcessTemplateStatus(id, status) {
  return impl.updateProcessTemplateStatus(id, status)
}
export function getApprovalTasks(params) {
  return impl.getApprovalTasks(params)
}
export function getApprovalTaskDetail(id) {
  return impl.getApprovalTaskDetail(id)
}
export function approveTask(id, payload) {
  return impl.approveTask(id, payload)
}
export function rejectTask(id, payload) {
  return impl.rejectTask(id, payload)
}
export function withdrawTask(id, payload) {
  return impl.withdrawTask(id, payload)
}
export function getProcessInstances(params) {
  return impl.getProcessInstances(params)
}
export function getProcessInstanceDetail(id) {
  return impl.getProcessInstanceDetail(id)
}
export function getRoles(params) {
  return impl.getRoles(params)
}
export function getRoleDetail(id) {
  return impl.getRoleDetail(id)
}
export function updateRolePermissions(id, payload) {
  return impl.updateRolePermissions(id, payload)
}
export function getPermissions(params) {
  return impl.getPermissions(params)
}
export function updatePermissionStatus(id, status) {
  return impl.updatePermissionStatus(id, status)
}
export function getAuditLogs(params) {
  return impl.getAuditLogs(params)
}
export function getPermissionContext() {
  return impl.getPermissionContext()
}

/* ---- mock 专用（licenseContext 预留演示；接真实授权中心后移除） ---- */
export function setLicenseViewState(state) {
  return impl.setLicenseViewState(state)
}
export function getLicenseViewState() {
  return impl.getLicenseViewState()
}
