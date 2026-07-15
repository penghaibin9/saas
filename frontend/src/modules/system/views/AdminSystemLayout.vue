<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="系统管理中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
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
import { LoadingState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'
import { SYSTEM_MANAGEMENT_CATALOG } from '@/modules/system/systemManagementCatalog'

/* ctx 尚未加载时的兼容菜单；正常状态由 BasePortalLayout 读取同一份 navPlan 渲染 8 组 / 26 项。 */
const MENUS = SYSTEM_MANAGEMENT_CATALOG.map((group) => ({
  key: group.key, label: group.label, icon: group.icon, path: group.items[0].path
}))

export default {
  name: 'AdminSystemLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { menus: MENUS, ctx: null }
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
    }
  },
  async created() {
    const res = await systemApi.getContext()
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
