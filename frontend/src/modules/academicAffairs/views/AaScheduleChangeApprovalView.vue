<template>
  <ModulePageShell
    title="调停课审批"
    subtitle="学院审 → 教务处审；终审通过后系统自动改写课表（原课位留痕 + 生成新项）并通知师生"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无待审调停课" description="学院审/教务处审通过或驳回后从此处移除" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.className || '—' }} · {{ row.teacherName || '—' }}</div>
        </template>
        <template #cell-type="{ row }"><StatusTag :type="typeTone(row.changeType)" :label="row.changeTypeLabel" dot /></template>
        <template #cell-move="{ row }">
          <span class="sc-slot">周{{ row.origin.weekday }}·{{ row.origin.slotNo }}节</span>
          <template v-if="row.changeType !== 'STOP'">
            <span class="sc-arrow">→</span>
            <span class="sc-slot sc-slot--to">周{{ row.target.weekday }}·{{ row.target.slotNo }}节</span>
          </template>
          <span v-else class="sc-stop">停课</span>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="askApprove(row)">通过</button>
          <button class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askReject(row)">驳回</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      reason-label="驳回原因（≥5 字）" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 调停课审批工作台（/admin/academic-affairs/schedule-change/approval）：学院/教务处两级审批。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { scheduleChangeApi, CHANGE_TYPES, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { toast } from '@/utils/toast'

const PENDING = ['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW']
const EMPTY = () => ({ changeType: '', status: '' })

export default {
  name: 'AaScheduleChangeApprovalView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY(),
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, action: null, row: null },
      columns: [
        { key: 'course', title: '课程 / 班级·教师' },
        { key: 'type', title: '类型' },
        { key: 'move', title: '原课位 → 目标' },
        { key: 'status', title: '当前节点' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  computed: {
    roleName() { return this.ctx?.currentRole?.roleName || '学院/教务处' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: CHANGE_TYPES.map((t) => ({ value: t.value, label: t.label })) },
        { key: 'status', label: '节点', type: 'select', options: CHANGE_STATUS.filter((s) => PENDING.includes(s.value)).map((s) => ({ value: s.value, label: s.label })) }
      ]
    }
  },
  created() { this.load() },
  methods: {
    typeTone(t) { return { ADJUST: 'processing', STOP: 'warning', MAKEUP: 'info' }[t] || 'default' },
    statusLabel(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).label || s },
    statusTone(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).tone || 'default' },
    async load() {
      this.loading = true; this.error = ''
      const res = await scheduleChangeApi.list({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) {
        // 仅保留在途待审（后端已按范围过滤；前端再收敛为待审节点）
        const all = res.data.list
        this.rows = this.filters.status ? all : all.filter((r) => PENDING.includes(r.status))
        this.total = this.filters.status ? res.data.total : this.rows.length
      } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    askApprove(row) {
      const final = row.status === 'COLLEGE_REVIEW' || row.status === 'ACADEMIC_REVIEW'
      this.confirm = { visible: true, title: '审批通过', type: 'primary', confirmText: '确认通过', requireReason: false, action: 'approve', row,
        message: final ? `终审通过后将立即改写课表：原课位留痕 + 生成新课表项，并通知「${row.className || ''}」师生。确认？` : `通过后转教务处终审。确认通过「${row.courseName || ''}」的${row.changeTypeLabel}？` }
    },
    askReject(row) {
      this.confirm = { visible: true, title: '驳回调停课', type: 'danger', confirmText: '确认驳回', requireReason: true, action: 'reject', row,
        message: `驳回「${row.courseName || ''}」的${row.changeTypeLabel}申请（原因≥5 字）` }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        const res = action === 'approve'
          ? await scheduleChangeApi.approve(row.changeId, reason || '')
          : await scheduleChangeApi.reject(row.changeId, reason || '')
        if (res.code === 0) {
          toast.success(action === 'approve' ? (res.data.status === 'APPLIED' ? '已终审通过，课表已改写' : '已通过，转教务处') : '已驳回')
          this.confirm.visible = false; this.load()
        } else toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-slot { font-size: 12px; color: var(--t2, #475569); }
.sc-slot--to { color: var(--pri, #2563eb); font-weight: 600; }
.sc-arrow { margin: 0 6px; color: var(--t3, #94a3b8); }
.sc-stop { color: var(--warning, #d97706); font-weight: 600; font-size: 12px; }
.mp-link--danger { color: var(--danger, #dc2626); }
</style>
