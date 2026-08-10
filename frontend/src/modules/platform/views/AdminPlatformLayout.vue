<template>
  <BasePortalLayout
    title="SaaS 运营平台"
    product-name="SaaS 运营平台"
    subtitle="平台运营控制面"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <ErrorState v-if="error" :description="error" @retry="loadContext" />
    <LoadingState v-else-if="loading" text="正在校验平台身份与数据范围…" />
    <router-view v-else-if="ctx" :ctx="ctx" />
  </BasePortalLayout>
</template>

<script>
/**
 * A5 / P0-07 平台运营父布局。
 * 身份、角色、dataScope 只来自真实 auth/RBAC；平台角色另由 /platform/overview 强校验。
 * 任何请求失败均 fail-closed，禁止构造 PLATFORM_OPS/区域演示身份。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { ErrorState, LoadingState } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { PLATFORM_MANAGEMENT_CATALOG } from '@/modules/platform/platformManagementCatalog'

const MENUS = PLATFORM_MANAGEMENT_CATALOG.map((group) => ({
  key: group.key, label: group.label, icon: group.icon, path: group.items[0].path
}))

export default {
  name: 'AdminPlatformLayout',
  components: { BasePortalLayout, ErrorState, LoadingState },
  data() {
    return { menus: MENUS, ctx: null, loading: true, error: '' }
  },
  computed: {
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus]
        .sort((a, b) => b.path.length - a.path.length)
        .find((m) => path === m.path || path.startsWith(m.path + '/'))
      return hit ? hit.key : 'plt-command'
    }
  },
  created() {
    this.loadContext()
  },
  methods: {
    async loadContext() {
      this.loading = true
      this.error = ''
      this.ctx = null
      const res = await platformControlApi.getContext()
      if (res.code === 0) this.ctx = res.data
      else this.error = res.message || '平台身份校验失败'
      this.loading = false
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>
