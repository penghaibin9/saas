<template>
  <ModulePageShell title="实习统计" subtitle="过程与结果指标 · 学院/专业/班级下钻 · 阈值预警"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 报表</AppExportButton>
    </template>

    <div class="bar">
      <select v-model="dim.college" class="bar__sel" @change="onDimChange('college')">
        <option value="">全部学院</option>
        <option v-for="c in dims.colleges" :key="c" :value="c">{{ c }}</option>
      </select>
      <select v-model="dim.major" class="bar__sel" @change="load">
        <option value="">全部专业</option>
        <option v-for="m in dims.majors" :key="m" :value="m">{{ m }}</option>
      </select>
      <select v-model="dim.className" class="bar__sel" @change="load">
        <option value="">全部班级</option>
        <option v-for="c in dims.classes" :key="c" :value="c">{{ c }}</option>
      </select>
      <button class="bar__go" @click="load">查询</button>
      <button v-if="dim.college || dim.major || dim.className" class="bar__clr" @click="clearDim">清除筛选</button>
      <span class="bar__hint">数据范围内可见 · 生成于 {{ generatedAt || '—' }}</span>
    </div>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />

    <template v-else>
      <!-- 计数概览 -->
      <div class="grid">
        <AppMetricCard v-for="c in counters" :key="c.key" :title="c.label" :value="c.value"
          :accent="c.warn ? 'warning' : 'primary'" :trend-quality="c.warn ? 'bad' : 'neutral'"
          :trend-label="c.warn ? '需关注' : ''" />
      </div>

      <!-- 指标卡（比率 + 阈值预警） -->
      <div class="sec-t">过程与结果指标（低于阈值标记预警）</div>
      <div class="grid">
        <AppMetricCard v-for="m in metrics" :key="m.key" :title="m.label"
          :value="m.rate === null ? '暂无数据' : (m.rate + '%')"
          :accent="m.warn ? 'warning' : 'success'"
          :trend-quality="m.rate === null ? 'neutral' : (m.warn ? 'bad' : 'good')"
          :trend-label="metricTrend(m)" />
      </div>

      <AppChartCard
        title="实习过程趋势"
        subtitle="最近 6 个月建档、报告提交、指导与巡访的真实业务发生量"
        :empty="!trendRows.length"
        empty-text="当前筛选范围暂无过程数据"
        :min-height="280"
      >
        <AppG2Chart :spec="trendChartSpec" :height="250" />
        <template #footer><span class="chart-note">统计口径：按建档创建时间、报告提交时间、指导/巡访记录创建时间汇总。</span></template>
      </AppChartCard>

      <AppChartCard
        title="成绩分布（已发布）"
        subtitle="按优 / 良 / 中 / 及格 / 不及格统计已发布综合成绩"
        :empty="!scoreTotal"
        empty-text="暂无已发布成绩"
        :min-height="260"
      >
        <AppG2Chart :spec="scoreChartSpec" :height="240" />
        <template #footer>
          <span class="chart-note">统计口径：仅统计已发布成绩；未发布成绩不进入分布。</span>
        </template>
      </AppChartCard>

      <!-- 就业/归档指标已接入真实台账；无数据时分母为 0 时显示「暂无数据」 -->
      <div v-if="partial.length" class="partial">
        <span v-for="p in partial" :key="p.key" class="partial__i">{{ p.label }}（{{ p.reason }}）</span>
      </div>
    </template>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppChartCard, AppG2Chart, AppMetricCard, AppExportButton, buildBarChartSpec } from '@/components/common'
import { statsApi } from '@/modules/internship/api/stats.api'
import { toast } from '@/utils/toast'

export default {
  name: 'StatsView',
  components: { ModulePageShell, LoadingState, ErrorState, AppExportButton, AppMetricCard, AppChartCard, AppG2Chart },
  data() {
    return {
      loading: false, error: '',
      dim: { college: '', major: '', className: '' },
      dims: { colleges: [], majors: [], classes: [] },
      counters: [], metrics: [], scoreDistribution: [], trendSeries: [], partial: [], generatedAt: '',
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    scoreTotal() { return this.scoreDistribution.reduce((a, d) => a + d.count, 0) },
    scoreChartSpec() {
      return buildBarChartSpec({
        data: this.scoreDistribution.map((d) => ({ label: d.bucket, value: d.count })),
        horizontal: true,
        valueLabel: '学生数',
        unit: '人',
        color: '#2563eb',
        maxLabelLength: 14
      })
    },
    trendRows() {
      return this.trendSeries.flatMap((series) => (series.points || []).map((point) => ({
        month: point.month, series: series.label, value: point.value
      })))
    },
    trendChartSpec() {
      return {
        type: 'line',
        data: this.trendRows,
        encode: { x: 'month', y: 'value', color: 'series' },
        shape: 'smooth',
        style: { lineWidth: 2.5, point: true },
        legend: { color: { position: 'bottom' } }
      }
    }
  },
  created() { this.loadDims(); this.load() },
  methods: {
    metricTrend(m) {
      const base = `${m.numerator}/${m.denominator} · 阈值${m.threshold}%`
      return m.warn ? `预警 · ${base}` : base
    },
    async loadDims() {
      const res = await statsApi.getDimensions()
      if (res.code === 0) this.dims = res.data
    },
    onDimChange() { this.load() },
    clearDim() { this.dim = { college: '', major: '', className: '' }; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = {}
      if (this.dim.college) params.college = this.dim.college
      if (this.dim.major) params.major = this.dim.major
      if (this.dim.className) params.className = this.dim.className
      const [res, trendRes] = await Promise.all([statsApi.getOverview(params), statsApi.getTrends(params)])
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; return }
      this.counters = res.data.counters || []
      this.metrics = res.data.metrics || []
      this.scoreDistribution = res.data.scoreDistribution || []
      this.partial = res.data.partial || []
      this.generatedAt = res.data.generatedAt || ''
      this.trendSeries = trendRes.code === 0 ? (trendRes.data.series || []) : []
    },
    exportFn() {
      const params = {}
      if (this.dim.college) params.college = this.dim.college
      if (this.dim.major) params.major = this.dim.major
      if (this.dim.className) params.className = this.dim.className
      return statsApi.exportStats(params)
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 行（水印 + 导出留痕）`) }
  }
}
</script>

<style scoped>
.bar { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.bar__sel { height: 32px; border: 1px solid var(--border-base); border-radius: var(--radius-base); padding: 0 var(--space-2); font-size: var(--font-size-sm); }
.bar__go { height: 32px; padding: 0 var(--space-3); border: 1px solid var(--primary-600); background: var(--primary-600); color: #fff; border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.bar__clr { height: 32px; padding: 0 var(--space-2); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); border-radius: var(--radius-base); cursor: pointer; font-size: var(--font-size-sm); }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-4); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin-bottom: var(--space-2); }
.chart-note { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.partial { padding: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-base); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.partial__t { font-weight: var(--font-weight-medium); margin-right: var(--space-2); }
.partial__i { margin-right: var(--space-3); }
</style>
