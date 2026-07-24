<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="学工中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <ErrorState
      v-if="loadError"
      title="无法加载学工身份上下文"
      :description="loadError"
      @retry="goLogin"
    />
    <router-view v-else-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载学工中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminStudentAffairsLayout — /admin/student-affairs 父布局。
 * 2026-07-12：从硬编码横向 tab 改为 navPlan 驱动（对齐 AdminInternshipLayout），
 * 侧栏二级/三级由 BasePortalLayout + navPlan.js「学工中心」组统一渲染，让学工中心 14 二级真正显示；
 * 禁止在此硬编码业务菜单。品牌名 / 角色 / 数据范围来自 studentAffairsApi.getContext()，ctx 下发给子路由。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { studentAffairsPickerAdapters } from '@/modules/studentAffairs/pickerAdapters'
import router from '@/router'

export default {
  name: 'AdminStudentAffairsLayout',
  components: { BasePortalLayout, LoadingState, ErrorState },
  provide() {
    return { appPickerAdapters: studentAffairsPickerAdapters }
  },
  data() {
    return { ctx: null, loadError: '' }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    }
  },
  async created() {
    const res = await studentAffairsApi.getContext()
    if (res.code !== 0) {
      this.loadError = res.message || '学工上下文加载失败'
      return
    }
    // 正式环境：RBAC 失败不得构造「看似正常但权限为空」的业务壳
    if (import.meta.env.PROD && res.data && res.data.rbacOk === false) {
      this.loadError = '身份权限上下文不可用，请重新登录后再进入学工中心'
      return
    }
    this.ctx = res.data
  },
  methods: {
    goLogin() {
      router.replace({ path: '/login', query: { redirect: this.$route.fullPath } }).catch(() => {})
    },
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        router.push(item.path).catch(() => {})
      }
    }
  }
}
</script>
