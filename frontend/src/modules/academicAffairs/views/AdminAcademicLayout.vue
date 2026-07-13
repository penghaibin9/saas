<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="教务中心 · 学业过程"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <label v-if="ctx" class="al-role-switch" title="演示环境：切换角色查看权限与数据范围差异">
        <span class="al-role-switch__label">角色</span>
        <select class="al-role-switch__select" :value="ctx.currentRole.roleId" @change="onSwitchRole($event.target.value)">
          <option v-for="r in ctx.roles" :key="r.roleId" :value="r.roleId">{{ r.roleName }} · {{ r.userName }}</option>
        </select>
      </label>
    </template>
    <router-view v-if="ctx" :key="ctx.currentRole.roleId" :ctx="ctx" />
    <LoadingState v-else text="正在加载学业过程中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminAcademicLayout — /admin/academic 父布局。
 * 品牌名 / 角色 / 数据范围 / 权限动作全部来自 academic.api 的 getAcademicContext()，禁止硬编码。
 * 支持角色切换（演示多角色指标与按钮差异），ctx 通过 props 下发给子路由页面。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { getAcademicContext, switchAcademicRole } from '@/modules/academicAffairs/api/academic.api'
import { toast } from '@/utils/toast'

const MENUS = [
  { key: 'acad-dashboard', label: '管理看板', icon: '◫', path: '/admin/academic' },
  { key: 'acad-students', label: '学业学生', icon: '☰', path: '/admin/academic/students' },
  { key: 'acad-grades', label: '课程成绩', icon: '✎', path: '/admin/academic/grades' },
  { key: 'acad-credits', label: '学分修读', icon: '◔', path: '/admin/academic/credits' },
  { key: 'acad-makeup', label: '补考重修', icon: '↻', path: '/admin/academic/makeup-retake' },
  { key: 'acad-warnings', label: '学业预警', icon: '◐', path: '/admin/academic/warnings' }
]

export default {
  name: 'AdminAcademicLayout',
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
      return hit ? hit.key : 'acad-dashboard'
    }
  },
  async created() {
    const res = await getAcademicContext()
    if (res.code === 0) this.ctx = res.data
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    async onSwitchRole(roleId) {
      const res = await switchAcademicRole(roleId)
      if (res.code === 0) {
        this.ctx = res.data
        toast.info(`已切换为「${res.data.currentRole.roleName}」，数据范围：${res.data.dataScope.name}`)
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.al-role-switch {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.al-role-switch__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.al-role-switch__select {
  height: 28px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  padding: 0 var(--space-1);
  max-width: 190px;
}
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
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.al-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
