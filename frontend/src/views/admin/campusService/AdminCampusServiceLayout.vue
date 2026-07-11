<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="学工中心 · 在校服务"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <label v-if="ctx" class="csl-role-switch" title="演示环境：切换角色查看权限与数据范围差异">
        <span class="csl-role-switch__label">角色</span>
        <select class="csl-role-switch__select" :value="ctx.currentRole.roleId" @change="onSwitchRole($event.target.value)">
          <option v-for="r in ctx.roles" :key="r.roleId" :value="r.roleId">{{ r.roleName }} · {{ r.userName }}</option>
        </select>
      </label>
    </template>
    <router-view v-if="ctx" :key="ctx.currentRole.roleId" :ctx="ctx" />
    <LoadingState v-else text="正在加载在校服务中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminCampusServiceLayout — /admin/campus-service 父布局。
 * 品牌名 / 角色 / 数据范围 / 权限动作全部来自 campusService.api 的 getCampusServiceContext()，禁止硬编码。
 * 支持角色切换（辅导员/学院管理员/学工/宿管/资助/心理），ctx 通过 props 下发给子路由页面。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { getCampusServiceContext, switchCampusServiceRole } from '@/modules/campusService/api/campusService.api'
import { toast } from '@/utils/toast'

const MENUS = [
  { key: 'cs-dashboard', label: '服务工作台', icon: '◫', path: '/admin/campus-service' },
  { key: 'cs-students', label: '学生服务', icon: '☰', path: '/admin/campus-service/students' },
  { key: 'cs-classes', label: '班级管理', icon: '❑', path: '/admin/campus-service/classes' },
  { key: 'cs-counselor-eval', label: '辅导员考评', icon: '✦', path: '/admin/campus-service/counselor-assessment' },
  { key: 'cs-leave', label: '请假审批', icon: '✈', path: '/admin/campus-service/leave' },
  { key: 'cs-leave-ext', label: '延期销假', icon: '↺', path: '/admin/campus-service/leave-extensions' },
  { key: 'cs-leave-ledger', label: '请假台账', icon: '▤', path: '/admin/campus-service/leave-ledger' },
  { key: 'cs-leave-stats', label: '请假统计', icon: '◔', path: '/admin/campus-service/leave-stats' },
  { key: 'cs-grants', label: '奖助资助', icon: '❖', path: '/admin/campus-service/grants' },
  { key: 'cs-dorm', label: '宿舍服务', icon: '⌂', path: '/admin/campus-service/dormitory' },
  { key: 'cs-discipline', label: '违纪处分', icon: '§', path: '/admin/campus-service/discipline' },
  { key: 'cs-workorders', label: '服务工单', icon: '✎', path: '/admin/campus-service/work-orders' }
]

export default {
  name: 'AdminCampusServiceLayout',
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
      return hit ? hit.key : 'cs-dashboard'
    }
  },
  async created() {
    const res = await getCampusServiceContext()
    if (res.code === 0) this.ctx = res.data
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    async onSwitchRole(roleId) {
      const res = await switchCampusServiceRole(roleId)
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
.csl-role-switch {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.csl-role-switch__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.csl-role-switch__select {
  height: 28px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  padding: 0 var(--space-1);
  max-width: 190px;
}
.csl-scope {
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
.csl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
