<template>
  <ModulePageShell
    title="教学任务统计"
    subtitle="总数与下钻都按当前学期"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">学期
          <AppTermEntityPicker v-model="termId" placeholder="请选择学期" @change="changeTerm" />
        </label>
        <AppButton :loading="loading" @click="load">刷新</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!termId" title="先选择统计学期" description="学校未提供当前学期时，不自动合并其它学期。" />
      <template v-else-if="stats">
        <div class="aa-metrics">
          <AppMetricCard title="任务批次总数" :value="stats.batchTotal" unit="个" />
          <AppMetricCard title="教学任务总数" :value="stats.taskTotal" unit="条" />
          <AppMetricCard title="分配率" :value="stats.assignRate.rate" unit="%"
                        :description="`已指定教师 ${stats.assignRate.numerator} / ${stats.assignRate.denominator}`" />
          <AppMetricCard title="教师确认率" :value="stats.teacherConfirmRate.rate" unit="%"
                        :description="`已确认 ${stats.teacherConfirmRate.numerator} / ${stats.teacherConfirmRate.denominator}`"
                        :accent="stats.teacherConfirmRate.rate >= 80 ? 'success' : 'warning'" />
        </div>

        <div class="aa-stat-distributions">
        <AppSectionCard title="批次状态分布">
          <AppG2Chart v-if="batchStatusChart.length" :spec="batchStatusSpec" :height="240" />
          <DataTable :columns="statusCols" :rows="batchStatusRows" row-key="status" />
        </AppSectionCard>
        <AppSectionCard title="任务状态分布">
          <AppG2Chart v-if="taskStatusChart.length" :spec="taskStatusSpec" :height="240" />
          <DataTable :columns="statusCols" :rows="taskStatusRows" row-key="status" />
        </AppSectionCard>
        </div>
        <AppSectionCard title="同学期明细下钻">
          <EmptyState v-if="!stats.byTerm.length" title="所选学期暂无正式教学任务" />
          <DataTable v-else :columns="termCols" :rows="stats.byTerm" row-key="termId">
            <template #cell-actions="{ row }"><button class="mp-link" @click="openTerm(row)">查看任务批次</button></template>
          </DataTable>
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
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppMetricCard, AppG2Chart, AppTermEntityPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_BATCH_STATUS, TASK_STATUS } from '@/modules/academicAffairs/constants/teaching'

export default {
  name: 'AaTaskStatsView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppMetricCard, AppG2Chart, AppTermEntityPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', stats: null, termId: '', revision: 0,
      statusCols: [{ key: 'label', title: '状态' }, { key: 'count', title: '数量' }],
      termCols: [
        { key: 'termLabel', title: '学期' }, { key: 'batchCount', title: '批次数' },
        { key: 'taskTotal', title: '任务数' }, { key: 'confirmedTotal', title: '教师已确认' },
        { key: 'confirmRate', title: '确认率(%)' }, { key: 'actions', title: '办理入口' }
      ]
    }
  },
  computed: {
    batchStatusRows() {
      if (!this.stats) return []
      return Object.entries(this.stats.batchByStatus).map(([status, count]) => ({
        status, count, label: TASK_BATCH_STATUS[status] || (status ? '状态待确认' : '—')
      }))
    },
    taskStatusRows() {
      if (!this.stats) return []
      return Object.entries(this.stats.taskByStatus).map(([status, count]) => ({
        status, count, label: TASK_STATUS[status] || (status ? '状态待确认' : '—')
      }))
    },
    batchStatusChart() {
      return this.batchStatusRows.map(r => ({ name: r.label, value: r.count }))
    },
    taskStatusChart() {
      return this.taskStatusRows.map(r => ({ name: r.label, value: r.count }))
    },
    batchStatusSpec() {
      return {
        type: 'interval',
        data: this.batchStatusChart,
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    },
    taskStatusSpec() {
      return {
        type: 'interval',
        data: this.taskStatusChart,
        encode: { x: 'name', y: 'value' },
        axis: { y: { title: null } },
        style: { radiusTopLeft: 4, radiusTopRight: 4 }
      }
    }
  },
  async created() {
    this.termId = String(this.$route.query.termId || '')
    if (!this.termId) {
      const revision = this.revision
      const result = await academicAffairsApi.getCurrentTerm()
      if (revision !== this.revision) return
      if (result.code !== 0) { this.error = result.message || '当前学期读取失败，请选择学期后重试。'; this.loading = false; return }
      this.termId = String(result.data?.termId || '')
    }
    this.load()
  },
  watch: { '$route.query.termId'(value) { this.termId = String(value || ''); this.load() } },
  beforeUnmount() { this.revision++ },
  methods: {
    changeTerm() {
      this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: this.termId || undefined } })
      this.load()
    },
    openTerm(row) {
      if (String(row.termId) !== String(this.termId)) return
      this.$router.push({ path: '/admin/academic-affairs/teaching-tasks', query: { termId: row.termId, returnTo: this.$route.fullPath } })
    },
    async load() {
      const revision = ++this.revision
      const termId = this.termId
      this.loading = true
      this.error = ''
      this.stats = null
      if (!termId) { this.loading = false; return }
      try {
        const res = await academicAffairsApi.getTeachingTaskStats({ termId })
        if (revision !== this.revision || termId !== this.termId) return
        if (res.code !== 0) { this.error = res.message || '统计读取失败，请重试。'; return }
        if (!res.data || !Array.isArray(res.data.byTerm) || res.data.byTerm.some(row => String(row.termId) !== String(termId))) {
          this.error = '统计学期与所选学期不一致，请重新核对。'; return
        }
        this.stats = res.data
      } catch (error) {
        if (revision === this.revision) this.error = error.message || '网络连接失败，请重试。'
      } finally { if (revision === this.revision) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-select { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; min-width: 200px; }
.aa-metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 14px; }
.aa-stat-distributions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
@media (max-width: 900px) { .aa-stat-distributions { grid-template-columns: 1fr; } }
</style>
