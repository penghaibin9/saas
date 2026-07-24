<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="工作台 · 审批中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载审批中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminApprovalLayout — /admin/approval 父布局（待办/审批闭环，区别于 /admin/workflow）。
 * 品牌名 / 角色 / 数据范围全部来自 approvalApi.getContext()，禁止硬编码。
 * P6：已移除「切换角色」假视角；切身份须走真实 /auth/switch-role。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { approvalApi } from '@/modules/approval/api/approval.api'

export default {
  name: 'AdminApprovalLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { ctx: null, todoCount: 0 }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    },
    menus() {
      return [
        { key: 'ap-dashboard', label: '待办看板', icon: '◫', path: '/admin/approval' },
        {
          key: 'ap-todos',
          label: '我的待办',
          icon: '☰',
          path: '/admin/approval/todos',
          badge: this.todoCount || ''
        },
        { key: 'ap-done', label: '已办 · 抄送', icon: '✓', path: '/admin/approval/done' },
        { key: 'ap-returned', label: '退回记录', icon: '↩', path: '/admin/approval/returned' },
        { key: 'ap-templates', label: '审批模板', icon: '⚙', path: '/admin/approval/templates' }
      ]
    },
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus]
        .sort((a, b) => b.path.length - a.path.length)
        .find((m) => path === m.path || path.startsWith(m.path + '/'))
      return hit ? hit.key : 'ap-dashboard'
    }
  },
  watch: {
    '$route.path'() {
      this.refreshBadge()
    }
  },
  created() {
    this.loadContext()
  },
  methods: {
    async loadContext() {
      const res = await approvalApi.getContext()
      if (res.code === 0) {
        this.ctx = res.data
        this.todoCount = res.data.todoCount
      }
    },
    async refreshBadge() {
      const res = await approvalApi.getTodoSummary()
      if (res.code === 0) this.todoCount = res.data.total
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.al-scope {
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
</style>
