<template>
  <BasePortalLayout
    :title="portalTitle"
    subtitle="学工中心 · 数字迎新"
    :ctx="context"
    @menu-select="onMenuSelect"
  >
    <template #menu>
      <StudentAffairsWorkspaceNav v-if="context" :ctx="context" />
    </template>
    <router-view :key="viewKey" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminOrientationLayout — /admin/orientation 模块内布局。
 * P6：已移除「当前角色」假切换；切身份须走真实 /auth/switch-role。
 * V6：二十条迎新真实路由按「数字迎新」工作区的阶段分组展示。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { getOrientationContext } from '@/modules/orientation/api/orientation.api'
import StudentAffairsWorkspaceNav from '@/modules/studentAffairs/components/StudentAffairsWorkspaceNav.vue'

export default {
  name: 'AdminOrientationLayout',
  components: { BasePortalLayout, StudentAffairsWorkspaceNav },
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
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>
