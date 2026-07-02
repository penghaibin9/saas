<template>
  <BasePortalLayout
    title="学校管理端"
    subtitle="权限与流程中心"
    :menus="visibleMenus"
    :active-key="activeKey"
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <!-- licenseContext 预留演示开关：本次不接真实授权中心，P6-2 接入 /platform 后由真实 license 驱动 -->
      <label class="wfl-state-switch">
        <span class="wfl-state-switch__label">授权状态演示</span>
        <select v-model="licenseView" class="wfl-state-switch__select" @change="onLicenseChange">
          <option value="NORMAL">正常</option>
          <option value="READONLY">到期只读</option>
          <option value="NO_LICENSE">未授权</option>
        </select>
      </label>
      <span class="wfl-user">{{ userName }}</span>
    </template>
    <router-view />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminWorkflowLayout —— /admin/workflow 最小承载壳。
 * 全局 /admin 菜单体系尚未建立（menu-freeze：P6-2 动态菜单），
 * 故本壳只提供 workflow 模块自有菜单（经 filterMenusByPermission 过滤），不改全局菜单。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import {
  loadPermissionContext,
  getPermissionContext,
  filterMenusByPermission
} from '@/modules/workflow/context/permission.context'
import { workflowProvider } from '@/modules/workflow'

const MENUS = [
  { key: 'workflow-home', label: '流程中心', icon: '◫', path: '/admin/workflow', permissionKey: 'workflow.home.view' },
  { key: 'workflow-processes', label: '流程模板', icon: '⧉', path: '/admin/workflow/processes', permissionKey: 'workflow.process.view' },
  { key: 'workflow-tasks', label: '审批任务', icon: '✓', path: '/admin/workflow/tasks', permissionKey: 'workflow.task.view' },
  { key: 'workflow-roles', label: '角色管理', icon: '◎', path: '/admin/workflow/roles', permissionKey: 'workflow.role.view' },
  { key: 'workflow-permissions', label: '权限点管理', icon: '⚙', path: '/admin/workflow/permissions', permissionKey: 'workflow.permission.view' }
]

export default {
  name: 'AdminWorkflowLayout',
  components: { BasePortalLayout },
  data() {
    return {
      menus: MENUS,
      contextLoaded: false,
      licenseView: workflowProvider.getLicenseViewState()
    }
  },
  computed: {
    visibleMenus() {
      if (!this.contextLoaded) return this.menus
      return filterMenusByPermission(this.menus)
    },
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus].sort((a, b) => b.path.length - a.path.length).find((m) => path === m.path || path.startsWith(m.path + '/'))
      return hit ? hit.key : 'workflow-home'
    },
    userName() {
      return getPermissionContext()?.userName || '管理员'
    }
  },
  async created() {
    await loadPermissionContext()
    this.contextLoaded = true
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    onLicenseChange() {
      workflowProvider.setLicenseViewState(this.licenseView)
      // 触发子页刷新：通过 route query 打点（子页 watch licenseTick）
      this.$router.replace({ query: { ...this.$route.query, lv: Date.now() } })
    }
  }
}
</script>

<style scoped>
.wfl-state-switch { display: inline-flex; align-items: center; gap: var(--space-2); }
.wfl-state-switch__label { font-size: var(--font-size-xs); color: var(--text-tertiary); white-space: nowrap; }
.wfl-state-switch__select {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: 2px var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  background: var(--bg-card);
}
.wfl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
