<template>
  <ModulePageShell title="请假统计" subtitle="请假人数 / 天数 / 逾期未销口径 · 按班级/类型/状态下钻 · 数据范围裁剪"
    :role-name="roleName" :data-scope-name="scopeHint">
    <div class="mp-stack">
      <div class="flt">
        <AppQuickFilterChips v-model="groupBy" :options="groupOptions" @change="load" />
        <AppDateRangePicker v-model="range" @change="load" />
        <span class="mp-note">日期默认不限；口径：请假人数=范围内去重学生，逾期未销=当前 OVERDUE。</span>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="metrics">
          <AppMetricCard v-for="m in metrics" :key="m.key" :title="m.label" :value="m.value" :unit="m.unit"
            :accent="m.key === 'overdue' && m.value ? 'risk' : (m.key === 'waitCancel' && m.value ? 'warning' : 'primary')" />
        </div>

        <div class="sec-t">{{ groupLabel }}分布</div>
        <EmptyState v-if="!breakdown.length" title="暂无分布数据" description="当前范围内没有请假记录" />
        <DataTable v-else :columns="columns" :rows="breakdown" row-key="key">
          <template #cell-count="{ row }"><b>{{ row.count }}</b> 件</template>
          <template #cell-days="{ row }">{{ row.days }} 天</template>
          <template #cell-studentCount="{ row }">{{ row.studentCount }} 人</template>
        </DataTable>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 请假统计（/admin/campus-service/leave-stats）。
 * 指标卡（人数/天数/在假/待审/待销假/逾期/已销假）+ 按班级/类型/状态下钻。真实对接 /student-affairs/leave/stats。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppQuickFilterChips, AppDateRangePicker } from '@/components/common'
import { leaveApi } from '@/modules/studentAffairs/api/leave.api'

const GROUP_OPTIONS = [
  { label: '按班级', value: 'CLASS' }, { label: '按类型', value: 'TYPE' }, { label: '按状态', value: 'STATUS' }
]
const COLUMNS = [
  { key: 'label', title: '分组' }, { key: 'count', title: '请假数' },
  { key: 'days', title: '请假天数' }, { key: 'studentCount', title: '涉及人数' }
]

export default {
  name: 'LeaveStatsView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppMetricCard, AppQuickFilterChips, AppDateRangePicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, error: '', groupBy: 'CLASS', groupOptions: GROUP_OPTIONS,
      range: { start: '', end: '' }, metrics: [], breakdown: [], columns: COLUMNS
    }
  },
  computed: {
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '辅导员 / 学院学工 / 学工处' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.name) || '按数据范围裁剪' },
    groupLabel() { return (GROUP_OPTIONS.find((o) => o.value === this.groupBy) || {}).label || '' }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const params = { groupBy: this.groupBy || 'CLASS' }
      if (this.range && this.range.start) params.dateStart = this.range.start
      if (this.range && this.range.end) params.dateEnd = this.range.end
      const res = await leaveApi.stats(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; return }
      this.metrics = res.data.metrics || []
      this.breakdown = res.data.breakdown || []
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.flt { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.metrics { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: var(--space-3); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }
</style>
