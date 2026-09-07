<template>
  <ModulePageShell flat title="请假统计" subtitle="掌握请假与返校情况，点击分组查看对应记录。"
    :role-name="roleName" :data-scope-name="scopeHint">
    <div class="mp-stack">
      <div class="flt">
        <AppQuickFilterChips v-model="groupBy" :options="groupOptions" @change="load" />
        <AppDateRangePicker :show-empty-hint="false" v-model="range" @change="load" />
        <details class="flat-details"><summary>统计口径</summary>按请假开始日期统计，人数按学生去重；逾期为当前逾期未销假记录。</details>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <BusinessMetrics :items="metrics" />

        <div class="sec-t">{{ groupLabel }}分布</div>
        <EmptyState v-if="!breakdown.length" title="暂无分布数据" description="当前范围内没有请假记录"><template #actions><button class="mp-link" @click="range = { start: '', end: '' }; load()">查看全部时间</button></template></EmptyState>
        <DataTable v-else :columns="columns" :rows="breakdown" row-key="key">
          <template #cell-count="{ row }"><button v-if="row.key" type="button" class="mp-link" @click="drillDown(row)">{{ row.count }} 件 · 查看</button><span v-else>{{ row.count }} 件</span></template>
          <template #cell-days="{ row }">{{ row.days }} 天</template>
          <template #cell-studentCount="{ row }">{{ row.studentCount }} 人</template>
        </DataTable>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import BusinessMetrics from '@/components/workspace/BusinessMetrics.vue'
/**
 * 请假统计（/admin/student-affairs/leave/stats）。
 * 指标卡（人数/天数/在假/待审/待销假/逾期/已销假）+ 按班级/类型/状态下钻。真实对接 /student-affairs/leave/stats。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppQuickFilterChips, AppDateRangePicker } from '@/components/common'
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
  components: { BusinessMetrics, ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppQuickFilterChips, AppDateRangePicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      hasActivated: false,
      loading: true, error: '', groupBy: 'CLASS', groupOptions: GROUP_OPTIONS,
      range: { start: '', end: '' }, metrics: [], breakdown: [], columns: COLUMNS
    }
  },
  computed: {
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '辅导员 / 学院学工 / 学工处' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && (this.ctx.dataScope.scopeName || this.ctx.dataScope.name)) || '按数据范围裁剪' },
    groupLabel() { return (GROUP_OPTIONS.find((o) => o.value === this.groupBy) || {}).label || '' }
  },
  created() { this.load() },
  activated() { if (this.hasActivated) this.load(); this.hasActivated = true },
  methods: {
    drillDown(row) {
      if (!row.key) return
      const query = {}
      if (this.groupBy === 'CLASS') query.classId = String(row.key)
      else if (this.groupBy === 'TYPE') query.leaveType = row.key
      else query.status = row.key
      if (this.range.start) query.dateStart = this.range.start
      if (this.range.end) query.dateEnd = this.range.end
      this.$router.push({ path: '/admin/student-affairs/leave/ledger', query })
    },
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
