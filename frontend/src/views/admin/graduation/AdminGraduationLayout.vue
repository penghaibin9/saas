<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="毕业设计中心"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载毕业设计中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminGraduationLayout — /admin/graduation 父布局。
 * 品牌名 / 角色 / 数据范围来自 graduationApi.getContext()，禁止硬编码。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'

const MENUS = [
  { key: 'gd-dashboard', label: '管理看板', icon: '◫', path: '/admin/graduation' },
  { key: 'gd-students', label: '毕设学生', icon: '☰', path: '/admin/graduation/students' },
  { key: 'gd-topics', label: '选题管理', icon: '◈', path: '/admin/graduation/topics' },
  { key: 'gd-proposals', label: '开题材料', icon: '✎', path: '/admin/graduation/proposals' },
  { key: 'gd-finals', label: '成果提交', icon: '▤', path: '/admin/graduation/finals' },
  { key: 'gd-defense', label: '答辩安排', icon: '◐', path: '/admin/graduation/defense' }
]

export default {
  name: 'AdminGraduationLayout',
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
      return hit ? hit.key : 'gd-dashboard'
    }
  },
  async created() {
    const res = await graduationApi.getContext()
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
.gl-scope {
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
.gl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
