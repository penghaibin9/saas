/**
 * Workflow 真实 API 示例（未启用 —— 页面与 provider 默认仍走 mock）。
 * 接后端时：provider 将 impl 切换为本文件导出；路径/方法与 workflow.contract.js 逐一对齐。
 * 依赖统一 http client（P11 引入），此处以 fetch 形式示例。
 */
import { WORKFLOW_API_CONTRACT as C } from './workflow.contract'

async function request(path, { method = 'GET', params, body } = {}) {
  const qs = params
    ? '?' +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== '')
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
        .join('&')
    : ''
  const res = await fetch(`${path}${qs}`, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined
  })
  // 统一响应包裹 { code, message, data, timestamp, requestId }
  return res.json()
}

const withId = (tpl, id) => tpl.replace('{id}', encodeURIComponent(id))

export const getWorkflowOverview = () => request(C.getWorkflowOverview.path)
export const getProcessTemplates = (params) => request(C.getProcessTemplates.path, { params })
export const getProcessTemplateDetail = (id) => request(withId(C.getProcessTemplateDetail.path, id))
export const updateProcessTemplateStatus = (id, status) =>
  request(withId(C.updateProcessTemplateStatus.path, id), { method: 'PATCH', body: { status } })
export const getApprovalTasks = (params) => request(C.getApprovalTasks.path, { params })
export const getApprovalTaskDetail = (id) => request(withId(C.getApprovalTaskDetail.path, id))
export const approveTask = (id, payload) =>
  request(withId(C.approveTask.path, id), { method: 'POST', body: payload })
export const rejectTask = (id, payload) =>
  request(withId(C.rejectTask.path, id), { method: 'POST', body: payload })
export const withdrawTask = (id, payload) =>
  request(withId(C.withdrawTask.path, id), { method: 'POST', body: payload })
export const getProcessInstances = (params) => request(C.getProcessInstances.path, { params })
export const getProcessInstanceDetail = (id) => request(withId(C.getProcessInstanceDetail.path, id))
export const getRoles = (params) => request(C.getRoles.path, { params })
export const getRoleDetail = (id) => request(withId(C.getRoleDetail.path, id))
export const updateRolePermissions = (id, payload) =>
  request(withId(C.updateRolePermissions.path, id), { method: 'PUT', body: payload })
export const getPermissions = (params) => request(C.getPermissions.path, { params })
export const updatePermissionStatus = (id, status) =>
  request(withId(C.updatePermissionStatus.path, id), { method: 'PATCH', body: { status } })
export const getAuditLogs = (params) => request(C.getAuditLogs.path, { params })
export const getPermissionContext = () => request(C.getPermissionContext.path)
