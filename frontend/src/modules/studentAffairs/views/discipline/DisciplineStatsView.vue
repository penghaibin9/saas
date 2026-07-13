<template>
  <AppPageShell
    title="违纪处分统计"
    subtitle="按处分类型与状态聚合，含投影一致性对账。数据范围与处分台账一致。"
    role-name="学工处 / 学院"
    data-scope-name="按数据范围聚合"
    watermark-purpose="违纪处分统计"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载处分统计..." @retry="load"
                    @back="$router.push('/admin/student-affairs/discipline')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="投影对账">
        <div class="ds-recon" :class="recon.consistent ? 'is-ok' : 'is-bad'">
          <div class="ds-recon__item"><span>EFFECTIVE 案件数</span><b>{{ recon.effectiveCases || 0 }}</b></div>
          <div class="ds-recon__sep">↔</div>
          <div class="ds-recon__item"><span>生效投影行数</span><b>{{ recon.activeProjections || 0 }}</b></div>
          <StatusTag :type="recon.consistent ? 'success' : 'danger'" :label="recon.consistent ? '一致' : '不一致（需核查）'" dot />
        </div>
      </AppSectionCard>

      <div class="ss-cols">
        <AppSectionCard title="按处分类型分布">
          <BreakdownTable :rows="stats.byType" :label-map="TYPE_LABELS" empty="暂无处分" />
        </AppSectionCard>
        <AppSectionCard title="按状态分布">
          <BreakdownTable :rows="stats.byStatus" :label-map="STATUS_LABELS" empty="暂无状态数据" />
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, AppStatusTag } from '@/components/common'
import BreakdownTable from '@/modules/studentAffairs/views/common/BreakdownTable.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TYPE_LABELS = { WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过', PROBATION: '留校察看', EXPEL: '开除' }
const STATUS_LABELS = { REGISTERED: '已登记', COLLEGE_REVIEW: '学院初审', STUDENT_AFFAIRS_REVIEW: '学工处复核', SCHOOL_REVIEW: '校级审批', EFFECTIVE: '已生效', REJECTED: '已驳回', RETURNED: '已退回', REMOVE_REVIEW: '解除审批', REMOVED: '已解除', ARCHIVED: '已归档' }

export default {
  name: 'DisciplineStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard, BreakdownTable, StatusTag: AppStatusTag },
  data() { return { loading: true, errorMessage: '', stats: { total: 0, byType: [], byStatus: [], reconcile: {} }, TYPE_LABELS, STATUS_LABELS } },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    recon() { return this.stats.reconcile || { effectiveCases: 0, activeProjections: 0, consistent: true } },
    metricCards() {
      const eff = (this.stats.byStatus || []).find((x) => x.key === 'EFFECTIVE')
      const removed = (this.stats.byStatus || []).find((x) => x.key === 'REMOVED')
      return [
        { key: 't', label: '处分记录数', value: this.stats.total || 0, accent: 'primary' },
        { key: 'e', label: '生效中', value: eff ? eff.count : 0, accent: 'risk' },
        { key: 'r', label: '已解除', value: removed ? removed.count : 0, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getDisciplineStats()
        this.stats = res.data || { total: 0, byType: [], byStatus: [], reconcile: {} }
      } catch (e) {
        this.errorMessage = e.message || '处分统计加载失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.ds-recon { display: flex; align-items: center; gap: var(--space-4); padding: var(--space-3) var(--space-4); border-radius: var(--radius-md); margin-bottom: var(--space-4); }
.ds-recon.is-ok { background: rgba(34,197,94,0.08); }
.ds-recon.is-bad { background: rgba(239,68,68,0.08); }
.ds-recon__item { display: flex; flex-direction: column; }
.ds-recon__item span { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ds-recon__item b { font-size: var(--font-size-lg); }
.ds-recon__sep { color: var(--text-tertiary); }
.ss-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } .ss-cols { grid-template-columns: 1fr; } }
</style>
