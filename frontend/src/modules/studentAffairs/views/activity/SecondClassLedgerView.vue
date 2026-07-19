<template>
  <AppPageShell
    title="第二课堂积分台账"
    subtitle="活动确认后生成的学时/德育积分/志愿时长流水，供综测·评优·推优入党只读引用（依据国标口径）。"
    role-name="团委 / 学工处"
    data-scope-name="按数据范围（辅导员限本班）"
    watermark-purpose="第二课堂积分台账"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载二课台账..." @retry="load"
                    @back="$router.push('/admin/student-affairs/activity')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>
      <AppSectionCard title="积分流水">
        <div class="cl-filters">
          <button v-for="f in typeFilters" :key="f.key" type="button" class="cl-chip"
                  :class="{ 'is-on': activeType === f.key }" @click="setType(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>学号</th><th>类型</th><th>数值</th><th>类目</th><th>来源</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="c in items" :key="c.creditId" class="cl-row" @click="openReport(c)">
              <td><strong>{{ c.realName || ('学生#' + c.studentId) }}</strong></td>
              <td>{{ c.studentNo || '—' }}</td>
              <td>{{ typeLabel(c.creditType) }}</td>
              <td>{{ c.creditValue }}</td>
              <td>{{ c.categoryCode || '—' }}</td>
              <td class="cl-remark">{{ c.remark || sourceLabel(c.source) }}</td>
              <td><AppDateDisplay :value="c.grantedAt" mode="date" empty-text="—" /></td>
            </tr>
            <tr v-if="!items.length"><td colspan="7" class="sa-empty">当前范围与筛选下暂无二课积分记录</td></tr>
          </tbody>
        </table>
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize" :total="pagination.total" @change="load" />
        <p class="cl-hint">点击任一行查看该生「加权成绩单」（按类目系数汇总）。</p>
      </AppSectionCard>

      <AppSectionCard v-if="report" :title="`个人成绩单（加权）· ${report.realName || ('学生#' + report.studentId)}`">
        <div class="cl-report-total">
          <span>原始合计 <b>{{ report.rawTotal }}</b></span>
          <span class="cl-weighted">加权合计 <b>{{ report.weightedTotal }}</b></span>
        </div>
        <table class="sa-table">
          <thead><tr><th>类目</th><th>原始合计</th><th>系数</th><th>加权后</th></tr></thead>
          <tbody>
            <tr v-for="row in (report.byCategoryWeighted || [])" :key="row.key">
              <td>{{ row.key }}</td>
              <td>{{ row.rawValue }}</td>
              <td>×{{ row.weight }}</td>
              <td><b>{{ row.value }}</b></td>
            </tr>
            <tr v-if="!(report.byCategoryWeighted || []).length"><td colspan="4" class="sa-empty">该生暂无类目积分</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppSectionCard } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TYPE = { SECOND_CLASS: '第二课堂学时', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }
const TYPE_FILTERS = [
  { key: '', label: '全部' }, { key: 'SECOND_CLASS', label: '第二课堂学时' },
  { key: 'MORAL', label: '德育积分' }, { key: 'VOLUNTEER_HOUR', label: '志愿时长' }
]

export default {
  name: 'SecondClassLedgerView',
  components: { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppSectionCard },
  data() {
    return {
      loading: true, errorMessage: '', all: [], items: [], activeType: '', typeFilters: TYPE_FILTERS, report: null,
      pagination: { page: 1, pageSize: 20, total: 0 }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      // 二课学时/志愿时长合计仍按改造前口径（all，pageSize 300 上限）汇总；
      // 流水条数改用服务端真实 total，比改造前的 items.length（受 300 上限）更准确。
      const sum = (t) => this.all.filter((x) => x.creditType === t).reduce((s, x) => s + (Number(x.creditValue) || 0), 0)
      return [
        { key: 'n', label: '流水条数', value: this.pagination.total, accent: 'primary' },
        { key: 'sc', label: '二课学时合计', value: Math.round(sum('SECOND_CLASS') * 10) / 10, accent: 'success' },
        { key: 'vh', label: '志愿时长合计', value: Math.round(sum('VOLUNTEER_HOUR') * 10) / 10, accent: 'info' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      // items 走真分页（服务端按 creditType 过滤+切片）；all 单独按改造前口径（同过滤条件，pageSize 300 一次性拉取）
      // 仅供统计卡片的“合计”汇总使用，避免真分页把合计数字切小。
      const [res, allRes] = await Promise.all([
        studentAffairsApi.getSecondClassLedger({ creditType: this.activeType, page: this.pagination.page, pageSize: this.pagination.pageSize }),
        studentAffairsApi.getSecondClassLedger({ creditType: this.activeType, pageSize: 300 })
      ])
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        this.pagination.total = res.data.total || 0
      } else {
        this.errorMessage = res.message || '二课台账加载失败'
      }
      if (allRes.code === 0 && allRes.data) this.all = allRes.data.items || []
      this.loading = false
    },
    setType(k) { if (this.activeType === k) return; this.activeType = k; this.pagination.page = 1; this.load() },
    async openReport(c) {
      if (!c || !c.studentId) return
      const res = await studentAffairsApi.getSecondClassReport(c.studentId)
      if (res.code === 0 && res.data) this.report = res.data
      else this.errorMessage = res.message || '成绩单加载失败'
    },
    typeLabel(t) { return TYPE[t] || t },
    sourceLabel(s) { return ({ ACTIVITY: '活动确认', MANUAL_ADJUST: '手工调整', VOLUNTEER_RECORD: '志愿补录' })[s] || s || '—' }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.cl-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.cl-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.cl-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.cl-remark { color: var(--text-secondary); font-size: var(--font-size-sm); }
.cl-row { cursor: pointer; }
.cl-row:hover { background: var(--bg-hover, rgba(0,0,0,0.03)); }
.cl-hint { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-top: var(--space-2); }
.cl-report-total { display: flex; gap: var(--space-5); margin-bottom: var(--space-3); font-size: var(--font-size-md); }
.cl-report-total .cl-weighted b { color: var(--color-primary); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
