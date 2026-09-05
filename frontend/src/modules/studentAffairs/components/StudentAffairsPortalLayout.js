import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { searchStudentAffairsWorkspaceDeepLinks } from '@/config/studentAffairsWorkspaceDeepLinks'

const baseComputed = BasePortalLayout.computed || {}
const baseFnResults = baseComputed.fnResults

if (typeof baseFnResults !== 'function') {
  throw new Error('BasePortalLayout.fnResults contract is unavailable')
}

/**
 * 学工门户只扩展功能搜索结果，不复制或改写公共壳。
 * 复用 BasePortalLayout 的同一 render / methods / styles，仅在当前权限范围内补回 D() 搜索深链。
 */
export default {
  ...BasePortalLayout,
  name: 'StudentAffairsPortalLayout',
  computed: {
    ...baseComputed,
    fnResults() {
      const baseResults = baseFnResults.call(this)
      const query = String(this.fnQueryDebounced || '').trim()
      if (!query || !this.visibleGroupKeys?.has('student-affairs')) return baseResults

      const permissionPatterns = this.ctx?.permissionPatterns
      const deepLinks = searchStudentAffairsWorkspaceDeepLinks(query, permissionPatterns).map((item) => ({
        kind: '功能/页面',
        label: item.label,
        sub: item.sub,
        to: item.path,
        disabled: false,
        badge: item.badge || ''
      }))
      const seen = new Set()
      return [...deepLinks, ...baseResults]
        .filter((item) => {
          const key = `${item.label}|${item.to || ''}`
          if (seen.has(key)) return false
          seen.add(key)
          return true
        })
        .slice(0, 16)
        .map((item, index) => ({ ...item, _idx: index }))
    }
  }
}
