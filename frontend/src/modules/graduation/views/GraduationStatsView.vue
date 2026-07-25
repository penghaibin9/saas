<template>
  <ModulePageShell
    title="毕设统计报表"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <p class="mp-note">以下为当前批次、当前数据范围内的汇总（时间筛选待后端统一接入后开放）。</p>
      <EmptyState v-if="!hasBatch" title="请先选择或创建毕设批次" description="顶部批次条选择当前工作批次后，再查看统计。" />
      <LoadingState v-else-if="loading" />
      <div v-else class="mp-stack">
        <section v-for="b in blocks" :key="b.key" class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">{{ b.title }}</span></div>
          <div class="mp-card__body gs-grid">
            <div v-if="b.data && b.data.total !== undefined" class="gs-cell"><b>{{ b.data.total }}</b><span>总数</span></div>
            <div v-for="s in (b.data && b.data.byStatus) || []" :key="s.status || s.label" class="gs-cell">
              <b>{{ s.count }}</b><span>{{ s.label }}</span>
            </div>
            <div v-for="e in extras(b)" :key="e.label" class="gs-cell gs-cell--extra"><b>{{ e.value }}</b><span>{{ e.label }}</span></div>
            <div v-if="!b.data && b.error" class="mp-note">
              统计加载失败
              <button type="button" class="mp-link" @click="loadOne(b)">重试</button>
            </div>
            <div v-else-if="!b.data" class="mp-note">暂无统计口径</div>
          </div>
          <div v-if="chartData(b).length >= 2" class="mp-card__body" style="padding-top: 0">
            <AppStackedBarChart
              :title="b.title + ' · 状态分布'"
              :data="chartData(b)"
              horizontal
              :height="Math.max(150, chartData(b).length * 40)"
              x-field="label"
              y-field="count"
              series-field="cat"
              value-label="数量"
            />
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕设统计报表中心（/admin/graduation/stats-report）。接各域真实 /stats，只读聚合。 */
import { ModulePageShell, LoadingState, EmptyState } from '@/components/business'
import { AppStackedBarChart } from '@/components/common'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

export default {
  name: 'GraduationStatsView',
  components: { ModulePageShell, LoadingState, EmptyState, AppStackedBarChart },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true,
      blocks: [
        { key: 'proposal', title: '开题统计', fn: 'getProposalStats', withBatch: true, data: null },
        { key: 'guidance', title: '指导频次统计', fn: 'getGuidanceStats', withBatch: true, data: null },
        { key: 'midterm', title: '中期检查统计', fn: 'getMidtermStats', withBatch: true, data: null },
        { key: 'final', title: '成果提交统计', fn: 'getFinalStats', withBatch: true, data: null },
        { key: 'plagiarism', title: '查重统计', fn: 'getPlagiarismStats', withBatch: true, data: null },
        { key: 'review', title: '教师评阅统计', fn: 'getReviewStats', withBatch: true, data: null },
        { key: 'peer', title: '成果互查统计', fn: 'getPeerStats', withBatch: true, data: null },
        { key: 'defense', title: '答辩评分统计', fn: 'getDefenseScoreStats', withBatch: true, data: null },
        { key: 'grade', title: '成绩评定统计', fn: 'getGradeStats', withBatch: true, data: null }
      ]
    }
  },
  computed: {
    hasBatch() {
      return !!this.batchStore.selectedBatchId
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先在顶部选择或创建毕设批次'
      const batch = this.batchStore.selectedBatchName ? `${this.batchStore.selectedBatchName} · ` : ''
      return `${batch}开题 / 指导 / 中期 / 查重 / 评阅 / 答辩 / 成绩 / 互查各阶段进度与质量统计`
    }
  },
  created() { this.loadAll() },
  watch: {
    'batchStore.selectedBatchId'() { this.loadAll() }
  },
  methods: {
    /** 各域 byStatus → 横向条形图数据（全零/单项不出图，不造假） */
    chartData(b) {
      return ((b.data && b.data.byStatus) || []).filter((s) => (s.count || 0) > 0).map((s) => ({ label: s.label, count: s.count, cat: '数量' }))
    },
    extras(b) {
      const d = b.data || {}
      const out = []
      if (d.notSubmitted !== undefined) out.push({ label: '未提交', value: d.notSubmitted })
      if (d.plagiarismOver !== undefined) out.push({ label: '查重超标', value: d.plagiarismOver })
      if (d.avgCount !== undefined) out.push({ label: '平均指导次数', value: d.avgCount })
      if (d.insufficientCount !== undefined) out.push({ label: '指导不足', value: d.insufficientCount })
      if (d.publishedAvg !== undefined && d.publishedAvg !== null) out.push({ label: '已发布均分', value: d.publishedAvg })
      if (d.excellentCount !== undefined) out.push({ label: '优秀数', value: d.excellentCount })
      return out
    },
    async loadOne(b) {
      if (!this.hasBatch) {
        b.data = null
        b.error = ''
        return
      }
      const params = b.withBatch ? { batchId: this.batchStore.selectedBatchId } : undefined
      const res = params ? await graduationMoreApi[b.fn](params) : await graduationMoreApi[b.fn]()
      if (res.code === 0) {
        b.data = res.data
        b.error = ''
      } else {
        b.data = null
        b.error = res.message || '加载失败'
      }
    },
    async loadAll() {
      this.loading = true
      if (!this.hasBatch) {
        this.blocks.forEach((b) => { b.data = null; b.error = '' })
        this.loading = false
        return
      }
      await Promise.all(this.blocks.map((b) => this.loadOne(b)))
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gs-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: var(--space-3); }
.gs-cell { display: flex; flex-direction: column; padding: var(--space-2) var(--space-3); background: var(--gray-50); border: 1px solid var(--border-light); border-radius: var(--radius-md); }
.gs-cell b { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.gs-cell span { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.gs-cell--extra { background: var(--primary-50); border-color: var(--primary-100); }
</style>
