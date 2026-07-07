<template>
  <BasePortalLayout
    :title="portalTitle"
    subtitle="岗位实习中心 · 就业服务"
    :menus="menus"
    :active-key="activeKey"
    :ctx="
      brand
        ? {
            tenantBrandConfig: brand,
            currentRole: roles.find((r) => r.roleId === currentRoleId) || {},
            dataScope: { name: dataScopeName }
          }
        : null
    "
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <label class="el-role">
        <span class="el-role__label">当前角色</span>
        <select class="el-role__select" :value="currentRoleId" @change="onRoleChange($event.target.value)">
          <option v-for="r in roles" :key="r.roleId" :value="r.roleId">{{ r.roleName }}</option>
        </select>
      </label>
    </template>
    <router-view :key="viewKey" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminEmploymentLayout — /admin/employment 模块内布局（不改全局 Layout / 全局菜单）。
 * 门户标题与角色/数据范围全部来自 employment.api 的 tenantBrandConfig / currentRole，禁止硬编码。
 * 角色切换后通过 viewKey 触发子页面重挂载，重新拉取权限与数据。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { getEmploymentContext, switchEmploymentRole } from '@/modules/employment/api/employment.api'

const MENUS = [
  { key: 'emp-dashboard', label: '管理看板', icon: '◫', path: '/admin/employment' },
  { key: 'emp-students', label: '就业学生', icon: '☰', path: '/admin/employment/students' },
  { key: 'emp-materials', label: '材料审核', icon: '◈', path: '/admin/employment/materials' },
  { key: 'emp-unemployed', label: '未就业帮扶', icon: '◐', path: '/admin/employment/unemployed' },
  { key: 'emp-followups', label: '跟进记录', icon: '✎', path: '/admin/employment/followups' }
]

export default {
  name: 'AdminEmploymentLayout',
  components: { BasePortalLayout },
  data() {
    return {
      menus: MENUS,
      brand: null,
      roles: [],
      currentRoleId: '',
      dataScopeName: ''
    }
  },
  computed: {
    portalTitle() {
      if (!this.brand) return '加载中…'
      return `${this.brand.schoolName} · ${this.brand.platformDisplayName}`
    },
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus].sort((a, b) => b.path.length - a.path.length).find((m) => path === m.path || path.startsWith(m.path + '/'))
      if (!hit && /^\/admin\/employment\/(students|materials)\//.test(path)) {
        return path.includes('/materials/') ? 'emp-materials' : 'emp-students'
      }
      return hit ? hit.key : 'emp-dashboard'
    },
    viewKey() {
      return `${this.$route.fullPath}::${this.currentRoleId}`
    }
  },
  async created() {
    await this.loadContext()
  },
  methods: {
    async loadContext() {
      const res = await getEmploymentContext()
      if (res.code === 0) this.applyContext(res.data)
    },
    applyContext(ctx) {
      this.brand = ctx.tenantBrandConfig
      this.roles = ctx.roles
      this.currentRoleId = ctx.currentRole.roleId
      this.dataScopeName = ctx.dataScope.name
    },
    async onRoleChange(roleId) {
      const res = await switchEmploymentRole(roleId)
      if (res.code === 0) this.applyContext(res.data)
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.el-role {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.el-role__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.el-role__select {
  height: 28px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  padding: 0 var(--space-1);
  outline: none;
}
</style>
