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
    <div v-else-if="ctx" class="student-affairs-ui-scope">
      <div class="sa-ops-stack">
        <StudentAffairsSlaStrip kind="both" />
        <CounselorTempExpiryPanel
          v-if="$route.name === 'student-affairs-counselor-assignments'"
          :ctx="ctx"
        />
      </div>
      <router-view :ctx="ctx" />
    </div>
    <LoadingState v-else text="正在加载学工中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminStudentAffairsLayout — /admin/student-affairs 父布局。
 * 2026-07-12：从硬编码横向 tab 改为 navPlan 驱动（对齐 AdminInternshipLayout），
 * 侧栏二级/三级由 BasePortalLayout + navPlan.js「学工中心」组统一渲染，让学工中心 14 二级真正显示；
 * 禁止在此硬编码业务菜单。品牌名 / 角色 / 数据范围来自 studentAffairsApi.getContext()，ctx 下发给子路由。
 * W5：父布局统一展示服务器 SLA 真值；责任台账页额外挂临时代班到期幂等同步兜底，不改业务菜单。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { studentAffairsPickerAdapters } from '@/modules/studentAffairs/pickerAdapters'
import StudentAffairsSlaStrip from '@/modules/studentAffairs/components/StudentAffairsSlaStrip.vue'
import CounselorTempExpiryPanel from '@/modules/studentAffairs/components/CounselorTempExpiryPanel.vue'
import router from '@/router'

export default {
  name: 'AdminStudentAffairsLayout',
  components: { BasePortalLayout, LoadingState, ErrorState, StudentAffairsSlaStrip, CounselorTempExpiryPanel },
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

<style src="@/modules/studentAffairs/styles/usability.css"></style>
<style scoped>
.sa-ops-stack { display: grid; gap: 10px; margin-bottom: 12px; }
</style>