<template>
  <BasePortalLayout
    title="学校管理端"
    subtitle="学生主档与身份中心"
    :menus="menus"
    :active-key="activeKey"
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <StudentDataScopeHint />
      <span class="sl-user">{{ userName }}</span>
    </template>
    <router-view />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminStudentLayout — /admin/student 父布局（模块内导航，不改全局菜单体系）。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import StudentDataScopeHint from '@/modules/student/components/StudentDataScopeHint.vue'
import { loadPermissionContext, getPermissionContext } from '@/modules/workflow/context/permission.context'

const MENUS = [
  { key: 'stu-overview', label: '主档概览', icon: '◫', path: '/admin/student' },
  { key: 'stu-list', label: '学生列表', icon: '☰', path: '/admin/student/list' },
  { key: 'stu-identity', label: '身份认证', icon: '◈', path: '/admin/student/identity' },
  { key: 'stu-status', label: '状态管理', icon: '◐', path: '/admin/student/status' },
  { key: 'stu-import-export', label: '导入导出', icon: '⇅', path: '/admin/student/import-export' }
]

export default {
  name: 'AdminStudentLayout',
  components: { BasePortalLayout, StudentDataScopeHint },
  data() {
    return { menus: MENUS, ready: false }
  },
  computed: {
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus].sort((a, b) => b.path.length - a.path.length).find((m) => path === m.path || path.startsWith(m.path + '/'))
      // 详情页 /admin/student/:id 归于列表
      if (!hit && /^\/admin\/student\/stu-/.test(path)) return 'stu-list'
      return hit ? hit.key : 'stu-overview'
    },
    userName() {
      return getPermissionContext()?.userName || '管理员'
    }
  },
  async created() {
    await loadPermissionContext()
    this.ready = true
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.sl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
