<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="工作台 · 领导驾驶舱"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载数据中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminDataCenterLayout — /admin/data-center 父布局。
 * 品牌名 / 角色 / 数据范围全部来自 dataCenterApi.getContext()，禁止硬编码。
 * P6：已移除「演示角色」假切换；切身份须走真实 /auth/switch-role（顶栏/身份体系）。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'

const MENUS = [
  { key: 'dc-dashboard', label: '数据驾驶舱', icon: '◫', path: '/admin/data-center' },
  { key: 'dc-lifecycle', label: '生命周期总览', icon: '↻', path: '/admin/data-center/lifecycle' },
  { key: 'dc-rankings', label: '排行分析', icon: '▤', path: '/admin/data-center/rankings' },
  { key: 'dc-risk', label: '风险预警', icon: '◐', path: '/admin/data-center/risk' },
  { key: 'dc-reports', label: '专题报表', icon: '▦', path: '/admin/data-center/reports' }
]

export default {
  name: 'AdminDataCenterLayout',
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
      return hit ? hit.key : 'dc-dashboard'
    }
  },
  async created() {
    await this.loadContext()
  },
  methods: {
    async loadContext() {
      const res = await dataCenterApi.getContext()
      if (res.code === 0) this.ctx = res.data
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.dcl-scope {
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
.dcl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
