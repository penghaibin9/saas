<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="平台运营中心"
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

const MENUS = [
  { key: 'plt-overview', label: '平台总控台', icon: '◎', path: '/admin/platform/overview' },
  { key: 'plt-tenants', label: '租户学校', icon: '♜', path: '/admin/platform/tenants' },
  { key: 'plt-packages', label: '套餐管理', icon: '❖', path: '/admin/platform/packages' },
  { key: 'plt-rules', label: '规则中心', icon: '☲', path: '/admin/platform/rules' },
  { key: 'plt-dicts', label: '字典管理', icon: '≣', path: '/admin/platform/dictionaries' },
  { key: 'plt-orders', label: '订单开通', icon: '▤', path: '/admin/platform/orders' },
  { key: 'plt-notices', label: '平台公告', icon: '♪', path: '/admin/platform/notices' },
  { key: 'plt-security', label: '安全策略', icon: '☖', path: '/admin/platform/security' },
  { key: 'plt-audit', label: '全平台审计', icon: '☰', path: '/admin/platform/audit' },
  { key: 'plt-settings', label: '系统参数', icon: '✱', path: '/admin/platform/settings' },
  { key: 'plt-file-storage', label: '文件存储', icon: '⛃', path: '/admin/platform/file-storage' },
  { key: 'plt-home', label: '运营看板', icon: '◫', path: '/admin/platform' },
  { key: 'plt-integrations', label: '集成开放', icon: '⇄', path: '/admin/platform/integrations' },
  { key: 'plt-api', label: 'API·Webhook', icon: '✦', path: '/admin/platform/api-access' },
  { key: 'plt-sync', label: '同步与日志', icon: '≡', path: '/admin/platform/sync' }
]

export default {
  name: 'AdminPlatformLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { menus: MENUS, ctx: null }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '平台运营'
      return this.ctx.tenantBrandConfig.platformDisplayName + ' · 运营端'
    },
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus]
        .sort((a, b) => b.path.length - a.path.length)
        .find((m) => path === m.path || path.startsWith(m.path + '/'))
      return hit ? hit.key : 'plt-home'
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
