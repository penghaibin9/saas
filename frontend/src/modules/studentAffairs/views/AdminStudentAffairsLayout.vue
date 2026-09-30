<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="学工中心"
    :ctx="ctx"
    :workspace="isCoreWorkspace"
    @menu-select="onMenuSelect"
  >
    <ErrorState
      v-if="loadError"
      title="无法加载学工身份上下文"
      :description="loadError"
      @retry="goLogin"
    />
    <div v-else-if="ctx" class="student-affairs-ui-scope" :class="{ 'sa-compact-workspace': isCoreWorkspace, 'sa-aid-workspace': isAidWorkspace }">
      <div v-if="showSla || showTempExpiry" class="sa-context-stack">
        <details v-if="showSla" class="sa-leave-sla">
          <summary>{{ isLeaveWorkspace ? '查看请假办理时限' : '查看办理时限' }}</summary>
          <StudentAffairsSlaStrip :kind="isLeaveWorkspace ? 'leave' : 'both'" />
        </details>
        <CounselorTempExpiryPanel
          v-if="showTempExpiry"
          :ctx="ctx"
        />
      </div>
      <router-view v-slot="{ Component }">
        <KeepAlive :include="['LeaveApprovalWorkbenchView', 'LeaveExtensionCancelView', 'LeaveLedgerView', 'LeaveStatsView']" :max="4">
          <component :is="Component" :ctx="ctx" />
        </KeepAlive>
      </router-view>
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
 * W5：看板/风险/请假按权限展示服务器 SLA 真值；责任台账页额外挂临时代班到期幂等同步兜底，不改业务菜单。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { studentAffairsPickerAdapters } from '@/modules/studentAffairs/pickerAdapters'
import StudentAffairsSlaStrip from '@/modules/studentAffairs/components/StudentAffairsSlaStrip.vue'
import CounselorTempExpiryPanel from '@/modules/studentAffairs/components/CounselorTempExpiryPanel.vue'
import { matchPermission } from '@/config/navPlan'
import router from '@/router'

export default {
  name: 'AdminStudentAffairsLayout',
  components: { BasePortalLayout, LoadingState, ErrorState, StudentAffairsSlaStrip, CounselorTempExpiryPanel },
  provide() {
    return { appPickerAdapters: studentAffairsPickerAdapters, conciseBusinessHeader: true, affairsWorkspace: true }
  },
  data() {
    return { ctx: null, loadError: '' }
  },
  computed: {
    isLeaveWorkspace() { return this.$route.path.startsWith('/admin/student-affairs/leave') },
    isAidWorkspace() { return this.$route.path === '/admin/student-affairs/aid' || this.$route.path.startsWith('/admin/student-affairs/aid/') },
    isFundingWorkspace() { return this.$route.path === '/admin/student-affairs/funding' || this.$route.path.startsWith('/admin/student-affairs/funding/') },
    // 本布局下所有业务、详情和编辑页统一使用新壳，不再逐页维护白名单。
    isCoreWorkspace() { return true },
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    },
    permissionPatterns() {
      return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : []
    },
    showSla() {
      const path = String(this.$route.path || '')
      const operationalPage = path === '/admin/student-affairs/dashboard' || path.startsWith('/admin/student-affairs/risk') || path.startsWith('/admin/student-affairs/leave')
      if (!operationalPage) return false
      return matchPermission(this.permissionPatterns, 'studentAffairs.stats.view') || matchPermission(this.permissionPatterns, 'studentAffairs.dashboard.view')
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
.sa-leave-sla { font-size: 12px; color: var(--text-secondary); }
.sa-leave-sla summary { cursor: pointer; padding: 4px 0; width: fit-content; }
.sa-leave-sla[open] summary { margin-bottom: 8px; }
.sa-compact-workspace :deep(.mps__head) { min-height: auto; padding: 0 0 10px; margin: 0; border-bottom: 1px solid var(--line); background: transparent; box-shadow: none; border-radius: 0; align-items: center; }
.sa-compact-workspace :deep(.mps__title) { font-size: 20px; }
.sa-compact-workspace :deep(.mps__subtitle) { font-size: 12px; margin-top: 4px; }
.sa-compact-workspace :deep(.mps) { gap: 12px; }
.sa-compact-workspace :deep(.mp-stack) { gap: 12px; }
.sa-compact-workspace .sa-context-stack { margin-bottom: 8px; }
.sa-aid-workspace :deep(.app-metric-card) { padding: 12px 16px; min-height: 0; background: var(--surface); border: 1px solid var(--line); box-shadow: none; }
.sa-aid-workspace :deep(.app-metric-card__value) { font-size: 24px; }
.sa-aid-workspace :deep(.app-metric-card__footer:empty) { display: none; }
.sa-aid-workspace :deep(.sa-grid--metrics) { gap: 10px; }
.sa-aid-workspace :deep(.bf-input) { background: var(--field-bg); color: var(--t1); }
.sa-context-stack {
  display: grid;
  width: 100%;
  min-width: 0;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
