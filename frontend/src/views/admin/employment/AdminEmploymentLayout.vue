<template>
  <BasePortalLayout
    :title="portalTitle"
    subtitle="岗位实习中心 · 就业服务"
    workspace
    hide-global-workbench
    :ctx="ctx"
  >
    <router-view :key="viewKey" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminEmploymentLayout — /admin/employment 模块内布局。
 * P6：已移除「当前角色」假切换；切身份须走真实 /auth/switch-role。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { getEmploymentContext } from '@/modules/employment/api/employment.api'

export default {
  name: 'AdminEmploymentLayout',
  components: { BasePortalLayout },
  data() {
    return { ctx: null }
  },
  computed: {
    portalTitle() {
      const brand = this.ctx?.tenantBrandConfig
      if (!brand) return '管理端'
      return `${brand.schoolName} · ${brand.platformDisplayName}`
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
      const res = await getEmploymentContext()
      if (res.code === 0) this.ctx = res.data
    }
  }
}
</script>
