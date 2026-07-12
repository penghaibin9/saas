<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="学工中心 · 学生画像"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <label v-if="ctx" class="sl-role-switch">
        <span class="sl-role-switch__label">演示角色</span>
        <select :value="ctx.currentRole.roleCode" @change="onSwitchRole($event.target.value)">
          <option v-for="r in ctx.availableRoles" :key="r.value" :value="r.value">{{ r.label }}</option>
        </select>
      </label>
    </template>
    <router-view v-if="ctx" :key="ctxVersion" :ctx="ctx" />
    <LoadingState v-else text="正在加载学生中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminStudentLayout — /admin/student 父布局（模块内导航，不改全局菜单体系）。
 * 品牌名 / 角色 / 数据范围全部来自 studentApi.getContext()，禁止硬编码；
 * ctx 经 props 下发子路由页面；顶部提供演示角色切换（体现权限 / 数据范围差异）。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { studentApi } from '@/modules/student/api/student.api'
import { registerStudentRoutes } from '@/modules/student/student.routes'

export default {
  name: 'AdminStudentLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { ctx: null, ctxVersion: 0 }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    }
  },
  async created() {
    // 模块内兜底注册（仅补注全局缺失的新页面路由，不修改全局 router 文件）
    registerStudentRoutes(this.$router)
    await this.loadContext()
  },
  methods: {
    async loadContext() {
      const res = await studentApi.getContext()
      if (res.code === 0) {
        this.ctx = res.data
        this.ctxVersion++
      }
    },
    async onSwitchRole(roleCode) {
      const res = await studentApi.switchRole(roleCode)
      if (res.code === 0) await this.loadContext()
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
/* 角色切换（演示多角色权限差异） */
.sl-role-switch {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.sl-role-switch__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.sl-role-switch select {
  height: 28px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  padding: 0 var(--space-2);
  outline: none;
}
.sl-role-switch select:focus {
  border-color: var(--primary-500);
}
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
