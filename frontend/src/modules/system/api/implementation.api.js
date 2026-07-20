import { request, requestUpload } from '@/services/http/client'

const root = '/system/implementation'

export const implementationApi = {
  catalog: () => request(`${root}/preset-catalog`),
  current: () => request(`${root}/projects/current`),
  create: (body) => request(`${root}/projects`, { method: 'POST', body }),
  saveSection: (id, code, body) => request(`${root}/projects/${id}/sections/${code}`, { method: 'PUT', body }),
  preview: (id) => request(`${root}/projects/${id}/preview`, { method: 'POST' }),
  apply: (id, body) => request(`${root}/projects/${id}/apply`, { method: 'POST', body }),
  validateIdentityFile: (file) => requestUpload('/system/identity-import/validate-file', file),
  discoverMapping: (id, batchNo) => request(`${root}/projects/${id}/mapping/discover`, { method: 'POST', body: { batchNo } }),
  confirmMapping: (id, body) => request(`${root}/projects/${id}/mapping/decisions`, { method: 'PUT', body }),
  applyMapping: (id, body) => request(`${root}/projects/${id}/mapping/apply`, { method: 'POST', body }),
  discoverRelations: (id, batchNo) => request(`${root}/projects/${id}/relations/discover`, { method: 'POST', body: { batchNo } }),
  confirmRelations: (id, body) => request(`${root}/projects/${id}/relations/decisions`, { method: 'PUT', body }),
  applyRelations: (id, body) => request(`${root}/projects/${id}/relations/apply`, { method: 'POST', body }),
  relationBatches: (id) => request(`${root}/projects/${id}/relations/batches`),
  rollbackRelations: (id, batchNo, body) => request(`${root}/projects/${id}/relations/${batchNo}/rollback`, { method: 'POST', body }),
  runtimePresets: (id) => request(`${root}/projects/${id}/runtime-presets`),
  confirmWorkflowPolicy: (id, body) => request(`${root}/projects/${id}/runtime-presets/workflows/confirm-policy`, { method: 'POST', body }),
  updateWorkflow: (id, code, body) => request(`${root}/projects/${id}/runtime-presets/workflows/${code}`, { method: 'PUT', body }),
  updateWorkbench: (id, roleCode, body) => request(`${root}/projects/${id}/runtime-presets/workbenches/${roleCode}`, { method: 'PUT', body }),
  updateNotification: (id, code, channel, body) => request(`${root}/projects/${id}/runtime-presets/notifications/${code}/${channel}`, { method: 'PUT', body }),
  installations: () => request(`${root}/installations`),
  createChange: (installationId, body) => request(`${root}/installations/${installationId}/changes`, { method: 'POST', body }),
  analyzeChange: (id) => request(`${root}/projects/${id}/changes/analyze`, { method: 'POST' }),
  runChecks: (id) => request(`${root}/projects/${id}/checks/run`, { method: 'POST' }),
  confirmCheck: (id, code, body) => request(`${root}/projects/${id}/checks/${code}/confirm`, { method: 'POST', body }),
  accept: (id, body) => request(`${root}/projects/${id}/accept`, { method: 'POST', body })
}
