<template>
  <ModulePageShell
    title="调停课统计"
    subtitle="按类型/状态/学院/教师聚合调课·停课·补课发生频率，辅助识别异常高频调整"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <div class="mp-stack">
      <div class="sc-filter">
        <label class="sc-filter__item">学期ID
          <input v-model.trim="termId" class="sc-in sc-in--sm" placeholder="可空=全部学期" @keyup.enter="load" />
        </label>
        <button class="mp-btn" :disabled="loading" @click="load">查询</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!stat || !stat.total" title="暂无调停课记录" description="所选范围/学期暂无调课、停课、补课数据" />
      <template v-else>
        <div class="sc-metrics">
          <AppMetricCard title="总单量" :value="stat.total" accent="primary" />
          <AppMetricCard title="调课" :value="stat.byType.ADJUST || 0" accent="primary" />
          <AppMetricCard title="停课" :value="stat.byType.STOP || 0" accent="warning" />
          <AppMetricCard title="补课" :value="stat.byType.MAKEUP || 0" accent="primary" />
          <AppMetricCard title="已生效" :value="stat.byStatus.APPLIED || 0" accent="success" />
          <AppMetricCard title="已驳回" :value="stat.byStatus.REJECTED || 0" accent="risk" />
          <AppMetricCard title="审批中" :value="pendingCount" accent="warning" />
          <AppMetricCard title="已撤销" :value="stat.byStatus.CANCELLED || 0" />
        </div>

        <div class="sc-charts">
          <AppRankingChart
            title="按学院分布"
            subtitle="学院管理员仅见本学院合计；教务处见全校（数据范围已在查询侧收敛）"
            :data="stat.byCollege"
            label-field="collegeName"
            value-field="count"
            value-label="调停课单量"
            unit="单"
          />
          <AppRankingChart
            title="教师调停课频率 TOP10"
            subtitle="用于识别异常高频调课的教师/课程，非绩效评价结论"
            :data="stat.topTeachers"
            label-field="teacherName"
            value-field="count"
            value-label="调停课单量"
            unit="单"
          />
        </div>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 调停课统计（/admin/academic-affairs/schedule-change/stats）：只读聚合看板，范围收敛复用 build_affairs_context。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppRankingChart } from '@/components/common'
import { scheduleChangeApi } from '@/modules/academicAffairs/api/academic-schedule-change.api'

export default {
  name: 'AaScheduleChangeStatsView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppMetricCard, AppRankingChart },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return { loading: true, error: '', termId: '', stat: null }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '教务' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    pendingCount() {
      if (!this.stat) return 0
      const s = this.stat.byStatus
      return (s.SUBMITTED || 0) + (s.COLLEGE_REVIEW || 0) + (s.ACADEMIC_REVIEW || 0) + (s.APPROVED || 0)
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const res = await scheduleChangeApi.stats({ termId: this.termId })
      if (res.code === 0) this.stat = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-filter { display: flex; align-items: flex-end; gap: var(--space-3); }
.sc-filter__item { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--t2, #475569); }
.sc-in--sm { padding: 6px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; width: 180px; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; height: 33px; }
.sc-metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-3); }
.sc-charts { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
@media (max-width: 960px) { .sc-charts { grid-template-columns: 1fr; } }
</style>
