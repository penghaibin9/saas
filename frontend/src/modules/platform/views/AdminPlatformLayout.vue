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
    <LoadingState v-else-if="loading" text="正在校验平台身份与职责能力…" />
    <router-view v-else-if="ctx" :ctx="ctx" />
  </BasePortalLayout>
</template>

<script>
/**
 * P-02 平台运营父布局。
 * identity-first：只接受 canonical /platform/context 的 PLATFORM principal；
 * capability-second：菜单和路由消费同一份 duty→permission pattern，root-only 页面不会
 * 因为 delegated principal 登录成功而自动放开。后端 capability dependency 仍是安全边界。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { ErrorState, LoadingState } from '@/components/business'
import { PLATFORM_MANAGEMENT_CATALOG } from '@/modules/platform/platformManagementCatalog'
import { canEnterRoute } from '@/security/permissionGate'
import {
  ensurePlatformAccessContext,
  toPlatformUiContext
} from '@/security/platformAccessGate'

const CONTROL_PLANE_LANDING = Object.freeze({
  'plt-standards': '/admin/platform/product-iam'
})

const BASE_MENUS = PLATFORM_MANAGEMENT_CATALOG.map((group) => ({
  key: group.key,
  label: group.label,
  icon: group.icon,
  path: CONTROL_PLANE_LANDING[group.key] || group.items[0].path
}))

export default {
  name: 'AdminPlatformLayout',
  components: { BasePortalLayout, ErrorState, LoadingState },
  data() {
    return { ctx: null, loading: true, error: '' }
  },
  computed: {
    menus() {
      if (!this.ctx) return []
      return BASE_MENUS.filter((item) => canEnterRoute(this.$router.resolve(item.path).meta))
    },
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus]
        .sort((a, b) => b.path.length - a.path.length)
        .find((m) => path === m.path || path.startsWith(m.path + '/'))
      return hit ? hit.key : (this.menus[0]?.key || '')
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
      const context = await ensurePlatformAccessContext({ force: true })
      if (context) this.ctx = toPlatformUiContext(context)
      else this.error = '平台身份或职责能力上下文加载失败'
      this.loading = false
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>