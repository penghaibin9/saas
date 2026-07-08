<template>
  <ModulePageShell
    title="毕设统计报表"
    subtitle="开题 / 指导频次 / 中期 / 查重 / 评阅 / 答辩 / 成绩 / 互查 各阶段统计（接各域真实 /stats）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <AppDateRangePicker
        v-model="statsRange"
        label="统计时间范围"
        mode="filter"
        empty-label="全部时间"
        memory-key="graduation.statsReport.dateRange"
        @change="loadAll"
      />
      <LoadingState v-if="loading" />
      <div v-else class="mp-stack">
        <section v-for="b in blocks" :key="b.key" class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">{{ b.title }}</span></div>
          <div class="mp-card__body gs-grid">
            <div v-if="b.data && b.data.total !== undefined" class="gs-cell"><b>{{ b.data.total }}</b><span>总数</span></div>
            <div v-for="s in (b.data && b.data.byStatus) || []" :key="s.status || s.label" class="gs-cell">
              <b>{{ s.count }}</b><span>{{ s.label }}</span>
            </div>
            <div v-for="e in extras(b)" :key="e.label" class="gs-cell gs-cell--extra"><b>{{ e.value }}</b><span>{{ e.label }}</span></div>
            <div v-if="!b.data" class="mp-note">加载失败或暂无数据</div>
          </div>
        </section>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕设统计报表中心（/admin/graduation/stats-report）。接各域真实 /stats，只读聚合。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppDateRangePicker } from '@/components/common/date'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'

export default {
  name: 'GraduationStatsView',
  components: { ModulePageShell, LoadingState, AppDateRangePicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      statsRange: { start: '', end: '' },
      blocks: [
        { key: 'proposal', title: '开题统计', fn: 'getProposalStats', data: null },
        { key: 'guidance', title: '指导频次统计', fn: 'getGuidanceStats', data: null },
        { key: 'midterm', title: '中期检查统计', fn: 'getMidtermStats', data: null },
        { key: 'final', title: '成果提交统计', fn: 'getFinalStats', data: null },
        { key: 'plagiarism', title: '查重统计', fn: 'getPlagiarismStats', data: null },
        { key: 'review', title: '教师评阅统计', fn: 'getReviewStats', data: null },
        { key: 'peer', title: '成果互查统计', fn: 'getPeerStats', data: null },
        { key: 'defense', title: '答辩评分统计', fn: 'getDefenseScoreStats', data: null },
        { key: 'grade', title: '成绩评定统计', fn: 'getGradeStats', data: null }
      ]
    }
  },
  created() { this.loadAll() },
  methods: {
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
    async loadAll() {
      this.loading = true
      // 时间范围默认空=全部时间；后端暂未统一接 dateStart/dateEnd 时前端仍保留筛选 UI 与记忆
      await Promise.all(this.blocks.map(async (b) => {
        const res = await graduationMoreApi[b.fn]()
        b.data = res.code === 0 ? res.data : null
      }))
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
