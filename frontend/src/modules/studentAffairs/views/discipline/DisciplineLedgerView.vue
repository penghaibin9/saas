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
        <DataTable v-if="items.length" :columns="caseColumns" :rows="items" row-key="rowKey">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span></template>
          <template #cell-studentNo="{ row }">{{ row.studentNo || '—' }}</template>
          <template #cell-discType="{ row }">{{ discTypeLabel(row.discType) }}</template>
          <template #cell-docNo="{ row }"><span class="dl-doc">{{ row.docNo || '—' }}</span></template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-effectiveAt="{ row }"><AppDateDisplay :value="row.effectiveAt" mode="date" empty-text="—" /></template>
          <template #cell-removedAt="{ row }"><AppDateDisplay :value="row.removedAt" mode="date" empty-text="—" /></template>
        </DataTable>
        <p v-else class="sa-empty">当前范围与筛选下暂无处分记录</p>
        <AppPagination v-if="items.length" v-model:page="paging.page" v-model:pageSize="paging.pageSize"
                       :total="paging.total" @change="loadPage" />
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const DISC_TYPES = { WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过', PROBATION: '留校察看', EXPEL: '开除' }
const STATUS_FILTERS = [
  { key: '', label: '全部' },
  { key: 'REGISTERED', label: '已登记' },
  { key: 'EFFECTIVE', label: '生效中' },
  { key: 'REMOVED', label: '已解除' }
]
const CASE_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'studentNo', title: '学号' },
  { key: 'discType', title: '处分类型' },
  { key: 'docNo', title: '文号' },
  { key: 'status', title: '状态' },
  { key: 'effectiveAt', title: '生效' },
  { key: 'removedAt', title: '解除' }
]

export default {
  name: 'DisciplineLedgerView',
  components: { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  data() {
    return {
      caseColumns: CASE_COLUMNS,
      loading: true, errorMessage: '', items: [],
      // 三项全局统计只取后端 total（pageSize=1 的轻量请求），与「处分记录」表的真实分页互相独立，
      // 避免表格翻页时头部统计卡跟着变化。
      metrics: { all: 0, eff: 0, removed: 0 },
      recon: { effectiveCases: 0, activeProjections: 0, consistent: true },
      activeStatus: '', statusFilters: STATUS_FILTERS,
      paging: { page: 1, pageSize: 20, total: 0 }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'all', label: '处分记录数', value: this.metrics.all, accent: 'primary' },
        { key: 'eff', label: '生效中', value: this.metrics.eff, accent: 'risk' },
        { key: 'rm', label: '已解除', value: this.metrics.removed, accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [allRes, effRes, rmRes, rec] = await Promise.all([
        studentAffairsApi.getDisciplineCases({ pageSize: 1 }),
        studentAffairsApi.getDisciplineCases({ status: 'EFFECTIVE', pageSize: 1 }),
        studentAffairsApi.getDisciplineCases({ status: 'REMOVED', pageSize: 1 }),
        studentAffairsApi.reconcileDiscipline()
      ])
      if (allRes.code === 0 && allRes.data) {
        this.metrics = {
          all: allRes.data.total || 0,
          eff: (effRes.code === 0 && effRes.data && effRes.data.total) || 0,
          removed: (rmRes.code === 0 && rmRes.data && rmRes.data.total) || 0
        }
        if (rec.code === 0 && rec.data) this.recon = rec.data
        await this.loadPage()
      } else {
        this.errorMessage = allRes.message || '处分台账加载失败'
      }
      this.loading = false
    },
    async loadPage() {
      const res = await studentAffairsApi.getDisciplineCases({
        status: this.activeStatus, page: this.paging.page, pageSize: this.paging.pageSize
      })
      if (res.code === 0 && res.data) {
        // rowKey：DataTable 需要具体字段名，caseId 缺失时回退 id（兼容历史数据）
        this.items = (res.data.items || []).map((c) => ({ ...c, rowKey: c.caseId || c.id }))
        this.paging.total = res.data.total || 0
      } else {
        this.errorMessage = res.message || '处分记录加载失败'
      }
    },
    setStatus(k) {
      if (this.activeStatus === k) return
      this.activeStatus = k
      this.paging.page = 1
      this.loadPage()
    },
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
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.dl-doc { color: var(--text-secondary); font-size: var(--font-size-sm); }
:deep(.dt) + .app-pagination { margin-top: var(--space-3); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
