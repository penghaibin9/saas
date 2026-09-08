<template>
  <ModulePageShell title="实习统计" subtitle="查看落实、过程与结果指标，定位需要跟进的环节。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton v-if="selectedKey" variant="ghost" @click="closeMetric">返回统计总览</AppButton>
      <AppExportButton :export-fn="exportFn" :has-permission="canBtn('internship.stats.export')">导出当前范围报表</AppExportButton>
    </template>

    <div class="stats-stack">
      <form class="filters" aria-label="统计范围" @submit.prevent="applyFilters">
        <label v-for="field in dimensionFields" :key="field.key" class="filter-field" :for="`stats-${field.key}`">
          <span>{{ field.label }}</span>
          <select :id="`stats-${field.key}`" v-model="dim[field.key]" :disabled="dimsLoading || !!dimsError" @change="applyFilters">
            <option value="">全部{{ field.label }}</option>
            <option v-if="dim[field.key] && !dims[field.options].includes(dim[field.key])" :value="dim[field.key]">{{ dim[field.key] }}</option>
            <option v-for="value in dims[field.options]" :key="value" :value="value">{{ value }}</option>
          </select>
        </label>
        <AppButton variant="ghost" :disabled="loading" @click="load">刷新数据</AppButton>
        <AppButton v-if="hasFilters" variant="ghost" @click="clearDim">清除筛选</AppButton>
      </form>
      <div v-if="dimsError" class="notice is-error" role="alert">
        <span>筛选选项加载失败：{{ dimsError }}</span><AppButton variant="ghost" size="sm" @click="loadDims">重试选项</AppButton>
      </div>

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <template v-else-if="loaded">
        <div class="snapshot-line"><span>{{ filterLabel }}</span><span>更新于 {{ displayTime(generatedAt) }}</span></div>

        <section v-if="selectedKey" class="metric-detail" aria-labelledby="metric-detail-title">
          <template v-if="selectedMetric">
            <header class="section-head">
              <div><span class="eyebrow">指标口径</span><h2 id="metric-detail-title" tabindex="-1">{{ selectedMetric.label }}</h2></div>
              <AppStatusTag :type="metricType(selectedMetric)">{{ metricStatus(selectedMetric) }}</AppStatusTag>
            </header>
            <div class="metric-result">
              <strong>{{ metricValue(selectedMetric) }}</strong>
              <span>参考阈值 {{ selectedMetric.threshold ?? '—' }}%</span>
            </div>
            <div class="metric-basis">
              <div><span>{{ selectedMetric.definition?.numeratorLabel || '分子' }}</span><strong>{{ selectedMetric.numerator ?? '—' }}</strong></div>
              <div><span>{{ selectedMetric.definition?.denominatorLabel || '分母' }}</span><strong>{{ selectedMetric.denominator ?? '—' }}</strong></div>
            </div>
            <div class="definition">
              <h3>如何计算</h3><p>{{ selectedMetric.note || selectedMetric.definition?.note || '当前接口未提供进一步的口径说明。' }}</p>
              <p>比率 = 分子 ÷ 分母 × 100%；无统计对象时不计算比率。</p>
              <p v-if="selectedMetric.anomaly" class="warning-text">分子大于分母，当前口径存在异常，请核对统计来源。</p>
              <p v-else-if="selectedMetric.rate == null">当前范围暂无可计算的数据，不计为达标或未达标。</p>
              <p v-else-if="selectedMetric.warn" class="warning-text">当前值低于参考阈值，可据此安排跟进。阈值不代表审批结论。</p>
            </div>
            <AppButton variant="secondary" @click="closeMetric">返回原筛选结果</AppButton>
          </template>
          <div v-else class="state" role="alert">当前统计结果中没有该指标。<AppButton variant="ghost" @click="closeMetric">返回统计总览</AppButton></div>
        </section>

        <template v-else>
          <dl class="counter-strip" aria-label="学生概况">
            <div v-for="item in counters" :key="item.key" :class="{ 'has-warning': item.warn }">
              <dt>{{ item.label }}</dt><dd>{{ item.value }}<small v-if="item.warn">需关注</small></dd>
            </div>
          </dl>
          <section class="indicator-panel" aria-labelledby="indicator-title">
            <header class="section-head">
              <div><h2 id="indicator-title" tabindex="-1">过程与结果指标</h2><p>{{ attentionCount }} 项需关注 · 无统计对象的指标不作达标判断</p></div>
              <label class="attention-toggle"><input v-model="onlyAttention" type="checkbox" @change="setAttention" />仅看需关注</label>
            </header>
            <DataTable v-if="visibleMetrics.length" :columns="metricColumns" :rows="visibleMetrics" row-key="key" row-clickable @row-click="openMetric">
              <template #cell-label="{ row }"><strong class="metric-name">{{ row.label }}</strong></template>
              <template #cell-rate="{ row }"><div class="rate-cell"><strong>{{ metricValue(row) }}</strong><span v-if="metricStatus(row) !== metricValue(row)" :class="{ 'warning-text': row.warn || row.anomaly }">{{ metricStatus(row) }}</span></div></template>
              <template #cell-basis="{ row }"><span class="basis-count">{{ row.numerator ?? '—' }} / {{ row.denominator ?? '—' }}</span></template>
              <template #cell-threshold="{ row }">{{ row.threshold ?? '—' }}%</template>
              <template #cell-actions="{ row }"><AppButton variant="ghost" size="sm" :aria-label="`查看${row.label}口径`" @click="openMetric(row)">查看口径</AppButton></template>
            </DataTable>
            <div v-else class="state">{{ onlyAttention ? '当前范围没有需关注指标' : '当前范围暂无统计指标' }}</div>
          </section>

          <div class="chart-grid">
            <AppChartCard title="实习过程趋势" subtitle="最近 6 个月的业务发生量" :min-height="280">
              <div v-if="trendError" class="state is-error" role="alert">{{ trendError }}<AppButton variant="ghost" size="sm" @click="load">重新加载</AppButton></div>
              <template v-else-if="trendRows.length">
                <AppG2Chart :spec="trendChartSpec" :height="250" />
                <details class="chart-values"><summary>查看趋势数据</summary><div class="table-scroll"><table><caption>每月业务发生量</caption><thead><tr><th>月份</th><th>业务</th><th>数量</th></tr></thead><tbody><tr v-for="(row, index) in trendRows" :key="index"><td>{{ row.month }}</td><td>{{ row.series }}</td><td>{{ row.value }}</td></tr></tbody></table></div></details>
              </template>
              <div v-else class="state">当前范围暂无过程数据</div>
              <template #footer><span class="chart-note">按建档、报告提交及指导巡访记录的发生时间汇总。</span></template>
            </AppChartCard>
            <AppChartCard title="成绩分布" subtitle="已发布综合成绩" :empty="!scoreTotal" empty-text="当前范围暂无已发布成绩" :min-height="280">
              <AppG2Chart :spec="scoreChartSpec" :height="250" />
              <details class="chart-values"><summary>查看分布数据</summary><dl class="score-values"><div v-for="item in scoreDistribution" :key="item.bucket"><dt>{{ item.bucket }}</dt><dd>{{ item.count }} 人</dd></div></dl></details>
              <template #footer><span class="chart-note">已发布 {{ scoreTotal }} 人；未发布成绩不计入分布。</span></template>
            </AppChartCard>
          </div>
          <div v-if="partial.length" class="notice" role="status"><span v-for="item in partial" :key="item.key">{{ item.label }}：{{ item.reason }}</span></div>
        </template>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, DataTable } from '@/components/business'
import { AppChartCard, AppG2Chart, AppExportButton, AppStatusTag, buildBarChartSpec } from '@/components/common'
import { AppButton } from '@/components/ui'
import { statsApi } from '@/modules/internship/api/stats.api'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const emptyDimensions = () => ({ colleges: [], majors: [], classes: [] })
const emptyFilters = () => ({ college: '', major: '', className: '' })
const queryText = value => typeof value === 'string' ? value : ''

export default {
  name: 'StatsView',
  components: { ModulePageShell, LoadingState, ErrorState, DataTable, AppExportButton, AppChartCard, AppG2Chart, AppStatusTag, AppButton },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: false, loaded: false, error: '', trendError: '', dimsError: '', dimsLoading: false,
      requestSeq: 0, dimsSeq: 0, contextEpoch: 0, requestKey: '', onlyAttention: false,
      dim: emptyFilters(), dims: emptyDimensions(),
      dimensionFields: [{ key: 'college', label: '学院', options: 'colleges' }, { key: 'major', label: '专业', options: 'majors' }, { key: 'className', label: '班级', options: 'classes' }],
      metricColumns: [{ key: 'label', title: '指标', width: '190px' }, { key: 'rate', title: '当前值', width: '130px' }, { key: 'basis', title: '分子 / 分母', width: '125px' }, { key: 'threshold', title: '参考阈值', width: '100px' }, { key: 'actions', title: '操作', width: '100px' }],
      counters: [], metrics: [], scoreDistribution: [], trendSeries: [], partial: [], generatedAt: '',
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    selectedKey() { return queryText(this.$route.query.metric) },
    selectedMetric() { return this.metrics.find(item => item.key === this.selectedKey) },
    hasFilters() { return Object.values(this.dim).some(Boolean) },
    filterLabel() { return Object.values(this.dim).filter(Boolean).join(' / ') || '当前批次 · 全部可见范围' },
    attentionCount() { return this.metrics.filter(item => item.warn || item.anomaly).length },
    visibleMetrics() { return this.onlyAttention ? this.metrics.filter(item => item.warn || item.anomaly) : this.metrics },
    contextKey() { return JSON.stringify([this.contextEpoch, String(this.batchStore.selectedBatchId || ''), this.dim]) },
    scoreTotal() { return this.scoreDistribution.reduce((sum, item) => sum + item.count, 0) },
    scoreChartSpec() {
      return buildBarChartSpec({ data: this.scoreDistribution.map(item => ({ label: item.bucket, value: item.count })), horizontal: true, valueLabel: '学生数', unit: '人', color: '#2563eb', maxLabelLength: 14 })
    },
    trendRows() { return this.trendSeries.flatMap(series => (series.points || []).map(point => ({ month: point.month, series: series.label, value: point.value }))) },
    trendChartSpec() { return { type: 'line', data: this.trendRows, encode: { x: 'month', y: 'value', color: 'series' }, shape: 'smooth', style: { lineWidth: 2.5, point: true }, legend: { color: { position: 'bottom' } } } }
  },
  watch: {
    selectedKey() { this.focusSection() },
    '$route.query'() { this.restoreQuery(); if (this.requestKey !== this.contextKey) this.load() },
    'batchStore.selectedBatchId'(value, previous) {
      if (previous && String(value) !== String(previous)) {
        this.dim = emptyFilters(); this.onlyAttention = false
        this.navigate({ college: undefined, major: undefined, className: undefined, metric: undefined, attention: undefined }, true)
      } else this.restoreQuery()
      this.loadDims(); this.load()
    },
    ctx: { deep: true, handler() { this.contextEpoch++; this.loadDims(); this.load() } }
  },
  created() { this.restoreQuery(); this.loadDims(); this.load() },
  beforeUnmount() { this.contextEpoch++; this.requestSeq++; this.dimsSeq++; this.clearData(); this.dims = emptyDimensions() },
  methods: {
    focusSection() {
      this.$nextTick?.(() => {
        const heading = this.$el?.querySelector(this.selectedKey ? '#metric-detail-title' : '#indicator-title')
        heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: 'start', behavior: 'auto' })
      })
    },
    canBtn(code) { return canCode(this.ctx, code) },
    displayTime(value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '—' },
    metricValue(item) { return item.anomaly ? '—' : item.rate == null ? '暂无数据' : `${item.rate}%` },
    metricStatus(item) { return item.anomaly ? '口径异常' : item.rate == null ? '暂无数据' : item.warn ? '低于阈值' : '达到阈值' },
    metricType(item) { return item.anomaly || item.warn ? 'warning' : item.rate == null ? 'default' : 'success' },
    restoreQuery() { this.dim = Object.fromEntries(Object.keys(emptyFilters()).map(key => [key, queryText(this.$route.query[key])])); this.onlyAttention = this.$route.query.attention === '1' },
    navigate(extra, replace = false) { const query = this.batchStore.withBatchQuery({ ...this.$route.query, ...extra }); return this.$router[replace ? 'replace' : 'push']({ path: '/admin/internship/stats', query }) },
    applyFilters() { return this.navigate({ ...this.dim, metric: undefined }) },
    clearDim() { this.dim = emptyFilters(); return this.applyFilters() },
    setAttention() { return this.navigate({ attention: this.onlyAttention ? '1' : undefined }) },
    openMetric(item) { return this.navigate({ metric: item.key }) },
    closeMetric() { return this.navigate({ metric: undefined }) },
    batchParams(extra = {}) { return { ...extra, batchId: this.batchStore.selectedBatchId || undefined } },
    clearData() { this.counters = []; this.metrics = []; this.scoreDistribution = []; this.trendSeries = []; this.partial = []; this.generatedAt = ''; this.loaded = false; this.trendError = '' },
    async loadDims() {
      const seq = ++this.dimsSeq, batchId = this.batchStore.selectedBatchId, epoch = this.contextEpoch
      this.dims = emptyDimensions(); this.dimsError = ''; this.dimsLoading = false
      if (!batchId || !this.canBtn('internship.stats.view')) return
      this.dimsLoading = true
      let res
      try { res = await statsApi.getDimensions({ batchId }) } catch (e) { res = { code: 1, message: e?.message } }
      if (seq !== this.dimsSeq || batchId !== this.batchStore.selectedBatchId || epoch !== this.contextEpoch) return
      this.dimsLoading = false
      if (res?.code !== 0) { this.dimsError = res?.message || '暂时无法读取筛选选项'; return }
      this.dims = { ...emptyDimensions(), ...res.data }
    },
    async exportFn() {
      if (!this.batchStore.selectedBatchId) return { code: 1, message: '请先选择批次' }
      if (!this.canBtn('internship.stats.export')) return { code: 1, message: '无统计导出权限' }
      const key = this.contextKey
      const res = await statsApi.exportStats(this.batchParams({ ...this.dim }))
      if (key !== this.contextKey) return { code: 1, message: '统计范围已切换，请在当前范围重新导出' }
      return res
    },
    async load() {
      const seq = ++this.requestSeq, key = this.contextKey
      this.requestKey = key; this.clearData(); this.loading = false; this.error = ''
      if (!this.batchStore.selectedBatchId) { this.error = '请先选择实习批次'; return }
      if (!this.canBtn('internship.stats.view')) { this.error = '无实习统计查看权限'; return }
      this.loading = true
      const params = this.batchParams(Object.fromEntries(Object.entries(this.dim).map(([name, value]) => [name, value || undefined])))
      const results = await Promise.allSettled([statsApi.getOverview(params), statsApi.getTrends({ ...params, months: 6 })])
      if (seq !== this.requestSeq || key !== this.contextKey) return
      this.loading = false
      const [ov, tr] = results.map(result => result.status === 'fulfilled' ? result.value : { code: 1, message: result.reason?.message })
      if (ov?.code !== 0) { this.error = ov?.message || '统计数据加载失败'; return }
      this.counters = ov.data.counters || []; this.metrics = ov.data.metrics || []
      this.scoreDistribution = ov.data.scoreDistribution || []; this.partial = ov.data.partial || []
      this.generatedAt = ov.data.generatedAt || ''; this.loaded = true
      if (tr?.code === 0) this.trendSeries = tr.data.series || []
      else this.trendError = tr?.message || '趋势数据加载失败'
      if (this.selectedKey) this.focusSection()
    }
  }
}
</script>

<style scoped>
.stats-stack { display: grid; gap: 18px; min-width: 0; }
.filters { display: flex; align-items: end; flex-wrap: wrap; gap: 12px; padding: 16px; border: 1px solid var(--border-base); border-radius: 12px; background: var(--bg-card); }
.filter-field { display: grid; gap: 6px; flex: 1 1 170px; min-width: 0; max-width: 260px; font-size: 12px; color: var(--text-secondary); }
.filter-field select { width: 100%; min-width: 0; height: 36px; padding: 0 10px; border: 1px solid var(--border-base); border-radius: 7px; background: var(--bg-card); color: var(--text-primary); font: inherit; font-size: 13px; }
.filter-field select:focus-visible, .attention-toggle input:focus-visible, summary:focus-visible { outline: 2px solid var(--primary-500); outline-offset: 3px; }
.snapshot-line { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 8px; color: var(--text-secondary); font-size: 12px; }
.counter-strip { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; padding: 18px 0; border: 1px solid var(--border-base); border-radius: 12px; background: var(--bg-card); }
.counter-strip > div { padding: 0 22px; border-right: 1px solid var(--border-base); }
.counter-strip > div:last-child { border: 0; }
.counter-strip dt { font-size: 13px; color: var(--text-secondary); }
.counter-strip dd { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px; margin: 8px 0 0; font-size: 28px; font-weight: 650; font-variant-numeric: tabular-nums; }
.counter-strip small { font-size: 12px; font-weight: 400; }
.has-warning, .warning-text { color: #946000; }
.indicator-panel, .metric-detail { overflow: hidden; min-width: 0; border: 1px solid var(--border-base); border-radius: 12px; background: var(--bg-card); }
.section-head { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px; padding: 20px; }
h2 { scroll-margin-top: 170px; margin: 0; color: var(--text-primary); font-size: 17px; font-weight: 650; }
h2:focus { outline: none; }
.section-head p { margin: 7px 0 0; font-size: 12px; color: var(--text-secondary); }
.attention-toggle { display: flex; gap: 7px; align-items: center; font-size: 13px; white-space: nowrap; cursor: pointer; }
.attention-toggle input { accent-color: var(--primary-600); }
.metric-name { font-size: 13px; font-weight: 550; }
.rate-cell { display: grid; gap: 4px; }
.rate-cell strong { font-size: 14px; font-variant-numeric: tabular-nums; }
.rate-cell span { font-size: 11px; color: var(--text-secondary); }
.rate-cell .warning-text { color: #946000; }
.basis-count { font-variant-numeric: tabular-nums; color: var(--text-secondary); }
.indicator-panel :deep(.dt__table) { min-width: 650px; }
.indicator-panel :deep(.dt__td) { padding-top: 12px; padding-bottom: 12px; }
.chart-grid { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 18px; min-width: 0; }
.chart-grid > * { min-width: 0; }
.chart-note, .chart-values { font-size: 12px; color: var(--text-secondary); }
.chart-values { padding: 12px 0 0; }
summary { cursor: pointer; width: fit-content; }
.table-scroll { overflow: auto; }
.chart-values table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.chart-values th, .chart-values td { padding: 8px; text-align: left; border-bottom: 1px solid var(--border-base); }
.chart-values caption { text-align: left; padding-bottom: 8px; }
.score-values > div { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid var(--border-base); }
.state { display: flex; gap: 12px; align-items: center; justify-content: center; flex-wrap: wrap; padding: 32px 20px; color: var(--text-secondary); font-size: 13px; }
.notice { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 12px 16px; background: var(--bg-card); border: 1px solid var(--border-base); border-radius: 8px; font-size: 13px; }
.is-error { color: var(--danger-600, #b42318); }
.metric-detail { padding: 0 24px 24px; }
.metric-detail .section-head { padding: 24px 0; }
.eyebrow { display: block; margin-bottom: 8px; font-size: 12px; color: var(--text-secondary); }
.metric-result { display: flex; gap: 18px; align-items: baseline; flex-wrap: wrap; padding-bottom: 24px; }
.metric-result strong { font-size: 36px; font-weight: 650; font-variant-numeric: tabular-nums; }
.metric-result span { color: var(--text-secondary); font-size: 13px; }
.metric-basis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; padding: 20px 0; border-block: 1px solid var(--border-base); }
.metric-basis > div { display: grid; gap: 10px; }
.metric-basis span { font-size: 13px; color: var(--text-secondary); }
.metric-basis strong { font-size: 22px; }
.definition { padding: 16px 0; font-size: 13px; line-height: 1.8; color: var(--text-secondary); }
.definition h3 { color: var(--text-primary); font-size: 14px; }
@media (max-width: 1000px) { .chart-grid { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 600px) { .filters { padding: 12px; gap: 10px; } .filter-field { flex-basis: 100%; max-width: none; } .counter-strip > div { padding: 0 12px; } .counter-strip dt { font-size: 12px; } .counter-strip dd { font-size: 24px; } .section-head { padding: 16px; } .metric-detail { padding-inline: 16px; } }
</style>
