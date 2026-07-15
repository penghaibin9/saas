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

const MENUS = [
  { key: 'sys-home', label: '管理看板', icon: '◫', path: '/admin/system' },
  { key: 'sys-users', label: '师生账号', icon: '☰', path: '/admin/system/users' },
  { key: 'sys-identity-import', label: '导入老师和学生', icon: '⇪', path: '/admin/system/identity-import' },
  { key: 'sys-roles', label: '角色权限', icon: '❖', path: '/admin/system/roles' },
  { key: 'sys-menus', label: '菜单权限', icon: '▤', path: '/admin/system/menus' },
  { key: 'sys-scopes', label: '数据范围', icon: '◔', path: '/admin/system/scopes' },
  { key: 'sys-org', label: '组织结构', icon: '♜', path: '/admin/system/org' },
  { key: 'sys-config', label: '系统与品牌', icon: '✦', path: '/admin/system/config' },
  { key: 'sys-logs', label: '日志中心', icon: '≡', path: '/admin/system/logs' }
]

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
      return hit ? hit.key : 'sys-home'
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
