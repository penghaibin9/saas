<template>
  <ModulePageShell
    title="调停课台账"
    subtitle="一条申请追踪审批、生效和通知；原课位改写后仍保留历史"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <template #actions>
      <div class="sc-actions">
        <AppButton variant="primary" @click="goApply">{{ isAcademicTeacher ? '从个人课表选择课程' : '＋ 发起调停课' }}</AppButton>
        <AppButton v-if="canReview" @click="goApproval">审批工作台</AppButton>
      </div>
    </template>

    <ScheduleChangeEvidence v-if="selectedId" :change-id="selectedId" :ctx="ctx" @close="closeDetail" @notice="goNotice" />
    <div v-else class="mp-stack">
      <section class="sc-ledger-head"><div><h2>调停课申请 · 台账</h2><p>申请课程、原课位、目标课位、影响周次和办理状态保持同一行核对。</p></div><span>共 {{ total }} 条 · 正式服务端分页</span></section>
      <label class="sc-term">学期<AppTermEntityPicker v-model="filters.termId" placeholder="全部学期" /></label>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无调停课单" description="点右上「＋ 发起调停课」创建" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="changeId"
                 :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-course="{ row }">
          <div class="mp-cell-main">{{ row.courseName || '—' }}</div>
          <div class="mp-cell-sub">{{ row.className || '—' }} · {{ row.teacherName || '—' }}</div>
        </template>
        <template #cell-type="{ row }"><StatusTag :type="typeTone(row.changeType)" :label="row.changeTypeLabel" dot /></template>
        <template #cell-move="{ row }">
          <span class="sc-slot">周{{ row.origin.weekday }}·{{ row.origin.slotNo }}节 {{ row.origin.classroom }}</span>
          <template v-if="row.changeType !== 'STOP'">
            <span class="sc-arrow">→</span>
            <span class="sc-slot sc-slot--to">周{{ row.target.weekday }}·{{ row.target.slotNo }}节 {{ row.target.classroom }}</span>
          </template>
          <span v-else class="sc-stop">停课</span>
        </template>
        <template #cell-status="{ row }"><StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot /></template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="goDetail(row)">详情</button>
          <button v-if="row.status === 'APPLIED'" class="mp-link" style="margin-left: var(--space-2)" @click="goNotice(row)">通知单</button>
          <button v-if="cancellable(row)" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askCancel(row)">撤销</button>
        </template>
      </DataTable>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      phrase-scene-key="aa.schedchg.cancel"
      reason-label="撤销原因" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 调停课台账（/admin/academic-affairs/schedule-change）：范围过滤 + 统计 + 撤销 + 通知单入口。生产级只走真实后端。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTermEntityPicker } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { scheduleChangeApi, CHANGE_TYPES, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { toast } from '@/utils/toast'
import ScheduleChangeEvidence from '../components/parallel-b/ScheduleChangeEvidence.vue'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'

const EMPTY = () => ({ changeType: '', status: '', termId: '' })

export default {
  name: 'AaScheduleChangeLedgerView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppConfirmDialog, ScheduleChangeEvidence, AppTermEntityPicker },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY(),
      loadSeq: 0, actionSeq: 0,
      confirm: { visible: false, title: '', message: '', type: 'danger', confirmText: '确认', requireReason: true, row: null },
      columns: [
        { key: 'course', title: '课程 / 班级·教师' },
        { key: 'type', title: '类型' },
        { key: 'move', title: '原课位 → 目标' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    }
  },
  computed: {
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    selectedId() { return String(this.$route.query.changeId || '') },
    roleName() { return this.ctx?.currentRole?.roleName || '教务' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    isAcademicTeacher() { return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER' },
    canReview() {
      const patterns = this.ctx?.permissionPatterns || []
      return matchPermission(patterns, 'academicAffairs.scheduleChange.collegeReview') ||
        matchPermission(patterns, 'academicAffairs.scheduleChange.academicReview')
    },
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: CHANGE_TYPES.map((t) => ({ value: t.value, label: t.label })) },
        { key: 'status', label: '状态', type: 'select', options: CHANGE_STATUS.map((s) => ({ value: s.value, label: s.label })) }
      ]
    }
  },
  watch: {
    identityKey() {
      this.loadSeq++; this.actionSeq++
      this.confirm.visible = false; this.submitting = false; this.rows = []; this.total = 0
      this.closeDetail(); this.load()
    }
  },
  created() { this.load() },
  beforeUnmount() { this.loadSeq++; this.actionSeq++ },
  methods: {
    typeTone(t) { return { ADJUST: 'processing', STOP: 'warning', MAKEUP: 'info' }[t] || 'default' },
    statusLabel(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).label || (s ? '状态待确认' : '—') },
    statusTone(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).tone || 'default' },
    cancellable(row) { return ['SUBMITTED', 'COLLEGE_REVIEW'].includes(row.status) },
    async load() {
      const seq = ++this.loadSeq
      const identity = this.identityKey
      const query = JSON.stringify([this.filters, this.page])
      const current = () => seq === this.loadSeq && identity === this.identityKey && query === JSON.stringify([this.filters, this.page])
      this.loading = true; this.error = ''
      try {
        const res = await scheduleChangeApi.list({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (!current()) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message || '台账加载失败'
      } catch (error) { if (current()) this.error = error?.message || '台账加载失败' }
      finally { if (current()) this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    goApply() { this.$router.push(this.isAcademicTeacher ? '/admin/academic-affairs/schedule/teacher' : '/admin/academic-affairs/schedule-change/apply') },
    goApproval() { this.$router.push('/admin/academic-affairs/schedule-change/approval') },
    goDetail(row) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, changeId: row.changeId } }) },
    closeDetail() { const query = { ...this.$route.query }; delete query.changeId; this.$router.replace({ path: this.$route.path, query }) },
    goNotice(row) { this.$router.push(`/admin/academic-affairs/print/schedule-change/${row.changeId}/notice`) },
    askCancel(row) {
      if (this.submitting || !this.cancellable(row)) return
      this.confirm = { visible: true, title: '撤销调停课', message: `确认撤销「${row.courseName || ''}」的${row.changeTypeLabel}申请？`, type: 'danger', confirmText: '确认撤销', requireReason: true, row: { ...row }, identity: this.identityKey }
    },
    async onConfirm({ reason } = {}) {
      if (this.submitting || !this.confirm.visible || !this.confirm.row || this.confirm.identity !== this.identityKey) return
      const row = { ...this.confirm.row }
      const identity = this.identityKey
      const seq = ++this.actionSeq
      const current = () => seq === this.actionSeq && identity === this.identityKey
      this.submitting = true
      try {
        const res = await scheduleChangeApi.cancel(row.changeId, reason || '')
        if (!current()) return
        if (res.code === 0) { toast.success('已撤销'); this.confirm.visible = false; this.load() } else toast.error(res.message)
      } catch (error) { if (current()) toast.error(error?.message || '撤销结果未确认，请刷新单据核对') }
      finally { if (current()) this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-actions { display: flex; gap: var(--space-2); }
.sc-term { display: grid; gap: 6px; width: 240px; max-width: 100%; font-size: 13px; }
.sc-ledger-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 15px 18px; border: 1px solid var(--line, #e2e8f0); border-radius: 12px; background: var(--bg-card, #fff); }.sc-ledger-head h2 { margin: 0; font-size: 16px; }.sc-ledger-head p { margin: 5px 0 0; color: var(--t2, #52647a); font-size: 12px; }.sc-ledger-head > span { color: var(--t2, #52647a); font-size: 12px; white-space: nowrap; }
.sc-slot { font-size: 12px; color: var(--t2, #475569); }
.sc-slot--to { color: var(--pri, #2563eb); font-weight: 600; }
.sc-arrow { margin: 0 6px; color: var(--t3, #94a3b8); }
.sc-stop { color: var(--warning, #d97706); font-weight: 600; font-size: 12px; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-link--danger { color: var(--danger, #dc2626); }
</style>
