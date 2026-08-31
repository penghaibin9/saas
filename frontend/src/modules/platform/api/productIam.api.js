import { request } from '@/services/http/client'

const ok = (data, message = 'ok') => ({ code: 0, data, message })
const fail = (error, fallback) => ({
  code: error?.code || 1,
  bizCode: error?.bizCode || error?.biz || '',
  data: null,
  message: error?.message || fallback
})

async function call(path, options, fallback) {
  try {
    return ok(await request(path, options))
  } catch (error) {
    return fail(error, fallback)
  }
}

export const productIamApi = {
  source: () => call('/platform/product-iam/source', {}, 'Product IAM 真值加载失败'),
  releases: () => call('/platform/product-iam/releases', {}, 'Product IAM 发布记录加载失败'),
  createRelease: (body) => call('/platform/product-iam/releases', { method: 'POST', body }, 'Product IAM 草稿创建失败'),
  impact: (id) => call(`/platform/product-iam/releases/${encodeURIComponent(id)}/impact`, {}, 'Product IAM 影响分析失败'),
  publish: (id, expectedVersion) => call(
    `/platform/product-iam/releases/${encodeURIComponent(id)}/publish`,
    { method: 'POST', body: { expectedVersion } },
    'Product IAM 发布失败'
  ),
  templateVersions: (code) => call(`/platform/product-iam/school-role-templates/${encodeURIComponent(code)}`, {}, '角色模板版本加载失败'),
  createTemplateDraft: (code, body) => call(`/platform/product-iam/school-role-templates/${encodeURIComponent(code)}/drafts`, { method: 'POST', body }, '角色模板草稿创建失败'),
  updateTemplateDraft: (code, id, body) => call(`/platform/product-iam/school-role-templates/${encodeURIComponent(code)}/drafts/${encodeURIComponent(id)}`, { method: 'PUT', body }, '角色模板草稿保存失败'),
  templateImpact: (code, id) => call(`/platform/product-iam/school-role-templates/${encodeURIComponent(code)}/drafts/${encodeURIComponent(id)}/impact`, {}, '角色模板影响分析失败'),
  publishTemplate: (code, id, body) => call(`/platform/product-iam/school-role-templates/${encodeURIComponent(code)}/drafts/${encodeURIComponent(id)}/publish`, { method: 'POST', body }, '角色模板发布失败'),
  rollbackTemplate: (code, body) => call(`/platform/product-iam/school-role-templates/${encodeURIComponent(code)}/rollback`, { method: 'POST', body }, '角色模板回滚草稿创建失败')
}
