<template>
  <ModulePageShell
    title="成绩总览"
    subtitle="分数段分布 + 及格率（读侧聚合，数据来自已发布成绩）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/grade-fail')">挂科清单</button>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/grade-entry')">成绩录入</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">学期<input v-model.trim="term" class="aa-input aa-input--sm" placeholder="学期码，如 2026-1（空=全部）" @keyup.enter="load" /></label>
        <button class="mp-btn" @click="load">查询</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="aa-metric-grid">
          <AppMetricCard title="总成绩记录" :value="data.total" unit="条" />
          <AppMetricCard title="及格率" :value="passRatePct" unit="%" />
        </div>
        <AppSectionCard title="分数段分布">
          <EmptyState v-if="!data.total" title="暂无成绩数据" description="发布成绩录入任务后，这里出现分数段分布" />
          <div v-else class="aa-dist">
            <div v-for="d in data.distribution" :key="d.range" class="aa-dist__row">
              <span class="aa-dist__label">{{ d.range }}</span>
              <div class="aa-dist__bar-wrap"><div class="aa-dist__bar" :style="{ width: barWidth(d.count) }"></div></div>
              <span class="aa-dist__count">{{ d.count }}</span>
            </div>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 成绩总览（/admin/academic-affairs/grade-overview）：GET /grade-views/analysis。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaGradeOverviewView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppMetricCard, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', term: '', data: { total: 0, passRate: 0, distribution: [] } }
  },
  computed: {
    passRatePct() { return Math.round((this.data.passRate || 0) * 100) },
    maxCount() { return Math.max(1, ...(this.data.distribution || []).map((d) => d.count)) }
  },
  created() { this.load() },
  methods: {
    barWidth(count) { return Math.round((count / this.maxCount) * 100) + '%' },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getGradeAnalysis(this.term || undefined)
      if (res.code === 0) this.data = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 200px; }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; }
.aa-dist__row { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; }
.aa-dist__label { width: 72px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-dist__bar-wrap { flex: 1; height: 18px; background: var(--fill-100, #f2f3f5); border-radius: 4px; overflow: hidden; }
.aa-dist__bar { height: 100%; background: var(--primary-400, #60a5fa); border-radius: 4px; }
.aa-dist__count { width: 48px; text-align: right; font-size: 13px; color: var(--text-900, #1f2329); }
</style>
