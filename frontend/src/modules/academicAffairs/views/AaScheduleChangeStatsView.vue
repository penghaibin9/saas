<template>
  <ModulePageShell
    title="调停课统计"
    subtitle="申请量与已生效课次数量分开，统计不替代正式台账"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <template #actions><AppButton variant="primary" @click="openLedger()">查看关联办理</AppButton></template>
    <div class="mp-stack">
      <div class="sc-filter">
        <label class="sc-filter__item">学期ID
          <AppTermEntityPicker v-model="termId" placeholder="全部学期" />
        </label>
        <AppButton :loading="loading" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!stat || !stat.total" title="暂无调停课记录" description="所选范围/学期暂无调课、停课、补课数据" />
      <template v-else>
        <div class="sc-metrics">
          <AppMetricCard title="当前统计范围" :value="termId ? `学期 #${termId}` : '全部学期'" accent="primary" />
          <AppMetricCard title="范围内申请" :value="stat.total" unit="单" accent="primary" />
          <AppMetricCard title="待办理" :value="pendingCount" unit="单" accent="warning" />
          <AppMetricCard title="完成比例" :value="completionRate" unit="%" accent="success" />
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
        <section class="sc-drilldown">
          <header><h2>同口径明细下钻</h2><span>申请量、终态与生效量保持分列</span></header>
          <button v-for="item in drilldowns" :key="item.label" @click="openLedger(item.query)"><strong>{{ item.value }}</strong><span>{{ item.label }}</span></button>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 调停课统计（/admin/academic-affairs/schedule-change/stats）：只读聚合看板，范围收敛复用 build_affairs_context。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppRankingChart, AppTermEntityPicker } from '@/components/common'
import { scheduleChangeApi } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { currentUserFromToken } from '@/services/http/client'

export default {
  name: 'AaScheduleChangeStatsView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppMetricCard, AppRankingChart, AppTermEntityPicker },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return { loading: true, error: '', termId: '', stat: null, loadSeq: 0 }
  },
  computed: {
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    roleName() { return this.ctx?.currentRole?.roleName || '教务' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    pendingCount() {
      if (!this.stat) return 0
      const s = this.stat.byStatus
      return (s.SUBMITTED || 0) + (s.COLLEGE_REVIEW || 0) + (s.ACADEMIC_REVIEW || 0) + (s.APPROVED || 0)
    },
    completionRate() { return this.stat?.total ? Math.round(((this.stat.byStatus.APPLIED || 0) / this.stat.total) * 1000) / 10 : 0 },
    drilldowns() {
      const byType = this.stat?.byType || {}, byStatus = this.stat?.byStatus || {}
      return [
        { label: '调课申请', value: byType.ADJUST || 0, query: { changeType: 'ADJUST' } },
        { label: '停课申请', value: byType.STOP || 0, query: { changeType: 'STOP' } },
        { label: '补课申请', value: byType.MAKEUP || 0, query: { changeType: 'MAKEUP' } },
        { label: '已生效课次', value: byStatus.APPLIED || 0, query: { status: 'APPLIED' } },
        { label: '未生效', value: Math.max(0, Number(this.stat?.total || 0) - Number(byStatus.APPLIED || 0)), query: {} }
      ]
    }
  },
  watch: { identityKey() { this.loadSeq++; this.stat = null; this.load() } },
  created() { this.load() },
  beforeUnmount() { this.loadSeq++ },
  methods: {
    async load() {
      const seq = ++this.loadSeq, identity = this.identityKey, termId = this.termId
      const current = () => seq === this.loadSeq && identity === this.identityKey && termId === this.termId
      this.loading = true; this.error = ''
      try {
        const res = await scheduleChangeApi.stats({ termId })
        if (!current()) return
        if (res.code === 0) this.stat = res.data
        else { this.stat = null; this.error = res.message || '调停课统计加载失败' }
      } catch (error) { if (current()) { this.stat = null; this.error = error?.message || '调停课统计加载失败' } }
      finally { if (current()) this.loading = false }
    },
    openLedger(query = {}) {
      this.$router.push({ path: '/admin/academic-affairs/schedule-change', query: { ...(this.termId ? { termId: this.termId } : {}), ...query } })
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
.sc-drilldown { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); border: 1px solid var(--line, #dce4ee); border-radius: 12px; overflow: hidden; background: var(--bg-card, #fff); }.sc-drilldown header { grid-column: 1 / -1; display: flex; justify-content: space-between; gap: 16px; padding: 15px 18px; border-bottom: 1px solid var(--line, #dce4ee); }.sc-drilldown h2 { margin: 0; font-size: 16px; }.sc-drilldown header span { color: var(--t2, #52647a); font-size: 12px; }.sc-drilldown button { display: grid; gap: 5px; border: 0; border-right: 1px solid var(--line, #dce4ee); padding: 16px; background: transparent; color: inherit; cursor: pointer; text-align: left; }.sc-drilldown button:last-child { border-right: 0; }.sc-drilldown button strong { color: var(--pri, #2563eb); font-size: 20px; }.sc-drilldown button span { color: var(--t2, #52647a); font-size: 12px; }
@media (max-width: 960px) { .sc-charts { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .sc-drilldown { grid-template-columns: 1fr; }.sc-drilldown button { border-right: 0; border-bottom: 1px solid var(--line, #dce4ee); } }
</style>
