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

export const schoolIamApi = {
  summary: () => call('/system/iam/summary', {}, '学校 IAM 总览加载失败'),
  permissionCatalog: () => call('/system/iam/permission-catalog', {}, '学校可分配权限目录加载失败'),
  roleTemplates: () => call('/system/iam/role-templates', {}, '学校角色模板加载失败'),
  templateImpact: (templateId) => call(
    `/system/iam/role-templates/${encodeURIComponent(templateId)}/impact`,
    {},
    '角色模板影响分析失败'
  ),
  roleMembers: (roleId, page = 1, pageSize = 50) => call(
    `/system/roles/${encodeURIComponent(roleId)}/members`,
    { params: { page, pageSize } },
    '角色成员分页加载失败'
  ),
  roleAudit: (roleId, page = 1, pageSize = 50) => call(
    `/system/roles/${encodeURIComponent(roleId)}/audit`,
    { params: { page, pageSize } },
    '角色审计分页加载失败'
  ),
  accessExplain: (userId, {
    moduleKey = 'internship',
    permissionCode = 'internship.recruitment.manage',
    scopeTargetType = '',
    scopeTargetId = '',
    resourceType = '',
    resourceId = ''
  } = {}) => call(
    `/system/iam/access-explain/${encodeURIComponent(userId)}`,
    {
      params: {
        moduleKey,
        permissionCode,
        ...(scopeTargetType ? { scopeTargetType } : {}),
        ...(scopeTargetId ? { scopeTargetId } : {}),
        ...(resourceType ? { resourceType } : {}),
        ...(resourceId ? { resourceId } : {})
      }
    },
    '访问解释失败'
  )
}
