<template>
  <ModulePageShell
    title="调停课审批"
    subtitle="学院审 → 教务处审；终审通过后系统自动改写课表（原课位留痕 + 生成新项）并通知师生"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <div class="mp-stack">
      <section v-if="receipt" class="sc-receipt" role="status">
        <div><strong>✓ {{ receipt.title }}</strong><span>{{ receipt.courseName }} · 单据 {{ receipt.changeId }}</span></div>
        <div><small>当前结果</small><b>{{ statusLabel(receipt.status) }}</b></div>
        <div><small>下一步</small><b>{{ receipt.next }}</b></div>
        <AppButton size="small" variant="ghost" @click="goReceipt">查看单据与通知</AppButton>
      </section>
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
      phrase-scene-key="aa.schedchg.reject"
      reason-label="驳回原因（≥5 字）" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 调停课审批工作台（/admin/academic-affairs/schedule-change/approval）：学院/教务处两级审批。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppButton } from '@/components/ui'
import { scheduleChangeApi, CHANGE_TYPES, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { toast } from '@/utils/toast'

const PENDING = ['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW']
const EMPTY = () => ({ changeType: '', status: '' })

export default {
  name: 'AaScheduleChangeApprovalView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppButton },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY(),
      receipt: null,
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
          ? await scheduleChangeApi.approve(row.changeId, row.version, reason || '')
          : await scheduleChangeApi.reject(row.changeId, row.version, reason || '')
        if (res.code === 0) {
          const status = res.data.status
          this.receipt = {
            changeId: row.changeId,
            courseName: row.courseName || '课程',
            status,
            title: action === 'approve' ? (status === 'APPLIED' ? '终审完成，课表已生效' : '学院审核已通过') : '调停课申请已驳回',
            next: status === 'APPLIED'
              ? `已通知 ${Number(res.data.notified?.students || 0)} 名学生和任课教师；新课位进入考勤`
              : (status === 'REJECTED' ? '任课教师查看原因后重新发起' : '教务处终审')
          }
          toast.success(action === 'approve' ? (res.data.status === 'APPLIED' ? '已终审通过，课表已改写' : '已通过，转教务处') : '已驳回')
          this.confirm.visible = false
          await this.load()
        } else {
          const code = String(res.code || '')
          if (code === '409' || code.includes('APPROVAL_VERSION_CONFLICT')) {
            toast.error('该单据已被其他操作更新，已刷新最新状态')
            this.confirm.visible = false
            await this.load()
          } else toast.error(res.message)
        }
      } finally { this.submitting = false }
    },
    goReceipt() {
      if (!this.receipt?.changeId) return
      this.$router.push(`/admin/academic-affairs/print/schedule-change/${this.receipt.changeId}/notice`)
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
.sc-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(180px,auto) auto; align-items: center; gap: 18px; padding: 13px 15px; border: 1px solid #a7d7b4; border-radius: 11px; background: #f3fbf5; }
.sc-receipt strong, .sc-receipt span, .sc-receipt small, .sc-receipt b { display: block; }.sc-receipt strong { color: #15803d; }.sc-receipt span, .sc-receipt small { margin-top: 3px; color: #64748b; font-size: 11px; }.sc-receipt b { margin-top: 3px; font-size: 12px; }
@media (max-width: 760px) { .sc-receipt { grid-template-columns: 1fr; gap: 10px; } }
</style>
