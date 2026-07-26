<template>
  <ModulePageShell title="请假台账" subtitle="全状态请假记录 · 按数据范围裁剪 · Excel 台账导出（水印 + 留痕）"
    :role-name="roleName" :data-scope-name="scopeHint">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">导出 Excel 台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <div class="flt">
        <AppSearchBox v-model="filters.keyword" placeholder="学生姓名 / 学号" @search="search" />
        <AppSelect v-model="filters.status" :options="statusOptions" placeholder="全部状态" @change="onStatusChange" />
        <AppSelect v-model="filters.leaveType" :options="typeOptions" placeholder="全部类型" @change="search" />
        <AppDateRangePicker v-model="filters.range" @change="search" />
        <button type="button" class="mp-link" @click="reset">重置</button>
      </div>

      <div v-if="studentFilterLabel" class="lv-student-filter">
        <span>{{ studentFilterLabel }}</span>
        <button type="button" class="mp-link" @click="clearStudentFilter">清除筛选</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="没有符合条件的请假记录" description="试着放宽筛选条件或清空日期范围" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }} · {{ row.className }}</div>
        </template>
        <template #cell-range="{ row }">
          <div class="mp-cell-main">{{ fmt(row.startTime) }}</div>
          <div class="mp-cell-sub">至 {{ fmt(row.endTime) }}</div>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.affairsStatus" :label="row.affairsStatusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button type="button" class="mp-link" @click="openDetail(row)">查看</button>
        </template>
      </DataTable>

      <p class="mp-note">导出按当前筛选与数据范围裁剪，Excel 首行含导出人/时间水印，导出行为写审计。请假原因涉隐私，导出仅授权角色可见。</p>
    </div>

    <AppDrawer v-model:visible="detailVisible" :title="detail ? '请假详情 · ' + detail.studentName : '请假详情'">
      <template v-if="detail">
        <AppDescriptionList :items="detailItems" :columns="1" />
        <template v-if="detail.extensions && detail.extensions.length">
          <div class="sec-t">续假记录</div>
          <ul class="rec-list">
            <li v-for="e in detail.extensions" :key="e.id">{{ fmt(e.oldEndTime) }} → {{ fmt(e.newEndTime) }}（+{{ e.extendDays }}天）· {{ e.status }}</li>
          </ul>
        </template>
        <template v-if="detail.cancelRecords && detail.cancelRecords.length">
          <div class="sec-t">销假记录</div>
          <ul class="rec-list">
            <li v-for="c in detail.cancelRecords" :key="c.id">实际返校 {{ fmt(c.actualReturnAt) }} · {{ c.status }}<span v-if="c.confirmBy"> · {{ c.confirmBy }}</span></li>
          </ul>
        </template>
        <div class="sec-t">审批留痕</div>
        <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无处理记录" />
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 请假台账（/admin/campus-service/leave-ledger）。
 * 全状态请假记录，按数据范围裁剪；筛选（状态/类型/关键词/日期区间，日期默认不限）；
 * 导出 Excel 台账（公共导出底座，水印 + 导出审计）。真实对接 /student-affairs/leave 与 /leave/export。
 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppExportButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppSelect, AppDateRangePicker } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { leaveApi } from '@/modules/studentAffairs/api/leave.api'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'
import { resolveTodoStatus, readStudentFilter } from '@/modules/studentAffairs/utils/todoFilterSemantics'

const STATUS_OPTIONS = [
  { label: '待审批(公共)', value: 'PENDING' },
  { label: '待辅导员审批', value: 'COUNSELOR_REVIEW' }, { label: '学院审批', value: 'COLLEGE_REVIEW' },
  { label: '学工处审批', value: 'STUDENT_AFFAIRS_REVIEW' }, { label: '已通过', value: 'APPROVED' },
  { label: '续假审批中', value: 'EXTENSION_REVIEW' }, { label: '待销假确认', value: 'WAIT_CANCEL_LEAVE' },
  { label: '已销假', value: 'CLOSED' }, { label: '已逾期', value: 'OVERDUE' },
  { label: '已驳回', value: 'REJECTED' }, { label: '已退回', value: 'RETURNED' }, { label: '已取消', value: 'CANCELLED' }
]
const TYPE_OPTIONS = [
  { label: '病假', value: 'SICK' }, { label: '事假', value: 'PERSONAL' }, { label: '探亲假', value: 'HOME' },
  { label: '住院假', value: 'HOSPITAL' }, { label: '外出', value: 'GOOUT' }, { label: '其他', value: 'OTHER' }
]
const COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'leaveTypeLabel', title: '类型' },
  { key: 'range', title: '起止时间' }, { key: 'days', title: '天数' },
  { key: 'status', title: '状态' }, { key: 'actions', title: '操作' }
]
const EMPTY_FILTERS = () => ({ keyword: '', status: '', leaveType: '', range: { start: '', end: '' }, studentId: '' })

export default {
  name: 'LeaveLedgerView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppExportButton,
    AppDescriptionList, AppAuditTrail, AppSearchBox, AppSelect, AppDateRangePicker, AppDrawer
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, error: '', rows: [], columns: COLUMNS, filters: EMPTY_FILTERS(),
      studentFilter: { studentId: '', studentNo: '', studentName: '' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      statusOptions: STATUS_OPTIONS, typeOptions: TYPE_OPTIONS,
      detailVisible: false, detail: null
    }
  },
  computed: {
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '辅导员 / 学院学工 / 学工处' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && (this.ctx.dataScope.scopeName || this.ctx.dataScope.name)) || '按数据范围裁剪' },
    studentFilterLabel() {
      const f = this.studentFilter || {}
      if (!f.studentId && !f.studentNo) return ''
      let name = f.studentName || ''
      let no = f.studentNo || ''
      const id = f.studentId || ''
      if ((!name || !no) && id && this.rows && this.rows.length) {
        const hit = this.rows.find((x) => String(x.studentId) === String(id))
        if (hit) {
          if (!name) name = hit.studentName || hit.realName || ''
          if (!no) no = hit.studentNo || ''
        }
      }
      if (name || no) return `当前学生筛选：${name || '学生'}${no ? ` / ${no}` : ''}`
      return `当前学生筛选：#${id}`
    },
    detailItems() {
      const d = this.detail || {}
      return [
        { label: '学生', value: `${d.studentName || ''}（${d.studentNo || ''} · ${d.className || ''}）` },
        { label: '请假类型 / 天数', value: `${d.leaveTypeLabel || ''} · ${d.days || 0} 天` },
        { label: '起止时间', value: `${this.fmt(d.startTime)} ~ ${this.fmt(d.endTime)}` },
        { label: '应返校 / 实际返校', value: `${this.fmt(d.expectedReturnAt) || '—'} / ${this.fmt(d.actualReturnAt) || '—'}` },
        { label: '状态', value: d.affairsStatusLabel },
        { label: '请假事由', value: d.reason || '—' }
      ]
    },
    auditRecords() {
      return ((this.detail && this.detail.auditTrail) || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail, at: t.occurredAt
      }))
    }
  },
  created() {
    this.applyRouteFilters()
    this.load()
  },
  watch: {
    '$route.query'() { this.applyRouteFilters(); this.pagination.page = 1; this.load() }
  },
  methods: {
    fmt(v) { return v ? formatDateTime(v) : '' },
    applyRouteFilters() {
      const q = this.$route.query || {}
      this.studentFilter = readStudentFilter(q)
      this.filters.studentId = this.studentFilter.studentId || ''
      if (!q.status) {
        this.filters.status = ''
        return
      }
      const resolved = resolveTodoStatus('leave', q.status)
      if (resolved.activeKey === 'PENDING' || q.status === 'PENDING') this.filters.status = 'PENDING'
      else if (resolved.activeKey === 'WAIT_CANCEL_LEAVE' || q.status === 'CANCEL_PENDING') this.filters.status = 'WAIT_CANCEL_LEAVE'
      else if (resolved.activeKey === 'OVERDUE') this.filters.status = 'OVERDUE'
      else if (resolved.matchStatuses && resolved.matchStatuses.length === 1) this.filters.status = resolved.matchStatuses[0]
      else this.filters.status = String(q.status)
    },
    clearStudentFilter() {
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      this.filters.studentId = ''
      const q = { ...this.$route.query }
      delete q.studentId
      delete q.studentNo
      delete q.studentName
      this.$router.replace({ query: q }).catch(() => {})
    },
    onStatusChange() {
      const q = { ...this.$route.query }
      if (!this.filters.status) delete q.status
      else q.status = this.filters.status
      this.$router.replace({ query: q }).catch(() => {})
      this.search()
    },
    buildParams() {
      const f = this.filters
      const p = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      if (f.keyword) p.keyword = f.keyword
      if (f.status) p.status = f.status
      if (f.leaveType) p.leaveType = f.leaveType
      if (f.studentId) p.studentId = f.studentId
      if (f.range && f.range.start) p.dateStart = f.range.start
      if (f.range && f.range.end) p.dateEnd = f.range.end
      return p
    },
    search() { this.pagination.page = 1; this.load() },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.studentFilter = { studentId: '', studentNo: '', studentName: '' }
      this.pagination.page = 1
      const q = { ...this.$route.query }
      delete q.status; delete q.studentId; delete q.studentNo; delete q.studentName
      this.$router.replace({ query: q }).catch(() => {})
      this.load()
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const res = await leaveApi.ledger(this.buildParams())
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; return }
      this.rows = res.data.list
      this.pagination.total = res.data.total
    },
    async openDetail(row) {
      const res = await leaveApi.detail(row.id)
      if (res.code !== 0) return toast.error(res.message || '详情加载失败')
      this.detail = res.data
      this.detailVisible = true
    },
    exportFn() {
      const p = this.buildParams()
      delete p.page; delete p.pageSize
      return leaveApi.exportLedger(p)
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条请假台账（含水印，已写导出审计）`) }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.flt { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.lv-student-filter {
  display: flex; align-items: center; justify-content: space-between; gap: var(--space-2);
  margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-md); background: var(--warning-50, #fffbeb);
  border: 1px solid var(--warning-200, #fde68a); font-size: var(--font-size-sm); color: var(--text-primary);
}
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }
.rec-list { list-style: none; margin: 0; padding: 0; font-size: var(--font-size-sm); color: var(--text-secondary); }
.rec-list li { padding: var(--space-1) 0; }
</style>
