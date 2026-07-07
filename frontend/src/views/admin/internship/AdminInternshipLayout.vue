<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="岗位实习中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载岗位实习中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminInternshipLayout — /admin/internship 父布局。
 * 品牌名 / 角色 / 数据范围全部来自 internshipApi.getContext()，禁止硬编码。
 * ctx 通过 props 下发给子路由页面，避免每页重复拉取。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'

const MENUS = [
  { key: 'int-dashboard', label: '管理看板', icon: '◫', path: '/admin/internship' },
  { key: 'int-batches', label: '实习批次', icon: '▤', path: '/admin/internship/batches' },
  { key: 'int-students', label: '实习学生', icon: '☰', path: '/admin/internship/students' },
  { key: 'int-exceptions', label: '打卡异常', icon: '◔', path: '/admin/internship/exceptions' },
  { key: 'int-reports', label: '周报批阅', icon: '✎', path: '/admin/internship/reports' },
  { key: 'int-risks', label: '风险学生', icon: '◐', path: '/admin/internship/risks' }
]

export default {
  name: 'AdminInternshipLayout',
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
      return hit ? hit.key : 'int-dashboard'
    }
  },
  async created() {
    const res = await internshipApi.getContext()
    if (res.code === 0) this.ctx = res.data
  },
  methods: {
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.il-scope {
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
.il-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
