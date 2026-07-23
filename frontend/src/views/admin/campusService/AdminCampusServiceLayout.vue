<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="学工中心 · 在校服务"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载在校服务中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminCampusServiceLayout — /admin/campus-service 父布局。
 * P6：已移除演示角色假切换；切身份须走真实 /auth/switch-role。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { getCampusServiceContext } from '@/modules/campusService/api/campusService.api'

export default {
  name: 'AdminCampusServiceLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { ctx: null }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    }
  },
  async created() {
    const res = await getCampusServiceContext()
    if (res.code === 0) this.ctx = res.data
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>
