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
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="按楼栋入住">
        <DataTable v-if="buildings.length" :columns="buildingColumns" :rows="buildings" row-key="buildingId">
          <template #cell-name="{ row }"><span class="mp-cell-main">{{ row.buildingName }}</span></template>
          <template #cell-gender="{ row }">{{ genderLabel(row.genderLimit) }}</template>
          <template #cell-vacant="{ row }">{{ row.vacantBeds }}</template>
          <template #cell-total="{ row }">{{ row.totalBeds }}</template>
          <template #cell-rate="{ row }">{{ rate(row) }}</template>
        </DataTable>
        <p v-else class="sa-empty">暂无楼栋数据</p>
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
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
@import '@/styles/module-page.css';
</style>
