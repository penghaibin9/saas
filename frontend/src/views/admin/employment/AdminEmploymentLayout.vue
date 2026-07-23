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
    <router-view :key="viewKey" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminEmploymentLayout — /admin/employment 模块内布局。
 * P6：已移除「当前角色」假切换；切身份须走真实 /auth/switch-role。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { getEmploymentContext } from '@/modules/employment/api/employment.api'

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
      return this.$route.fullPath
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
      this.roles = ctx.roles || []
      this.currentRoleId = ctx.currentRole?.roleId || ''
      this.dataScopeName = ctx.dataScope?.name || ''
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>
