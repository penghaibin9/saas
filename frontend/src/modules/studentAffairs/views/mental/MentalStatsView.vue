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
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="card in metricCards" :key="card.key" :title="card.label" :value="card.value" :accent="card.accent" />
      </div>

      <div class="sa-grid sa-grid--two">
        <AppSectionCard title="按状态分布">
          <DataTable v-if="statusRows.length" :columns="statusColumns" :rows="statusRows" row-key="key">
            <template #cell-label="{ row }"><AppStatusTag :type="row.kind" :label="row.label" /></template>
            <template #cell-value="{ row }">{{ row.value }}</template>
          </DataTable>
          <p v-else class="sa-empty">暂无数据</p>
        </AppSectionCard>

        <AppSectionCard title="按关注等级分布">
          <DataTable v-if="levelRows.length" :columns="levelColumns" :rows="levelRows" row-key="key">
            <template #cell-label="{ row }"><AppStatusTag :type="row.kind" :label="row.label" /></template>
            <template #cell-value="{ row }">{{ row.value }}</template>
          </DataTable>
          <p v-else class="sa-empty">暂无数据</p>
        </AppSectionCard>
      </div>
      <p class="sa-note">本页仅呈现聚合数量，不含任何学生姓名、咨询记录或诊断信息。</p>
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
.sa-grid--metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.sa-grid--two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-4);
}
.sa-note {
  color: var(--text-tertiary);
  margin-top: var(--space-4);
}
.sa-empty {
  color: var(--text-tertiary);
  padding: var(--space-4);
  text-align: center;
}
@media (max-width: 960px) {
  .sa-grid--metrics,
  .sa-grid--two {
    grid-template-columns: 1fr;
  }
}
@import '@/styles/module-page.css';
</style>
