<template>
  <BasePortalLayout
    :title="portalTitle"
    subtitle="学工中心 · 数字迎新"
    :ctx="context"
    :workspace-navigate="resolveOrientationDestination"
    @menu-select="onMenuSelect"
  >
    <OrientationWorkspaceNav />
    <router-view :key="viewKey" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminOrientationLayout — /admin/orientation 模块内布局。
 * P6：已移除「当前角色」假切换；切身份须走真实 /auth/switch-role。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import OrientationWorkspaceNav from '@/modules/orientation/components/OrientationWorkspaceNav.vue'
import { getOrientationContext } from '@/modules/orientation/api/orientation.api'
import { orientationDestination } from '@/modules/orientation/routeContext'

export default {
  name: 'AdminOrientationLayout',
  components: { BasePortalLayout, OrientationWorkspaceNav },
  provide() { return { affairsWorkspace: true, conciseBusinessHeader: true } },
  data() {
    return { context: null, brand: null, roles: [], currentRoleId: '', dataScopeName: '' }
  },
  computed: {
    portalTitle() {
      if (!this.brand) return '加载中…'
      return `${this.brand.schoolName} · ${this.brand.platformDisplayName}`
    },
    viewKey() {
      return this.$route.fullPath
    }
  },
  async created() {
    await this.loadContext()
  },
  methods: {
    resolveOrientationDestination(path) { return orientationDestination(path, this.$route) },
    async loadContext() {
      const res = await getOrientationContext()
      if (res.code === 0) this.applyContext(res.data)
    },
    applyContext(ctx) {
      this.context = ctx
      this.brand = ctx.tenantBrandConfig
      this.roles = ctx.roles || []
      this.currentRoleId = ctx.currentRole?.roleId || ''
      this.dataScopeName = ctx.dataScope?.name || ''
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(this.resolveOrientationDestination(item.path))
    }
  }
}
</script>
