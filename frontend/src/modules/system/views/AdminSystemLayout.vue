<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="系统管理中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    workspace
    horizontal-module="sys-org"
    @menu-select="onMenuSelect"
  >
    <template v-if="ctx">
      <div class="system-ui-polish">
        <SystemP1ClosurePanel
          v-if="showP1Closure"
          :key="$route.path"
          :ctx="ctx"
          @refresh-child="childKey += 1"
        />
        <router-view :key="childKey" :ctx="ctx" />
      </div>
    </template>
    <ErrorState v-else-if="contextError" :description="contextError" @retry="retryContext" />
    <LoadingState v-else text="正在加载系统管理中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * /admin/system 唯一父布局。system-ui-polish 只包系统管理内容区，
 * 不创建第二套门户壳，不改全局导航、路由、权限或业务接口。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import SystemP1ClosurePanel from '@/modules/system/components/SystemP1ClosurePanel.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { installSystemAuthorityCompatibility } from '@/modules/system/api/systemAuthorityCompatibility'
import { SYSTEM_MANAGEMENT_CATALOG } from '@/modules/system/systemManagementCatalog'
import { matchPermission } from '@/config/navPlan'
import '@/modules/system/styles/system-ui-polish.css'

// Install before any system child view starts issuing reads/writes. The bridge is
// module-scoped and mutates only systemApi methods; BasePortalLayout/navPlan stay untouched.
installSystemAuthorityCompatibility(systemApi)

const CONTROL_PLANE_LANDING = Object.freeze({ 'sys-access': '/admin/system/iam?surface=roles' })
const P1_CLOSURE_PATHS = new Set([
  '/admin/system/role-assignments',
  '/admin/system/login-policy',
  '/admin/system/account-exceptions'
])

export default {
  name: 'AdminSystemLayout',
  components: { BasePortalLayout, LoadingState, ErrorState, SystemP1ClosurePanel },
  data() { return { ctx: null, contextError: '', childKey: 0 } },
  computed: {
    menus() {
      const patterns = this.ctx?.permissionPatterns || []
      return SYSTEM_MANAGEMENT_CATALOG.flatMap(group => {
        const allowed = group.items.filter(item => matchPermission(patterns, item.permissionKey))
        if (!allowed.length) return []
        const preferred = CONTROL_PLANE_LANDING[group.key]
        const path = preferred && allowed.some(item => item.path === preferred) ? preferred : allowed[0].path
        return [{ key: group.key, label: group.label, icon: group.icon, path }]
      })
    },
    brandTitle() { return this.ctx ? this.ctx.tenantBrandConfig.schoolName + ' · 管理端' : '高校学生全生命周期管理平台' },
    activeKey() {
      const path = this.$route.path
      const candidates = SYSTEM_MANAGEMENT_CATALOG.flatMap(group => group.items.map(item => ({
        groupKey: group.key, path: item.path.split('?')[0]
      }))).sort((a, b) => b.path.length - a.path.length)
      const hit = candidates.find(item => path === item.path || path.startsWith(item.path + '/'))
      return hit ? hit.groupKey : 'sys-overview'
    },
    showP1Closure() { return P1_CLOSURE_PATHS.has(this.$route.path) }
  },
  async created() { await this.loadContext() },
  methods: {
    onMenuSelect(item) { if (item.path && item.path !== this.$route.path) this.$router.push(item.path) },
    async loadContext() {
      const res = await systemApi.getContext()
      if (res.code === 0) { this.ctx = res.data; this.contextError = '' }
      else { this.ctx = null; this.contextError = res.message || '系统管理上下文加载失败' }
    },
    async retryContext() { this.contextError = ''; await this.loadContext() }
  }
}
</script>
