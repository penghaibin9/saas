<template>
  <AppPageShell
    title="宿舍统计"
    subtitle="入住率与床位分布聚合；宿管统计限本人负责楼栋。"
    role-name="学工处 / 宿管"
    data-scope-name="宿管限负责楼栋"
    watermark-purpose="宿舍统计查看"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载宿舍统计..." @retry="load"
                    @back="$router.push('/admin/student-affairs/dashboard')">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前床位结论</span>
          <h2 class="sa-summary-strip__title">总床位 {{ occ.totalBeds || 0 }} 张，已入住 {{ occ.occupiedBeds || 0 }} 张，空床 {{ occ.vacantBeds || 0 }} 张</h2>
          <p class="sa-summary-strip__text">当前范围入住率 {{ occ.occupancyRate != null ? Math.round(occ.occupancyRate * 100) + '%' : '—' }}。优先核查入住率异常偏高、无空床或空床长期较多的楼栋。</p>
        </div>
      </section>

      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="楼栋入住与空床对比">
        <p class="dorm-stats-hint">按楼栋对比性别限制、空床、总床和入住率。入住率达到100%时应关注新生安排与调宿空间。</p>
        <DataTable v-if="buildings.length" :columns="buildingColumns" :rows="buildings" row-key="buildingId">
          <template #cell-name="{ row }"><span class="mp-cell-main">{{ row.buildingName }}</span></template>
          <template #cell-gender="{ row }"><span class="dorm-stats-gender">{{ genderLabel(row.genderLimit) }}</span></template>
          <template #cell-vacant="{ row }"><strong :class="row.vacantBeds ? 'dorm-stats-vacant' : 'dorm-stats-full'">{{ row.vacantBeds }}</strong></template>
          <template #cell-total="{ row }">{{ row.totalBeds }}</template>
          <template #cell-rate="{ row }"><span class="dorm-stats-rate" :class="{ 'is-full': row.totalBeds && !row.vacantBeds }">{{ rate(row) }}</span></template>
        </DataTable>
        <p v-else class="sa-empty">当前数据范围内暂无楼栋统计。请先维护宿舍房源，或检查宿管楼栋数据范围。</p>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

const BUILDING_COLUMNS = [
  { key: 'name', title: '楼栋' },
  { key: 'gender', title: '性别' },
  { key: 'vacant', title: '空床' },
  { key: 'total', title: '总床' },
  { key: 'rate', title: '入住率' }
]

export default {
  name: 'DormStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, DataTable },
  data() { return { buildingColumns: BUILDING_COLUMNS, loading: true, errorMessage: '', occ: {}, buildings: [] } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const rate = this.occ.occupancyRate != null ? Math.round(this.occ.occupancyRate * 100) : 0
      return [
        { key: 't', label: '总床位', value: this.occ.totalBeds || 0, accent: 'primary' },
        { key: 'o', label: '已住', value: this.occ.occupiedBeds || 0, accent: 'info' },
        { key: 'v', label: '空床', value: this.occ.vacantBeds || 0, accent: (this.occ.vacantBeds || 0) ? 'success' : 'warning' },
        { key: 'r', label: '入住率', value: rate + '%', accent: 'primary' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const [oc, bs] = await Promise.all([studentAffairsApi.getDormOccupancy(), studentAffairsApi.listDormBuildings()])
        this.occ = oc.data || {}; this.buildings = bs.data.items || []
      } catch (e) { this.errorMessage = e.message || '宿舍统计加载失败' } finally { this.loading = false }
    },
    rate(b) { return b.totalBeds ? Math.round((b.totalBeds - b.vacantBeds) / b.totalBeds * 100) + '%' : '—' },
    genderLabel(g) { return ({ MALE: '男寝', FEMALE: '女寝', MIXED: '混合' })[g] || g }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.dorm-stats-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.dorm-stats-gender { padding: 2px 7px; border-radius: var(--radius-full); background: var(--bg-section); color: var(--text-secondary); font-size: var(--font-size-xs); }
.dorm-stats-vacant { color: var(--success-700, #15803d); font-variant-numeric: tabular-nums; }
.dorm-stats-full { color: var(--danger-700, #b91c1c); font-variant-numeric: tabular-nums; }
.dorm-stats-rate { display: inline-block; min-width: 54px; padding: 3px 8px; border-radius: var(--radius-full); background: var(--primary-50); color: var(--primary-700); text-align: center; font-weight: 600; font-variant-numeric: tabular-nums; }
.dorm-stats-rate.is-full { background: var(--warning-50); color: var(--warning-800, #92400e); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
