<template>
  <AppPageShell
    title="谈心谈话统计"
    subtitle="谈话工作量与完成率聚合，可按谈话类型或辅导员分组。仅聚合口径，不含谈话原文。"
    role-name="学工处 / 学院"
    data-scope-name="按数据范围聚合"
    watermark-purpose="谈话工作量统计"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载谈话统计..." @retry="load"
                    @back="$router.push('/admin/student-affairs/talk')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <AppSectionCard title="分组完成率">
        <div class="ts-tabs">
          <button v-for="g in groups" :key="g.key" type="button" class="ts-tab"
                  :class="{ 'is-on': groupBy === g.key }" @click="setGroup(g.key)">{{ g.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>{{ groupColLabel }}</th><th>谈话数</th><th>已完成</th><th>完成率</th></tr></thead>
          <tbody>
            <tr v-for="row in breakdown" :key="row.key">
              <td><strong>{{ keyLabel(row.key) }}</strong></td>
              <td>{{ row.total }}</td>
              <td>{{ row.completed }}</td>
              <td>
                <div class="ts-bar"><div class="ts-bar__fill" :style="{ width: pct(row) + '%' }"></div><span>{{ pct(row) }}%</span></div>
              </td>
            </tr>
            <tr v-if="!breakdown.length"><td colspan="4" class="sa-empty">暂无谈话记录</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const TYPE_LABELS = {
  ACADEMIC: '学业', PSYCHOLOGICAL: '心理', LIFE: '生活', CAREER: '就业', DISCIPLINE: '违纪',
  ECONOMIC: '经济', SAFETY: '安全', ROUTINE: '常规', OTHER: '其他'
}
const GROUPS = [{ key: 'TYPE', label: '按谈话类型' }, { key: 'COUNSELOR', label: '按辅导员' }]

export default {
  name: 'TalkStatsView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppSectionCard },
  data() {
    return { loading: true, errorMessage: '', stats: { total: 0, completed: 0, completionRate: 0, breakdown: [] }, groupBy: 'TYPE', groups: GROUPS }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    breakdown() { return this.stats.breakdown || [] },
    groupColLabel() { return this.groupBy === 'COUNSELOR' ? '辅导员' : '谈话类型' },
    metricCards() {
      const rate = Math.round((this.stats.completionRate || 0) * 100)
      const pending = (this.stats.total || 0) - (this.stats.completed || 0)
      return [
        { key: 't', label: '谈话总数', value: this.stats.total || 0, accent: 'primary' },
        { key: 'c', label: '已完成', value: this.stats.completed || 0, accent: 'success' },
        { key: 'p', label: '待完成', value: pending, accent: pending ? 'warning' : 'success' },
        { key: 'r', label: '完成率', value: rate + '%', accent: 'primary' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      try {
        const res = await studentAffairsApi.getTalkStats(this.groupBy)
        this.stats = res.data || { total: 0, completed: 0, completionRate: 0, breakdown: [] }
      } catch (e) {
        this.errorMessage = e.message || '谈话统计加载失败'
      } finally {
        this.loading = false
      }
    },
    setGroup(k) { if (this.groupBy === k) return; this.groupBy = k; this.load() },
    keyLabel(k) {
      if (!k) return '未分类'
      if (this.groupBy === 'COUNSELOR') return '辅导员#' + k
      return TYPE_LABELS[k] || k
    },
    pct(row) { return row.total ? Math.round(row.completed / row.total * 100) : 0 }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.ts-tabs { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.ts-tab { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 6px 16px; font-size: var(--font-size-sm); cursor: pointer; }
.ts-tab.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.ts-bar { position: relative; background: var(--bg-muted, #f1f5f9); border-radius: var(--radius-full); height: 18px; min-width: 120px; max-width: 220px; }
.ts-bar__fill { position: absolute; left: 0; top: 0; bottom: 0; background: var(--color-primary); border-radius: var(--radius-full); }
.ts-bar span { position: relative; font-size: var(--font-size-xs); padding-left: 8px; line-height: 18px; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } }
</style>
