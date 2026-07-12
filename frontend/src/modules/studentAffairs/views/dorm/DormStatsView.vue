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
        <table class="sa-table">
          <thead><tr><th>楼栋</th><th>性别</th><th>空床</th><th>总床</th><th>入住率</th></tr></thead>
          <tbody>
            <tr v-for="b in buildings" :key="b.buildingId">
              <td><strong>{{ b.buildingName }}</strong></td>
              <td>{{ genderLabel(b.genderLimit) }}</td>
              <td>{{ b.vacantBeds }}</td>
              <td>{{ b.totalBeds }}</td>
              <td>{{ rate(b) }}</td>
            </tr>
            <tr v-if="!buildings.length"><td colspan="5" class="sa-empty">暂无楼栋数据</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairsB.api'

export default {
  name: 'DormStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard },
  data() { return { loading: true, errorMessage: '', occ: {}, buildings: [] } },
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
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
