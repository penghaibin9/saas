<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="岗位实习中心"
    :ctx="ctx"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载岗位实习中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminInternshipLayout — /admin/internship 父布局。
 * 侧栏二级/三级菜单由 BasePortalLayout + navPlan.js（getVisibleNavPlan）渲染，禁止在此硬编码业务菜单。
 * 品牌名 / 角色 / 数据范围来自 internshipApi.getContext()；ctx 下发给子路由避免重复拉取。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'

export default {
  name: 'AdminInternshipLayout',
  components: { BasePortalLayout, LoadingState },
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
    const res = await internshipApi.getContext()
    if (res.code === 0) this.ctx = res.data
  }
}
</script>
