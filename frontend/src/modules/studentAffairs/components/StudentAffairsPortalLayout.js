import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { searchStudentAffairsWorkspaceDeepLinks } from '@/config/studentAffairsWorkspaceDeepLinks'

const baseComputed = BasePortalLayout.computed || {}
const baseFnResults = baseComputed.fnResults
const baseWatch = BasePortalLayout.watch || {}
const baseFnQueryWatcher = baseWatch.fnQuery

if (typeof baseFnResults !== 'function') {
  throw new Error('BasePortalLayout.fnResults contract is unavailable')
}
if (typeof baseFnQueryWatcher !== 'function') {
  throw new Error('BasePortalLayout.fnQuery watcher contract is unavailable')
}

/**
 * 学工门户复用公共壳的搜索权威，只做两项页面级适配：
 * 1. D() 低频页显示短标题，避免与公共壳的完整路径结果重复；
 * 2. 同一父布局内连续跳转后，输入新查询时重新打开结果面板。
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
      const exactPaths = new Set(deepLinks.map((item) => item.to).filter(Boolean))
      const seen = new Set()
      return [...deepLinks, ...baseResults.filter((item) => !item.to || !exactPaths.has(item.to))]
        .filter((item) => {
          const key = `${item.label}|${item.to || ''}`
          if (seen.has(key)) return false
          seen.add(key)
          return true
        })
        .slice(0, 16)
        .map((item, index) => ({ ...item, _idx: index }))
    }
  },
  watch: {
    ...baseWatch,
    fnQuery(q, previousQuery) {
      baseFnQueryWatcher.call(this, q, previousQuery)
      if (String(q || '').trim()) this.fnOpen = true
    }
  }
}
