<template>
  <BasePortalLayout :title="brandTitle" subtitle="学工中心" :ctx="ctx" @menu-select="onMenuSelect">
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载学工中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminStudentAffairsLayout — /admin/student-affairs 父布局。
 * 品牌名 / 角色 / 数据范围来自 studentAffairsApi.getContext()（真实共享端点），禁止硬编码。
 * 侧栏三级树由 BasePortalLayout 依 navPlan「学工中心」组自动渲染（传 ctx、不传 menus/#menu），
 * rail 高亮与三级高亮由 adminMenu.js / navPlan.js 统一驱动（对齐 CLAUDE.md §9.4 高亮铁律）。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

export default {
  name: 'AdminStudentAffairsLayout',
  components: { BasePortalLayout, LoadingState },
  data() {
    return { ctx: null }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return (this.ctx.tenantBrandConfig.schoolName || '学工中心') + ' · 管理端'
    }
  },
  async created() {
    const res = await studentAffairsApi.getContext()
    if (res.code === 0) this.ctx = res.data
  },
  methods: {
    onMenuSelect(item) {
      // navPlan 驱动模式下叶子/rail 由 BasePortalLayout 内部自导航；此处仅作兜底，避免重复 push。
      if (item.path && item.path !== this.$route.fullPath) this.$router.push(item.path)
    }
  }
}
</script>
