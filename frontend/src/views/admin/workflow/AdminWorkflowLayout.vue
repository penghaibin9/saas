<template>
  <BasePortalLayout
    title="学校管理端"
    subtitle="系统管理 · 权限与流程"
    :menus="visibleMenus"
    :active-key="activeKey"
    :ctx="ctx"
    workspace
    @menu-select="onMenuSelect"
  >
    <template v-if="ctx && contextLoaded"><router-view /></template>
    <ErrorState v-else-if="contextError" :description="contextError" @retry="loadContext" />
    <LoadingState v-else text="正在加载流程工作区…" />
  </BasePortalLayout>
</template>

<script>
/**
 * Workflow belongs to the system workspace. Global navigation consumes the same
 * real identity/module projection as the workbench; legacy preview context stays local.
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import {
  loadPermissionContext,
  filterMenusByPermission
} from '@/modules/workflow/context/permission.context'
import { fetchLayoutContext } from '@/modules/workbench/api/workbench.api'
import { LoadingState, ErrorState } from '@/components/business'

const MENUS = [
  { key: 'workflow-home', label: '流程中心', icon: '◫', path: '/admin/workflow', permissionKey: 'workflow.home.view' },
  { key: 'workflow-processes', label: '流程模板', icon: '⧉', path: '/admin/workflow/processes', permissionKey: 'workflow.process.view' },
  { key: 'workflow-tasks', label: '审批任务', icon: '✓', path: '/admin/workflow/tasks', permissionKey: 'workflow.task.view' },
  { key: 'workflow-roles', label: '角色管理', icon: '◎', path: '/admin/workflow/roles', permissionKey: 'workflow.role.view' },
  { key: 'workflow-permissions', label: '权限点管理', icon: '⚙', path: '/admin/workflow/permissions', permissionKey: 'workflow.permission.view' }
]

export default {
  name: 'AdminWorkflowLayout',
  components: { BasePortalLayout, LoadingState, ErrorState },
  data() {
    return {
      menus: MENUS,
      contextLoaded: false,
      ctx: null,
      contextError: ''
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
    }
  },
  async created() {
    await this.loadContext()
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    async loadContext() {
      this.ctx = null
      this.contextLoaded = false
      this.contextError = ''
      try {
        const ctx = await fetchLayoutContext()
        if (!Array.isArray(ctx.permissionPatterns) || !ctx.currentRole?.roleCode) {
          throw new Error('身份与权限信息暂不可用，请重试')
        }
        await loadPermissionContext()
        this.ctx = ctx
        this.contextLoaded = true
      } catch (error) {
        this.contextError = error.message || '流程工作区加载失败，请重试'
      }
    }
  }
}
</script>

<style scoped>
</style>
