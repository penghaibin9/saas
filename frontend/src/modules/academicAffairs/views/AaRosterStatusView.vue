<template>
  <ModulePageShell
    title="学籍状态"
    subtitle="学籍状态分布总览 · 点击状态卡片下钻学籍名册"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="summary">
        <div class="aa-metric-row">
          <AppMetricCard title="学生总数" :value="summary.total" unit="人" accent-tone="primary" />
          <AppMetricCard title="在籍学生" :value="summary.enrolledCount" unit="人" accent-tone="success" />
          <AppMetricCard title="非在籍" :value="summary.notEnrolledCount" unit="人" accent-tone="warning" />
          <AppMetricCard title="近 30 天生效异动" :value="summary.recentChanges30d" unit="次" accent-tone="risk" />
        </div>

        <AppSectionCard title="学籍状态分布（13 态）" subtitle="点击卡片查看该状态下的学籍名册">
          <EmptyState v-if="!summary.byStatus.length" title="暂无学生数据" />
          <div v-else class="aa-status-grid">
            <button
              v-for="row in summary.byStatus"
              :key="row.status"
              class="aa-status-cell"
              @click="goRoster(row.status)"
            >
              <AppStatusTag :status="row.status" dot>{{ row.label }}</AppStatusTag>
              <span class="aa-status-cell__count">{{ row.count }}</span>
            </button>
          </div>
        </AppSectionCard>

        <AppSectionCard title="学籍状态迁移说明" subtitle="受控扩展枚举（t_student_profile.student_status），仅四类受控入口可变更">
          <p class="mp-note">
            学籍状态不可在页面直改，只能由「入学/学年注册确认」「学籍异动生效（休学/复学/退学/留级/转专业）」
            「毕业审核发布」三类受控入口驱动流转，全部写入 change_student_status() 单一入口并留痕 360 时间线。
            如需变更学生学籍状态，请前往「学籍异动」发起对应申请。
          </p>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 学籍状态总览（/admin/academic-affairs/roster/status）：GET /academic-affairs/roster/status-summary。
 * 只读聚合展示，状态变更统一走「学籍异动」（不重复实现审批链）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppMetricCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaRosterStatusView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppMetricCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', summary: null }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRosterStatusSummary()
      if (res.code === 0) {
        this.summary = res.data
      } else {
        this.error = res.message
      }
      this.loading = false
    },
    goRoster(status) {
      this.$router.push({ path: '/admin/academic-affairs/roster', query: { status } })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-metric-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-4); }
.aa-status-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--space-3); }
.aa-status-cell {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-base); border-radius: var(--radius-base);
  background: var(--bg-card); cursor: pointer; text-align: left;
}
.aa-status-cell:hover { border-color: var(--primary-400); background: var(--bg-section-blue); }
.aa-status-cell__count { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
</style>
