<template>
  <AppPageShell
    title="违纪处分台账"
    subtitle="全量处分记录只读台账 + 处分投影一致性对账（EFFECTIVE 案件数 ↔ t_cs_discipline 生效行数）。"
    role-name="学工处 / 学院"
    data-scope-name="学院本院 / 学工处全校"
    watermark-purpose="违纪处分台账查看"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载处分台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/discipline')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="处分投影对账">
        <div class="dl-recon" :class="recon.consistent ? 'is-ok' : 'is-bad'">
          <div class="dl-recon__item"><span>EFFECTIVE 案件数</span><b>{{ recon.effectiveCases }}</b></div>
          <div class="dl-recon__sep">↔</div>
          <div class="dl-recon__item"><span>生效投影行数</span><b>{{ recon.activeProjections }}</b></div>
          <StatusTag :type="recon.consistent ? 'success' : 'danger'"
                     :label="recon.consistent ? '一致' : '不一致（需核查）'" dot />
        </div>
      </AppSectionCard>

      <AppSectionCard title="处分记录">
        <div class="dl-filters">
          <button v-for="f in statusFilters" :key="f.key" type="button" class="dl-chip"
                  :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>学号</th><th>处分类型</th><th>文号</th><th>状态</th><th>生效</th><th>解除</th></tr></thead>
          <tbody>
            <tr v-for="c in items" :key="c.caseId || c.id">
              <td><strong>{{ c.realName || ('学生#' + c.studentId) }}</strong></td>
              <td>{{ c.studentNo || '—' }}</td>
              <td>{{ discTypeLabel(c.discType) }}</td>
              <td class="dl-doc">{{ c.docNo || '—' }}</td>
              <td><StatusTag :type="statusType(c.status)" :label="c.statusLabel || c.status" dot /></td>
              <td>{{ (c.effectiveAt || '').slice(0, 10) || '—' }}</td>
              <td>{{ (c.removedAt || '').slice(0, 10) || '—' }}</td>
            </tr>
            <tr v-if="!items.length"><td colspan="7" class="sa-empty">当前范围与筛选下暂无处分记录</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const DISC_TYPES = { WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过', PROBATION: '留校察看', EXPEL: '开除' }
const STATUS_FILTERS = [
  { key: '', label: '全部' },
  { key: 'REGISTERED', label: '已登记' },
  { key: 'EFFECTIVE', label: '生效中' },
  { key: 'REMOVED', label: '已解除' }
]

export default {
  name: 'DisciplineLedgerView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return { loading: true, errorMessage: '', all: [], items: [], recon: { effectiveCases: 0, activeProjections: 0, consistent: true }, activeStatus: '', statusFilters: STATUS_FILTERS }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const eff = this.all.filter((c) => c.status === 'EFFECTIVE').length
      const removed = this.all.filter((c) => c.status === 'REMOVED').length
      return [
        { key: 'all', label: '处分记录数', value: this.all.length, accent: 'primary' },
        { key: 'eff', label: '生效中', value: eff, accent: 'risk' },
        { key: 'rm', label: '已解除', value: removed, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const [cases, rec] = await Promise.all([
          studentAffairsApi.getDisciplineCases({ pageSize: 500 }),
          studentAffairsApi.reconcileDiscipline().catch(() => ({ data: null }))
        ])
        this.all = (cases.data && cases.data.items) || []
        this.applyFilter()
        if (rec && rec.data) this.recon = rec.data
      } catch (e) {
        this.errorMessage = e.message || '处分台账加载失败'
      } finally {
        this.loading = false
      }
    },
    applyFilter() {
      this.items = this.activeStatus ? this.all.filter((c) => c.status === this.activeStatus) : this.all
    },
    setStatus(k) { this.activeStatus = k; this.applyFilter() },
    discTypeLabel(t) { return DISC_TYPES[t] || t || '—' },
    statusType(s) {
      if (s === 'EFFECTIVE') return 'danger'
      if (s === 'REMOVED') return 'success'
      if (['REGISTERED', 'RETURNED'].includes(s)) return 'warning'
      return 'processing'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.dl-recon { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); }
.dl-recon.is-ok { background: rgba(34,197,94,0.08); }
.dl-recon.is-bad { background: rgba(239,68,68,0.08); }
.dl-recon__item { display: flex; flex-direction: column; }
.dl-recon__item span { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.dl-recon__item b { font-size: var(--font-size-lg); }
.dl-recon__sep { color: var(--text-tertiary); }
.dl-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.dl-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.dl-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.dl-doc { color: var(--text-secondary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
