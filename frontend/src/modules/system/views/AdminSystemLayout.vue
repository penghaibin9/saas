<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="系统管理中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template v-if="ctx">
      <SystemP1ClosurePanel
        v-if="showP1Closure"
        :key="$route.path"
        :ctx="ctx"
        @refresh-child="childKey += 1"
      />
      <router-view :key="childKey" :ctx="ctx" />
    </template>
    <ErrorState v-else-if="contextError" :description="contextError" @retry="retryContext" />
    <LoadingState v-else text="正在加载系统管理中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminSystemLayout — /admin/system 父布局。
 * 品牌名 / 角色 / 数据范围全部来自 systemApi.getContext()，禁止硬编码。
 * ctx 通过 props 下发给子路由页面，避免每页重复拉取。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import SystemP1ClosurePanel from '@/modules/system/components/SystemP1ClosurePanel.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { SYSTEM_MANAGEMENT_CATALOG } from '@/modules/system/systemManagementCatalog'

const CONTROL_PLANE_LANDING = Object.freeze({
  'sys-access': '/admin/system/iam'
})

/* ctx 尚未加载时的兼容菜单；正常状态由 BasePortalLayout 读取同一份 navPlan 渲染 8 组 / 26 项。 */
const MENUS = SYSTEM_MANAGEMENT_CATALOG.map((group) => ({
  key: group.key,
  label: group.label,
  icon: group.icon,
  path: CONTROL_PLANE_LANDING[group.key] || group.items[0].path
}))

const P1_CLOSURE_PATHS = new Set([
  '/admin/system/role-assignments',
  '/admin/system/login-policy',
  '/admin/system/account-exceptions',
  '/admin/system/org'
])

export default {
  name: 'AdminSystemLayout',
  components: { BasePortalLayout, LoadingState, ErrorState, SystemP1ClosurePanel },
  data() {
    return { menus: MENUS, ctx: null, contextError: '', childKey: 0 }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    },
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus]
        .sort((a, b) => b.path.length - a.path.length)
        .find((m) => path === m.path || path.startsWith(m.path + '/'))
      return hit ? hit.key : 'sys-overview'
    },
    showP1Closure() {
      return P1_CLOSURE_PATHS.has(this.$route.path)
    }
  },
  async created() {
    const res = await systemApi.getContext()
    if (res.code === 0) {
      this.ctx = res.data
      this.contextError = ''
    } else {
      this.ctx = null
      this.contextError = res.message || '系统管理上下文加载失败'
    }
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    async retryContext() {
      this.contextError = ''
      const res = await systemApi.getContext()
      if (res.code === 0) this.ctx = res.data
      else this.contextError = res.message || '系统管理上下文加载失败'
    }
  }
}
</script>

<style scoped>
.sl-scope {
  font-size: var(--font-size-xs);
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  padding: 0 var(--space-3);
  height: 24px;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
.sl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
