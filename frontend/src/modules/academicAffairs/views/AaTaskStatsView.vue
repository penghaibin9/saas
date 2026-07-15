<template>
  <ModulePageShell
    title="教学任务统计"
    subtitle="批次/任务状态分布 · 分配率 · 教师确认率 · 按学期拆分"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">学期
          <select v-model="termId" class="aa-select" @change="load">
            <option value="">全部学期</option>
            <option v-for="t in terms" :key="t.termId" :value="t.termId">{{ t.yearCode }} 第 {{ t.termNo }} 学期</option>
          </select>
        </label>
        <button class="mp-btn" :disabled="loading" @click="load">刷新</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="stats">
        <div class="aa-metrics">
          <AppMetricCard title="任务批次总数" :value="stats.batchTotal" unit="个" />
          <AppMetricCard title="教学任务总数" :value="stats.taskTotal" unit="条" />
          <AppMetricCard title="分配率" :value="stats.assignRate.rate" unit="%"
                        :description="`已指定教师 ${stats.assignRate.numerator} / ${stats.assignRate.denominator}`" />
          <AppMetricCard title="教师确认率" :value="stats.teacherConfirmRate.rate" unit="%"
                        :description="`已确认 ${stats.teacherConfirmRate.numerator} / ${stats.teacherConfirmRate.denominator}`"
                        :accent="stats.teacherConfirmRate.rate >= 80 ? 'success' : 'warning'" />
          <AppMetricCard title="已合班任务" :value="stats.mergedCount" unit="条" />
        </div>

        <AppSectionCard title="批次状态分布">
          <DataTable :columns="statusCols" :rows="batchStatusRows" row-key="status" />
        </AppSectionCard>
        <AppSectionCard title="任务状态分布">
          <DataTable :columns="statusCols" :rows="taskStatusRows" row-key="status" />
        </AppSectionCard>
        <AppSectionCard title="按学期拆分">
          <EmptyState v-if="!stats.byTerm.length" title="暂无数据" />
          <DataTable v-else :columns="termCols" :rows="stats.byTerm" row-key="termId" />
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 教学任务统计（/admin/academic-affairs/teaching-tasks/stats）。
 * GET /academic-affairs/teaching-task-batches/stats。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppMetricCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_BATCH_STATUS, TASK_STATUS } from '@/modules/academicAffairs/constants/teaching'

export default {
  name: 'AaTaskStatsView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppMetricCard },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', stats: null, terms: [], termId: '',
      statusCols: [{ key: 'label', title: '状态' }, { key: 'count', title: '数量' }],
      termCols: [
        { key: 'termLabel', title: '学期' }, { key: 'batchCount', title: '批次数' },
        { key: 'taskTotal', title: '任务数' }, { key: 'confirmedTotal', title: '教师已确认' },
        { key: 'confirmRate', title: '确认率(%)' }
      ]
    }
  },
  computed: {
    batchStatusRows() {
      if (!this.stats) return []
      return Object.entries(this.stats.batchByStatus).map(([status, count]) => ({
        status, count, label: TASK_BATCH_STATUS[status] || status
      }))
    },
    taskStatusRows() {
      if (!this.stats) return []
      return Object.entries(this.stats.taskByStatus).map(([status, count]) => ({
        status, count, label: TASK_STATUS[status] || status
      }))
    }
  },
  created() {
    this.loadTerms()
    this.load()
  },
  methods: {
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) this.terms = res.data.list
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTeachingTaskStats({ termId: this.termId || undefined })
      if (res.code === 0) this.stats = res.data
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; min-width: 200px; }
.aa-metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
</style>
