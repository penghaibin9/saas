<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="工作台 · 审批中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <label v-if="ctx" class="al-role">
        <span class="al-role__label">切换角色</span>
        <select
          class="al-role__select"
          :value="ctx.currentRole.roleCode"
          :disabled="switching"
          @change="onRoleChange($event.target.value)"
        >
          <option v-for="r in ctx.availableRoles" :key="r.roleCode" :value="r.roleCode">
            {{ r.roleName }} · {{ r.userName }}
          </option>
        </select>
      </label>
    </template>
    <router-view v-if="ctx" :key="ctx.currentRole.roleCode" :ctx="ctx" />
    <LoadingState v-else text="正在加载审批中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminApprovalLayout — /admin/approval 父布局（待办/审批闭环，区别于 /admin/workflow）。
 * 品牌名 / 角色 / 数据范围全部来自 approvalApi.getContext()，禁止硬编码。
 * ctx 通过 props 下发子路由页面；切换角色后重新拉取 ctx，并用 :key 触发子页刷新。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { approvalApi } from '@/modules/approval/api/approval.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AdminApprovalLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { ctx: null, todoCount: 0, switching: false }
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
    async onRoleChange(roleCode) {
      if (!this.ctx || roleCode === this.ctx.currentRole.roleCode) return
      this.switching = true
      const res = await approvalApi.switchRole(roleCode)
      if (res.code === 0) {
        await this.loadContext()
        toast.success('已切换至 ' + res.data.roleName + '（' + res.data.userName + '）视角，数据范围已更新')
      } else {
        toast.error(res.message)
      }
      this.switching = false
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
.al-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
.al-role {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
}
.al-role__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.al-role__select {
  height: 30px;
  max-width: 200px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: 0 var(--space-2);
  outline: none;
  cursor: pointer;
  transition: border-color var(--motion-fast) var(--ease-standard);
}
.al-role__select:focus {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px var(--primary-50);
}
.al-role__select:disabled {
  color: var(--text-disabled);
  cursor: not-allowed;
}
</style>
