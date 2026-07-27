<template>
  <AppPageShell
    title="心理统计"
    subtitle="仅聚合口径：按状态 / 等级的数量分布与在办危机数；严禁下钻到任何学生个体明细。"
    role-name="学工处 / 学院 / 心理老师（聚合）"
    data-scope-name="按角色聚合（心理明细不外泄）"
    watermark-purpose="心理统计查看"
  >
    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载心理统计..."
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <section class="sa-summary-strip mental-stats-summary" :class="{ 'has-crisis': stats && stats.openCrisis }">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">聚合管理结论</span>
          <h2 class="sa-summary-strip__title">
            当前关注在册 {{ (stats && stats.total) || 0 }} 条，在办危机 {{ (stats && stats.openCrisis) || 0 }} 条，回访中 {{ (stats && stats.byStatus && stats.byStatus.FOLLOWING) || 0 }} 条
          </h2>
          <p class="sa-summary-strip__text">本页只展示数量分布，不提供姓名、学号、咨询记录、诊断或个体明细。发现危机数量异常时，应由具备专项权限的人员进入危机工作区处置。</p>
        </div>
      </section>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <div class="sa-grid sa-grid--two">
        <AppSectionCard title="按处置状态分布">
          <p class="mental-stats-hint">了解转介、回访、危机升级和关闭的数量结构，不支持点击查看个人。</p>
          <DataTable v-if="statusRows.length" :columns="statusColumns" :rows="statusRows" row-key="key">
            <template #cell-label="{ row }"><AppStatusTag :type="row.kind" :label="row.label" /></template>
            <template #cell-value="{ row }"><strong class="mental-stat-number">{{ row.value }}</strong></template>
          </DataTable>
          <p v-else class="sa-empty">当前数据范围内暂无状态分布数据。</p>
        </AppSectionCard>

        <AppSectionCard title="按关注等级分布">
          <p class="mental-stats-hint">用于识别一般关注、重点关注与危机记录的整体结构，不展示任何事由或明细。</p>
          <DataTable v-if="levelRows.length" :columns="levelColumns" :rows="levelRows" row-key="key">
            <template #cell-label="{ row }"><AppStatusTag :type="row.kind" :label="row.label" /></template>
            <template #cell-value="{ row }"><strong class="mental-stat-number">{{ row.value }}</strong></template>
          </DataTable>
          <p v-else class="sa-empty">当前数据范围内暂无关注等级分布。</p>
        </AppSectionCard>
      </div>
      <p class="sa-note">隐私边界：本页仅呈现聚合数量，不含任何学生姓名、咨询记录、诊断信息或可反推个体的明细。</p>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

const STATUS_COLUMNS = [{ key: 'label', title: '状态' }, { key: 'value', title: '数量' }]
const LEVEL_COLUMNS = [{ key: 'label', title: '等级' }, { key: 'value', title: '数量' }]
const STATUS = [
  { key: 'REFERRED', label: '已转介', kind: 'info' },
  { key: 'FOLLOWING', label: '回访中', kind: 'warning' },
  { key: 'ESCALATED', label: '已升级危机', kind: 'danger' },
  { key: 'CLOSED', label: '已关闭', kind: 'success' }
]
const LEVEL = [
  { key: 'CRISIS', label: '危机', kind: 'danger' },
  { key: 'FOCUS', label: '重点关注', kind: 'warning' },
  { key: 'GENERAL', label: '一般关注', kind: 'info' }
]

export default {
  name: 'MentalStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag, DataTable },
  data() {
    return { statusColumns: STATUS_COLUMNS, levelColumns: LEVEL_COLUMNS, loading: true, errorMessage: '', stats: null }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    metricCards() {
      const s = this.stats || {}
      const byStatus = s.byStatus || {}
      return [
        { key: 'total', label: '关注在册', value: s.total || 0, accent: 'primary' },
        { key: 'openCrisis', label: '在办危机', value: s.openCrisis || 0, accent: (s.openCrisis || 0) ? 'risk' : 'success' },
        { key: 'following', label: '回访中', value: byStatus.FOLLOWING || 0, accent: 'warning' },
        { key: 'closed', label: '已结案', value: byStatus.CLOSED || 0, accent: 'success' }
      ]
    },
    statusRows() {
      const by = (this.stats && this.stats.byStatus) || {}
      return STATUS.filter((s) => by[s.key] !== undefined).map((s) => ({ ...s, value: by[s.key] || 0 }))
    },
    levelRows() {
      const by = (this.stats && this.stats.byLevel) || {}
      return LEVEL.filter((s) => by[s.key] !== undefined).map((s) => ({ ...s, value: by[s.key] || 0 }))
    }
  },
  mounted() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getMentalStats()
        this.stats = res.data || {}
      } catch (e) {
        this.errorMessage = e.message || '心理统计加载失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.mental-stats-summary.has-crisis { border-color: var(--danger-200, #fecaca); background: var(--danger-50, #fef2f2); }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.sa-grid--two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); }
.mental-stats-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.mental-stat-number { color: var(--primary-700); font-size: var(--font-size-lg); font-variant-numeric: tabular-nums; }
.sa-note { margin: var(--space-4) 0 0; padding: 10px 12px; border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-md); background: var(--warning-50, #fffbeb); color: var(--text-secondary); font-size: var(--font-size-xs); line-height: 1.65; }
@media (max-width: 960px) { .sa-grid--metrics, .sa-grid--two { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .sa-grid--metrics, .sa-grid--two { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
