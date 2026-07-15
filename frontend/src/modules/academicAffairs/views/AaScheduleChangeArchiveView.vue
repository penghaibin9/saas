<template>
  <ModulePageShell
    title="调停课归档"
    :subtitle="'共 ' + total + ' 条已终结记录（已生效/已驳回/已撤销）· 事后核查与材料留存'"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无已归档的调停课记录" description="所选筛选条件下没有已终结的调课/停课/补课单据" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.className || '—' }} · {{ row.teacherName || '—' }}</div>
        </template>
        <template #cell-type="{ row }"><StatusTag :type="typeTone(row.changeType)" :label="row.changeTypeLabel" dot /></template>
        <template #cell-status="{ row }"><StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-terminatedAt="{ row }">{{ row.createdAt || '—' }}</template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">{{ row.status === 'APPLIED' ? '详情/打印通知单' : '查看详情' }}</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 调停课归档（/admin/academic-affairs/schedule-change/archive）：台账的终态特化视图，
 * 服务层强制过滤仅终态记录（复用 archive_list()，与台账共用同一底层查询，不重复实现）。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { scheduleChangeApi, CHANGE_TYPES } from '@/modules/academicAffairs/api/academic-schedule-change.api'

const TERMINAL_STATUS = [
  { value: 'APPLIED', label: '已生效', tone: 'success' },
  { value: 'REJECTED', label: '已驳回', tone: 'danger' },
  { value: 'CANCELLED', label: '已撤销', tone: 'default' }
]

const EMPTY = () => ({ changeType: '', status: '', termId: '' })

export default {
  name: 'AaScheduleChangeArchiveView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: true, error: '',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY(),
      columns: [
        { key: 'course', title: '课程 / 班级·教师' },
        { key: 'type', title: '类型' },
        { key: 'status', title: '终态' },
        { key: 'terminatedAt', title: '发起时间' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '教务' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: CHANGE_TYPES.map((t) => ({ value: t.value, label: t.label })) },
        { key: 'status', label: '终态', type: 'select', options: TERMINAL_STATUS.map((s) => ({ value: s.value, label: s.label })) },
        { key: 'termId', label: '学期ID', type: 'text', placeholder: '学期主键' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    typeTone(t) { return { ADJUST: 'processing', STOP: 'warning', MAKEUP: 'info' }[t] || 'default' },
    statusLabel(s) { return (TERMINAL_STATUS.find((x) => x.value === s) || {}).label || s },
    statusTone(s) { return (TERMINAL_STATUS.find((x) => x.value === s) || {}).tone || 'default' },
    async load() {
      this.loading = true; this.error = ''
      const res = await scheduleChangeApi.archive({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    goDetail(row) { this.$router.push(`/admin/academic-affairs/print/schedule-change/${row.changeId}/notice`) }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link { color: var(--pri, #2563eb); background: none; border: none; cursor: pointer; font-size: 13px; padding: 0; }
</style>
