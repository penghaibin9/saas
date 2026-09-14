import { request } from '@/services/http/client'
const id = value => {
  const text = String(value ?? '')
  if (!/^[1-9][0-9]{0,18}$/.test(text)) throw new Error('INVALID_OBJECT_ID')
  return encodeURIComponent(text)
}
const base = batchId => `/academic-affairs/scheduling/batches/${id(batchId)}/optimizer`
export const schedulingOptimizerApi = {
  apply: (batchId, jobId, version) => request(`${base(batchId)}/jobs/${id(jobId)}/apply`, {
    method: 'POST', body: { expectedVersion: version }, timeoutMs: 60000
  }),
  context: batchId => request(`${base(batchId)}/context`, { timeoutMs: 30000 }),
  enqueue: (batchId, body) => request(`${base(batchId)}/jobs`, { method: 'POST', body, timeoutMs: 60000 }),
  get: (batchId, jobId) => request(`${base(batchId)}/jobs/${id(jobId)}`),
  lookup: (batchId, key) => request(`${base(batchId)}/lookup`, { params: { idempotencyKey: key } }),
  cancel: (batchId, jobId, version) => request(`${base(batchId)}/jobs/${id(jobId)}/cancel`, {
    method: 'POST', body: { expectedVersion: version }
  }),
  preview: (batchId, jobId, taskId, week) => request(`${base(batchId)}/jobs/${id(jobId)}/preview`, {
    params: { taskId, week }
  })
}
