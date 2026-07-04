<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="数据中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <label v-if="ctx" class="dcl-switch" title="演示环境：切换角色以查看不同数据范围与权限差异">
        <span class="dcl-switch__label">演示角色</span>
        <select
          class="dcl-switch__select"
          :value="ctx.currentRole.roleCode"
          :disabled="switching"
          @change="onSwitchRole($event.target.value)"
        >
          <option v-for="r in ctx.availableRoles" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
      </label>
    </template>
    <router-view v-if="ctx" :key="ctx.currentRole.roleCode" :ctx="ctx" />
    <LoadingState v-else text="正在加载数据中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminDataCenterLayout — /admin/data-center 父布局。
 * 品牌名 / 角色 / 数据范围全部来自 dataCenterApi.getContext()，禁止硬编码。
 * ctx 通过 props 下发给子路由页面；header-right 提供演示角色切换：
 * switchRole 后重新 getContext，router-view 以角色码为 :key 强制子页刷新。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'
import { toast } from '@/utils/toast'

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
    return { menus: MENUS, ctx: null, switching: false }
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
    },
    async onSwitchRole(roleCode) {
      if (!this.ctx || roleCode === this.ctx.currentRole.roleCode) return
      this.switching = true
      const res = await dataCenterApi.switchRole(roleCode)
      if (res.code === 0) {
        await this.loadContext()
        toast.success('已切换为「' + res.data.roleName + '」视角，可见指标与操作权限已同步刷新')
      } else {
        toast.error(res.message)
      }
      this.switching = false
    }
  }
}
</script>

<style scoped>
.dcl-switch {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.dcl-switch__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.dcl-switch__select {
  height: 28px;
  max-width: 230px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  padding: 0 var(--space-2);
  outline: none;
  cursor: pointer;
}
.dcl-switch__select:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.dcl-switch__select:disabled {
  color: var(--text-disabled);
  cursor: not-allowed;
}
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
