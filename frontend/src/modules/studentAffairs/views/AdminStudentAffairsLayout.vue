<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="学工中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <template #menu>
      <StudentAffairsWorkspaceNav v-if="ctx" :ctx="ctx" />
    </template>

    <ErrorState
      v-if="loadError"
      title="无法加载学工身份上下文"
      :description="loadError"
      @retry="goLogin"
    />
    <div v-else-if="ctx" class="student-affairs-ui-scope">
      <div v-if="showSla || showTempExpiry" class="sa-context-stack">
        <StudentAffairsSlaStrip v-if="showSla" kind="both" />
        <CounselorTempExpiryPanel
          v-if="showTempExpiry"
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
 * AdminStudentAffairsLayout — /admin/student-affairs 与兼容 campus-service 学工页父布局。
 *
 * V6：完整 navPlan 继续作为搜索与能力事实目录；教师左侧改为 12 个工作区 + 当前工作区三级页投影。
 * 真实 route、permission、ctx、数据范围和旧地址保持不变。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { studentAffairsPickerAdapters } from '@/modules/studentAffairs/pickerAdapters'
import StudentAffairsSlaStrip from '@/modules/studentAffairs/components/StudentAffairsSlaStrip.vue'
import CounselorTempExpiryPanel from '@/modules/studentAffairs/components/CounselorTempExpiryPanel.vue'
import StudentAffairsWorkspaceNav from '@/modules/studentAffairs/components/StudentAffairsWorkspaceNav.vue'
import { matchPermission } from '@/config/navPlan'
import router from '@/router'

export default {
  name: 'AdminStudentAffairsLayout',
  components: {
    BasePortalLayout,
    LoadingState,
    ErrorState,
    StudentAffairsSlaStrip,
    CounselorTempExpiryPanel,
    StudentAffairsWorkspaceNav
  },
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
    },
    permissionPatterns() {
      return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : []
    },
    showSla() {
      const path = String(this.$route.path || '')
      const operationalPage = path === '/admin/student-affairs/dashboard' ||
        path.startsWith('/admin/student-affairs/risk') ||
        path.startsWith('/admin/student-affairs/leave')
      if (!operationalPage) return false
      return matchPermission(this.permissionPatterns, 'studentAffairs.stats.view') ||
        matchPermission(this.permissionPatterns, 'studentAffairs.dashboard.view')
    },
    showTempExpiry() {
      return this.$route.name === 'student-affairs-counselor-assignments'
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
.sa-context-stack {
  display: grid;
  width: 100%;
  min-width: 0;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
