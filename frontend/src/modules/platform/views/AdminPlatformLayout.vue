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
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载平台运营中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminPlatformLayout — /admin/platform 父布局（SaaS 运营方视角）。
 * 平台显示名 / 角色 / 数据范围全部来自 platformApi.getContext()，禁止硬编码。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { platformApi } from '@/modules/platform/api/platform.api'
import { PLATFORM_MANAGEMENT_CATALOG } from '@/modules/platform/platformManagementCatalog'

const MENUS = PLATFORM_MANAGEMENT_CATALOG.map((group) => ({
  key: group.key, label: group.label, icon: group.icon, path: group.items[0].path
}))

export default {
  name: 'AdminPlatformLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { menus: MENUS, ctx: null }
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
  async created() {
    const res = await platformApi.getContext()
    if (res.code === 0) this.ctx = res.data
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.pl-scope {
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
.pl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
