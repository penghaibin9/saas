<template>
  <ModulePageShell
    title="调停课台账"
    subtitle="一条申请追踪审批、生效和通知；原课位改写后仍保留历史"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <template #actions>
      <div class="sc-actions">
        <AppButton v-if="canApply" variant="primary" @click="goApply">{{ isAcademicTeacher ? '从个人课表选择课程' : '＋ 发起调停课' }}</AppButton>
        <AppButton v-if="isAcademicTeacher && !selectedId" @click="toggleHistory">{{ showHistory ? '返回当前学期' : '历史记录' }}</AppButton>
        <AppButton v-if="canReview" @click="goApproval">审批工作台</AppButton>
      </div>
    </template>

    <ErrorState v-if="routeError || detailError" :description="routeError || detailError" @retry="syncRoute" />
    <ScheduleChangeEvidence v-else-if="selectedId" :key="detailKey" :change-id="selectedId" :ctx="ctx" @loaded="checkDetailTerm" @close="closeDetail" @notice="goNotice" />
    <div v-else class="mp-stack">
      <section class="sc-ledger-head"><div><h2>调停课申请 · 台账</h2><p>申请课程、原课位、目标课位、影响周次和办理状态保持同一行核对。</p></div><span>共 {{ loading || error ? '待核对' : total }} 条 · 正式服务端分页</span></section>
      <div v-if="isAcademicTeacher && !showHistory" class="sc-term-current">当前学期：<strong>{{ currentTermName || currentTermId || '待确认' }}</strong></div>
      <label v-else class="sc-term">学期<AppTermEntityPicker :model-value="filters.termId" placeholder="全部学期" @update:model-value="selectTerm" /></label>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无调停课单" :description="canApply ? '点右上「＋ 发起调停课」创建' : '当前范围暂无调停课申请，可稍后刷新查看。'" />
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
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
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
      currentTermId: '', currentTermName: '', showHistory: false,
      loadSeq: 0, actionSeq: 0, termSeq: 0, disposed: false, detailError: '',
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
    selectedId() { return typeof this.$route.query.changeId === 'string' && /^[1-9]\d*$/.test(this.$route.query.changeId) ? this.$route.query.changeId : '' },
    routeTermId() { return typeof this.$route.query.termId === 'string' && /^[1-9]\d*$/.test(this.$route.query.termId) ? this.$route.query.termId : '' },
    routeError() { return ['termId', 'changeId'].some(key => this.$route.query[key] != null && (typeof this.$route.query[key] !== 'string' || !/^[1-9]\d*$/.test(this.$route.query[key]))) ? '学期或调停课申请参数无效，请返回原责任事项重新进入。' : '' },
    routeKey() { return JSON.stringify([this.$route.query.termId, this.$route.query.changeId, this.$route.query.history]) },
    detailKey() { return JSON.stringify([this.identityKey, this.routeKey]) },
    roleName() { return this.ctx?.currentRole?.roleName || '教务' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    isAcademicTeacher() { return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER' },
    canApply() { return matchPermission(this.ctx?.permissionPatterns || [], 'academicAffairs.scheduleChange.apply') },
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
    routeKey() { this.syncRoute() },
    identityKey() {
      this.loadSeq++; this.actionSeq++; this.termSeq++
      this.confirm.visible = false; this.submitting = false; this.rows = []; this.total = 0
      this.currentTermId = ''; this.currentTermName = ''; this.showHistory = false
      this.filters = EMPTY(); this.syncRoute()
    }
  },
  created() { this.syncRoute() },
  beforeUnmount() { this.loadSeq++; this.actionSeq++; this.termSeq++; this.disposed = true },
  methods: {
    syncRoute() {
      this.loadSeq++; this.termSeq++; this.actionSeq++; this.confirm.visible = false; this.submitting = false
      this.rows = []; this.total = 0; this.detailError = ''; this.page = 1
      this.filters.termId = this.routeTermId
      this.showHistory = Boolean(this.routeTermId) || this.$route.query.history === '1'
      return this.load()
    },
    checkDetailTerm(detail) {
      if (!detail || this.routeError || String(detail.changeId || '') !== this.selectedId) return
      if (this.routeTermId && String(detail.termId || '') !== this.routeTermId) this.detailError = '申请所属学期与来源责任事项不一致，请返回原事项重新核对。'
    },
    selectTerm(value) {
      const termId = value == null ? '' : String(value)
      if (termId && !/^[1-9]\d*$/.test(termId)) return
      return this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: termId || undefined, history: this.isAcademicTeacher && !termId ? '1' : undefined } })
    },
    typeTone(t) { return { ADJUST: 'processing', STOP: 'warning', MAKEUP: 'info' }[t] || 'default' },
    statusLabel(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).label || (s ? '状态待确认' : '—') },
    statusTone(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).tone || 'default' },
    cancellable(row) { return this.canApply && row?.canCancel === true && ['SUBMITTED', 'COLLEGE_REVIEW'].includes(row.status) },
    async initializeTeacherTerm() {
      if (!this.isAcademicTeacher || this.showHistory || this.selectedId || this.routeTermId) return true
      if (this.currentTermId) { this.filters.termId = this.currentTermId; return true }
      const seq = ++this.termSeq, identity = this.identityKey, route = this.routeKey
      const current = () => !this.disposed && seq === this.termSeq && identity === this.identityKey && route === this.routeKey
      try {
        const res = await academicAffairsApi.getCurrentTerm()
        if (!current()) return false
        if (res?.code === 0 && res.data?.termId) {
          this.currentTermId = String(res.data.termId)
          this.currentTermName = res.data.termName || res.data.name || res.data.termCode || this.currentTermId
          this.filters.termId = this.currentTermId
          return true
        } else {
          this.error = res?.message || '当前学期尚未设置'
        }
      } catch (error) {
        if (current()) this.error = error?.message || '当前学期读取失败'
      }
      return false
    },
    async toggleHistory() {
      if (!this.isAcademicTeacher || this.loading || this.selectedId) return
      return this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: undefined, history: this.showHistory ? undefined : '1' } })
    },
    async load() {
      const seq = ++this.loadSeq
      const identity = this.identityKey, route = this.routeKey
      let query = ''
      const current = () => !this.disposed && seq === this.loadSeq && identity === this.identityKey && route === this.routeKey && (!query || query === JSON.stringify([this.filters, this.page]))
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      try {
        if (this.routeError) { this.error = this.routeError; return }
        if (this.selectedId) return
        if (this.routeTermId) this.filters.termId = this.routeTermId
        if (this.isAcademicTeacher && !this.showHistory && !this.filters.termId && (!await this.initializeTeacherTerm() || !current())) return
        query = JSON.stringify([this.filters, this.page])
        const res = await scheduleChangeApi.list({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (!current()) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message || '台账加载失败'
      } catch (error) { if (current()) this.error = error?.message || '台账加载失败' }
      finally { if (current()) this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() {
      this.filters = { ...EMPTY(), termId: this.routeTermId }
      if (this.isAcademicTeacher && !this.showHistory && this.currentTermId) this.filters.termId = this.currentTermId
      this.page = 1
      this.load()
    },
    turnPage(p) { this.page = p; this.load() },
    goApply() { if (this.canApply) this.$router.push(this.isAcademicTeacher ? '/admin/academic-affairs/schedule/teacher' : '/admin/academic-affairs/schedule-change/apply') },
    goApproval() { this.$router.push('/admin/academic-affairs/schedule-change/approval') },
    goDetail(row) { this.$router.push({ path: this.$route.path, query: { ...this.$route.query, termId: this.filters.termId || undefined, changeId: String(row.changeId) } }) },
    closeDetail() { const query = { ...this.$route.query }; delete query.changeId; this.$router.replace({ path: this.$route.path, query }) },
    goNotice(row) { this.$router.push(`/admin/academic-affairs/print/schedule-change/${row.changeId}/notice`) },
    askCancel(row) {
      if (this.submitting || !this.cancellable(row)) return
      this.confirm = { visible: true, title: '撤销调停课', message: `确认撤销「${row.courseName || ''}」的${row.changeTypeLabel}申请？`, type: 'danger', confirmText: '确认撤销', requireReason: true, row: { ...row }, identity: this.identityKey, route: this.routeKey }
    },
    async onConfirm({ reason } = {}) {
      if (this.submitting || !this.confirm.visible || !this.confirm.row || this.confirm.identity !== this.identityKey || this.confirm.route !== this.routeKey) return
      if (!this.cancellable(this.confirm.row)) { this.confirm.visible = false; return }
      const row = { ...this.confirm.row }
      const identity = this.identityKey
      const seq = ++this.actionSeq
      const route = this.routeKey
      const current = () => !this.disposed && seq === this.actionSeq && identity === this.identityKey && route === this.routeKey
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
.sc-term-current { width:max-content; max-width:100%; padding:8px 12px; border-radius:8px; background:var(--pri-bg,#eef5ff); color:var(--t2,#52647a); font-size:12px; }
.sc-ledger-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 15px 18px; border: 1px solid var(--line, #e2e8f0); border-radius: 12px; background: var(--bg-card, #fff); }.sc-ledger-head h2 { margin: 0; font-size: 16px; }.sc-ledger-head p { margin: 5px 0 0; color: var(--t2, #52647a); font-size: 12px; }.sc-ledger-head > span { color: var(--t2, #52647a); font-size: 12px; white-space: nowrap; }
.sc-slot { font-size: 12px; color: var(--t2, #475569); }
.sc-slot--to { color: var(--pri, #2563eb); font-weight: 600; }
.sc-arrow { margin: 0 6px; color: var(--t3, #94a3b8); }
.sc-stop { color: var(--warning, #d97706); font-weight: 600; font-size: 12px; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-link--danger { color: var(--danger, #dc2626); }
</style>
