/**
 * A5 · 平台运营父布局认证上下文。
 *
 * 只读取真实 /auth/me，不维护浏览器角色、数据范围或租户列表。
 * 平台业务 API 仍统一走 platformControl.api.js；本文件只负责把已认证身份
 * 整理成 BasePortalLayout 需要的只读 ctx。
 */
import { request } from '@/services/http/client'

const PLATFORM_ROLES = new Set(['PLATFORM_SUPER_ADMIN', 'PLATFORM_OWNER'])
const PLATFORM_DISPLAY_NAME = 'SaaS 运营平台'

function failed(error) {
  return {
    code: Number(error && error.code) || 1,
    data: null,
    message: (error && error.message) || '平台认证上下文加载失败'
  }
}

export const platformContextApi = {
  async getContext() {
    try {
      const me = await request('/auth/me')
      const role = (me && me.currentRole) || {}
      const roleCode = String(role.roleCode || role.contextType || '').trim().toUpperCase()
      if (!PLATFORM_ROLES.has(roleCode)) {
        return {
          code: 403001,
          data: null,
          message: '当前账号不是平台运营角色，禁止进入跨租户控制面'
        }
      }

      return {
        code: 0,
        message: 'ok',
        data: {
          tenantBrandConfig: {
            platformDisplayName: PLATFORM_DISPLAY_NAME
          },
          currentRole: {
            roleCode,
            roleName: role.roleName || role.contextName || '平台运营角色',
            userName: (me && (me.realName || me.loginName)) || '—'
          },
          dataScope: {
            scopeType: role.dataScope || 'PLATFORM',
            scopeName: role.scopeLabel || '平台配置面（不含学校业务敏感明细）'
          }
        }
      }
    } catch (error) {
      return failed(error)
    }
  }
}
