/** 流程模板的真实接口。写操作始终走服务端，禁止 mock 成功。 */
import { request } from '@/services/http/client'

function nodeType(index, total) {
  if (index === 0) return 'START'
  if (index === total - 1) return 'END'
  return 'APPROVAL'
}

function status(value) {
  const code = String(value || '').toUpperCase()
  if (code === 'PENDING_CONFIRMATION') return 'DRAFT'
  if (code === 'ARCHIVED') return 'DISABLED'
  return code
}

function template(row = {}) {
  const nodes = Array.isArray(row.nodes) ? row.nodes : []
  return {
    templateId: String(row.id || ''),
    templateCode: String(row.workflowCode || ''),
    templateName: String(row.name || ''),
    moduleCode: String(row.sourceModule || 'WORKFLOW').toUpperCase(),
    businessType: String(row.bizType || ''),
    version: String(row.definitionVersion || '1'),
    rowVersion: Number(row.rowVersion || 0),
    status: status(row.status),
    rawStatus: String(row.status || ''),
    publishedAt: row.policyConfirmed ? row.updatedAt : '',
    updatedAt: row.updatedAt || '',
    updatedBy: row.updatedBy || '学校管理员',
    draftOfWorkflowCode: row.draftOfWorkflowCode || '',
    nodes: nodes.map((node, index) => ({
      nodeId: node.nodeCode || `NODE_${index + 1}`,
      nodeCode: node.nodeCode || `NODE_${index + 1}`,
      nodeName: node.name || '',
      nodeType: nodeType(index, nodes.length),
      candidateRoles: node.role ? [node.role] : [],
      allowReject: true,
      allowWithdraw: index === 0,
      allowTransfer: true,
      requireComment: false,
      commentMinLength: 0,
      nextNodeIds: index < nodes.length - 1 ? [nodes[index + 1].nodeCode || `NODE_${index + 2}`] : [],
      sla: Number(node.sla || 48)
    }))
  }
}

function response(data, message = '操作成功') {
  return { code: 0, data, message }
}

export async function getProcessTemplates(params = {}) {
  const data = await request('/approvals/templates', {
    params: {
      page: params.page || 1,
      pageSize: params.pageSize || 100,
      keyword: params.keyword || undefined,
      bizType: params.businessType || undefined,
      status: params.status === 'DISABLED' ? 'VOIDED' : params.status || undefined
    }
  })
  return response({ list: (data.items || []).map(template), total: Number(data.total || 0) })
}

export async function getProcessTemplateDetail(id) {
  return response(template(await request(`/approvals/templates/${encodeURIComponent(id)}`)))
}

export async function createProcessTemplate(payload) {
  return response(template(await request('/approvals/templates', { method: 'POST', body: payload })))
}

export async function updateProcessTemplate(id, payload) {
  return response(template(await request(`/approvals/templates/${encodeURIComponent(id)}`, { method: 'PUT', body: payload })))
}

export async function createProcessTemplateDraft(id, version) {
  return response(template(await request(`/approvals/templates/${encodeURIComponent(id)}/draft`, {
    method: 'POST', body: { version }
  })))
}

export async function publishProcessTemplateDraft(id, version) {
  return response(template(await request(`/approvals/templates/${encodeURIComponent(id)}/publish`, {
    method: 'POST', body: { version }
  })))
}

export async function updateProcessTemplateStatus(id, status, version, reason = '') {
  if (status !== 'DISABLED') throw new Error('流程启用必须通过发布草稿完成')
  return response(template(await request(`/approvals/templates/${encodeURIComponent(id)}/void`, {
    method: 'POST', body: { version, reason }
  })))
}
