<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="教务中心 · 学业过程"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载学业过程中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminAcademicLayout — /admin/academic 父布局。
 * P6：已移除演示角色假切换；切身份须走真实 /auth/switch-role。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { getAcademicContext } from '@/modules/academicAffairs/api/academic.api'

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
    }
  }
}
</script>
