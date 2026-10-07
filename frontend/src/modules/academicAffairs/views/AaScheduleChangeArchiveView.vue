<template>
  <ModulePageShell
    title="调停课归档"
    subtitle="只读原审批、通知单与课位历史；终态记录不在本页重新办理"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <template #actions><AppButton variant="primary" @click="$router.push('/admin/academic-affairs/schedule-change')">查看调停课台账</AppButton></template>
    <div class="mp-stack">
      <ol class="sc-archive-rail" aria-label="调停课归档责任链"><li v-for="(stage, index) in stages" :key="stage" :class="{ 'is-done': index < 4, 'is-active': index === 4 }"><b>{{ index + 1 }}</b><span>{{ stage }}</span><small>{{ index === 4 ? '当前归档核对' : '由正式状态确认' }}</small></li></ol>
      <AppInlineAlert type="info" title="已封存事实只读；UNKNOWN 域会阻断新的封存" description="原审批和课位历史不在本页覆盖。需要纠错时应走受控纠错版本，并由独立责任岗位复核。" />
      <ScheduleChangeEvidence v-if="selectedId" :change-id="selectedId" :ctx="ctx" @close="closeDetail" @notice="goNotice" />
      <template v-else>
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
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 调停课归档（/admin/academic-affairs/schedule-change/archive）：台账的终态特化视图，
 * 服务层强制过滤仅终态记录（复用 archive_list()，与台账共用同一底层查询，不重复实现）。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert } from '@/components/common'
import { scheduleChangeApi, CHANGE_TYPES } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import ScheduleChangeEvidence from '../components/parallel-b/ScheduleChangeEvidence.vue'
import { currentUserFromToken } from '@/services/http/client'

const TERMINAL_STATUS = [
  { value: 'APPLIED', label: '已生效', tone: 'success' },
  { value: 'REJECTED', label: '已驳回', tone: 'danger' },
  { value: 'CANCELLED', label: '已撤销', tone: 'default' }
]

const EMPTY = () => ({ changeType: '', status: '', termId: '', dateFrom: '', dateTo: '' })

export default {
  name: 'AaScheduleChangeArchiveView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppInlineAlert, ScheduleChangeEvidence },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: true, error: '', loadSeq: 0,
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
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    selectedId() { return String(this.$route.query.changeId || '') },
    stages() { return ['正式课位', '发起申请', '冲突预检', '审批生效', '通知归档'] },
    roleName() { return this.ctx?.currentRole?.roleName || '教务' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: CHANGE_TYPES.map((t) => ({ value: t.value, label: t.label })) },
        { key: 'status', label: '终态', type: 'select', options: TERMINAL_STATUS.map((s) => ({ value: s.value, label: s.label })) },
        { key: 'termId', label: '学期ID', type: 'text', placeholder: '学期主键' },
        { key: 'date', label: '发起时间', type: 'daterange',
          startKey: 'dateFrom', endKey: 'dateTo',
          memoryKey: 'academicAffairs.scheduleChangeArchive.dateRange', emptyLabel: '全部时间' }
      ]
    }
  },
  watch: { identityKey() { this.loadSeq++; this.rows = []; this.total = 0; this.closeDetail(); this.load() } },
  created() { this.load() },
  beforeUnmount() { this.loadSeq++ },
  methods: {
    typeTone(t) { return { ADJUST: 'processing', STOP: 'warning', MAKEUP: 'info' }[t] || 'default' },
    statusLabel(s) { return (TERMINAL_STATUS.find((x) => x.value === s) || {}).label || (s ? '状态待确认' : '—') },
    statusTone(s) { return (TERMINAL_STATUS.find((x) => x.value === s) || {}).tone || 'default' },
    async load() {
      const seq = ++this.loadSeq, identity = this.identityKey
      const query = JSON.stringify([this.filters, this.page])
      const current = () => seq === this.loadSeq && identity === this.identityKey && query === JSON.stringify([this.filters, this.page])
      this.loading = true; this.error = ''
      try {
        const res = await scheduleChangeApi.archive({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (!current()) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
        else { this.rows = []; this.total = 0; this.error = res.message || '调停课归档加载失败' }
      } catch (error) { if (current()) { this.rows = []; this.total = 0; this.error = error?.message || '调停课归档加载失败' } }
      finally { if (current()) this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    goDetail(row) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, changeId: row.changeId } }) },
    closeDetail() { const query = { ...this.$route.query }; delete query.changeId; this.$router.replace({ path: this.$route.path, query }) },
    goNotice(row) { this.$router.push(`/admin/academic-affairs/print/schedule-change/${row.changeId}/notice`) }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-link { color: var(--pri, #2563eb); background: none; border: none; cursor: pointer; font-size: 13px; padding: 0; }
.sc-archive-rail { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); list-style: none; margin: 0; padding: 15px 10px; background: var(--bg-card, #fff); border: 1px solid var(--line, #dce4ee); border-radius: 12px; }.sc-archive-rail li { position: relative; display: grid; justify-items: center; gap: 4px; text-align: center; color: var(--t2, #52647a); font-size: 12px; }.sc-archive-rail li::after { content: ''; position: absolute; top: 12px; left: calc(50% + 18px); width: calc(100% - 36px); height: 1px; background: var(--line, #dce4ee); }.sc-archive-rail li:last-child::after { display: none; }.sc-archive-rail b { position: relative; z-index: 1; display: grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; border: 1px solid #b7dfc2; color: #16803c; background: #f0f9f2; }.sc-archive-rail .is-active b { color: #fff; border-color: var(--pri, #2563eb); background: var(--pri, #2563eb); }.sc-archive-rail small { color: var(--t3, #94a3b8); }
@media (max-width: 760px) { .sc-archive-rail { grid-template-columns: 1fr; gap: 10px; }.sc-archive-rail li { justify-items: start; grid-template-columns: 26px auto; text-align: left; }.sc-archive-rail li::after { display: none; }.sc-archive-rail li small { grid-column: 2; } }
</style>
