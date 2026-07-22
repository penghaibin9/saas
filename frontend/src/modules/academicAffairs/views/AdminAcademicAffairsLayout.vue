<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="教务中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载教务中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminAcademicAffairsLayout — /admin/academic-affairs 父布局（13B 教务中心）。
 * 侧栏二级/三级菜单由 BasePortalLayout + navPlan.js（getVisibleNavPlan）渲染，禁止在此硬编码业务菜单。
 * 品牌名 / 角色 / 数据范围来自 academicAffairsApi.getContext()；ctx 下发给子路由避免重复拉取。
 * 参照 modules/internship/views/AdminInternshipLayout.vue（同一布局底座）。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsPickerAdapters } from '@/modules/academicAffairs/pickerAdapters'
import router from '@/router'

export default {
  name: 'AdminAcademicAffairsLayout',
  components: { BasePortalLayout, LoadingState },
  provide() {
    return { appPickerAdapters: academicAffairsPickerAdapters }
  },
  data() {
    return { ctx: null }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    }
  },
  async created() {
    const res = await academicAffairsApi.getContext()
    if (res.code === 0) this.ctx = res.data
  },
  methods: {
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        router.push(item.path).catch(() => {})
      }
    }
  }
}
</script>
