<template>
  <ModulePageShell
    title="调停课审批"
    subtitle="学院审 → 教务处审；终审通过后系统自动改写课表（原课位留痕 + 生成新项）并通知师生"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <div class="mp-stack">
      <p v-if="reviewNotice" class="sc-review-notice" role="alert">{{ reviewNotice }}<span v-if="reviewDraft?.reason"> 保留意见：{{ reviewDraft.reason }}</span></p>
      <section v-if="receipt" class="sc-receipt" role="status">
        <div><strong>✓ {{ receipt.title }}</strong><span>{{ receipt.courseName }} · 单据 {{ receipt.changeId }}</span></div>
        <div><small>当前结果</small><b>{{ statusLabel(receipt.status) }}</b></div>
        <div><small>下一步</small><b>{{ receipt.next }}</b></div>
        <AppButton size="small" variant="ghost" @click="goReceipt">查看单据与通知</AppButton>
      </section>
      <div v-if="selectedId" class="sc-review-layout">
        <aside class="sc-review-queue" aria-label="本页待审队列">
          <h2>待审申请</h2>
          <button v-for="row in rows" :key="row.changeId" :class="{ 'is-current': String(row.changeId) === selectedId }" @click="openEvidence(row)">
            <strong>{{ row.courseName || '课程未提供' }}</strong><span>{{ row.className || '班级未提供' }} · {{ statusLabel(row.status) }}</span>
          </button>
        </aside>
        <div class="sc-review-object">
          <ScheduleChangeEvidence :key="`${selectedId}:${evidenceRevision}`" :change-id="selectedId" :ctx="ctx" @close="closeEvidence" @notice="goNotice" @loaded="evidence = $event" @read-denied="revokeRead" />
          <section v-if="evidence && canReview(evidence)" class="sc-review-action">
            <strong>办理当前申请 · {{ evidence.changeId }}</strong>
            <AppButton :disabled="submitting" @click="askReject(evidence)">驳回</AppButton>
            <AppButton variant="primary" :disabled="submitting" @click="askApprove(evidence)">审核通过</AppButton>
          </section>
        </div>
      </div>
      <template v-else>
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <p class="sc-stage-note">待审状态由服务端合并筛选后分页，也可按审核节点单独查看。</p>
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
          <button class="mp-link" @click="openEvidence(row)">查看证据与办理</button>
        </template>
      </DataTable>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText"
      phrase-scene-key="aa.schedchg.reject"
      reason-label="驳回原因（≥5 字）" :submitting="submitting" @confirm="onConfirm"
    >
      <template v-if="confirm.requireReason"><AppQuickPhrases scene-key="aa.schedchg.reject" @pick="reviewReason += $event" /><label>驳回原因（≥5 字）<textarea v-model.trim="reviewReason" rows="3" class="sc-review-reason" :disabled="submitting" /></label></template>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 调停课审批工作台（/admin/academic-affairs/schedule-change/approval）：学院/教务处两级审批。 */
import { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import AppQuickPhrases from '@/components/common/AppQuickPhrases.vue'
import { AppButton } from '@/components/ui'
import { scheduleChangeApi, CHANGE_TYPES, CHANGE_STATUS } from '@/modules/academicAffairs/api/academic-schedule-change.api'
import { toast } from '@/utils/toast'
import ScheduleChangeEvidence from '../components/parallel-b/ScheduleChangeEvidence.vue'
import { currentUserFromToken } from '@/services/http/client'

const PENDING = ['SUBMITTED', 'COLLEGE_REVIEW', 'ACADEMIC_REVIEW']
const ALL_PENDING = PENDING.join(',')
const EMPTY = () => ({ changeType: '', status: ALL_PENDING })

export default {
  name: 'AaScheduleChangeApprovalView',
  components: { ModulePageShell, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppQuickPhrases, AppButton, ScheduleChangeEvidence },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY(),
      receipt: null,
      evidence: null, loadSeq: 0, actionSeq: 0, evidenceRevision: 0,
      reviewNotice: '', reviewReason: '', reviewDraft: null, blockedReviews: [],
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
    selectedId() { return String(this.$route.query.changeId || '') },
    identityKey() { return JSON.stringify([currentUserFromToken(), this.ctx]) },
    roleName() { return this.ctx?.currentRole?.roleName || '学院/教务处' },
    scopeName() { return this.ctx?.dataScope?.scopeName || '按授权范围' },
    filterFields() {
      return [
        { key: 'changeType', label: '类型', type: 'select', options: CHANGE_TYPES.map((t) => ({ value: t.value, label: t.label })) },
        { key: 'status', label: '节点', type: 'select', options: [{ value: ALL_PENDING, label: '全部待审' }, ...CHANGE_STATUS.filter((s) => PENDING.includes(s.value)).map((s) => ({ value: s.value, label: s.label }))] }
      ]
    }
  },
  watch: {
    selectedId() { this.actionSeq++; this.confirm.visible = false; this.confirm.row = null; this.evidence = null; this.submitting = false; this.reviewReason = '' },
    identityKey() {
      this.loadSeq++; this.actionSeq++
      this.confirm.visible = false; this.receipt = null; this.evidence = null; this.closeEvidence()
      this.rows = []; this.total = 0; this.submitting = false
      this.reviewDraft = null; this.reviewReason = ''; this.reviewNotice = ''; this.blockedReviews = []; this.evidenceRevision++
      this.load()
    }
  },
  created() { this.load() },
  beforeUnmount() { this.loadSeq++; this.actionSeq++ },
  methods: {
    canReview(row) { return this.isPending(row.status) && !this.blockedReviews.some(item => item.id === String(row.changeId) && item.version === row.version) },
    revokeRead() {
      this.loadSeq++; this.actionSeq++; this.evidenceRevision++
      this.rows = []; this.total = 0; this.receipt = null; this.reviewDraft = null; this.reviewReason = ''
      this.confirm.visible = false; this.confirm.row = null; this.submitting = false; this.loading = false
      this.error = '读取权限已变化，请重新核对当前身份与授权'
      this.closeEvidence()
    },
    invalidateReview(row, reason, message) {
      this.blockedReviews.push({ id: String(row.changeId), version: row.version })
      this.reviewDraft = { changeId: String(row.changeId), action: this.confirm.action, reason, identity: this.identityKey }
      this.reviewNotice = message
      this.confirm.visible = false; this.confirm.row = null; this.evidence = null; this.evidenceRevision++
    },
    isPending(status) { return PENDING.includes(status) },
    openEvidence(row) { this.evidence = null; this.$router.push({ query: { ...this.$route.query, changeId: String(row.changeId) } }) },
    closeEvidence() { this.evidence = null; const query = { ...this.$route.query }; delete query.changeId; this.$router.replace({ query }) },
    typeTone(t) { return { ADJUST: 'processing', STOP: 'warning', MAKEUP: 'info' }[t] || 'default' },
    statusLabel(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).label || (s ? '状态待确认' : '—') },
    statusTone(s) { return (CHANGE_STATUS.find((x) => x.value === s) || {}).tone || 'default' },
    async load() {
      const seq = ++this.loadSeq
      const identity = this.identityKey
      if (![ALL_PENDING, ...PENDING].includes(this.filters.status)) this.filters.status = ALL_PENDING
      const query = JSON.stringify([this.filters, this.page])
      const current = () => seq === this.loadSeq && identity === this.identityKey && query === JSON.stringify([this.filters, this.page])
      this.loading = true; this.error = ''
      try {
      const res = await scheduleChangeApi.list({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (!current()) return
      if (res.code === 0) {
        this.rows = res.data.list
        this.total = res.data.total
      } else if (Number(res.code) === 403 || Math.floor(Number(res.code) / 1000) === 403) this.revokeRead()
      else this.error = res.message
      } catch (error) { if (current()) this.error = error?.message || '待审申请加载失败' }
      finally { if (current()) this.loading = false }
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    askApprove(row) {
      if (this.submitting || !this.canReview(row)) return
      this.reviewReason = ''
      const final = row.status === 'COLLEGE_REVIEW' || row.status === 'ACADEMIC_REVIEW'
      this.confirm = { visible: true, title: '审批通过', type: 'primary', confirmText: '确认通过', requireReason: false, action: 'approve', row: { ...row }, identity: this.identityKey,
        message: final
          ? (row.changeType === 'STOP'
              ? `确认对「${row.courseName || ''}」的申请 ${row.changeId} 终审通过？将登记停课、更新正式课表并生成师生通知。`
              : `终审通过后将立即改写课表：原课位留痕 + 生成新课表项，并通知「${row.className || ''}」师生。确认？`)
          : `通过后转教务处终审。确认通过「${row.courseName || ''}」的${row.changeTypeLabel}？` }
    },
    askReject(row) {
      if (this.submitting || !this.canReview(row)) return
      this.reviewReason = this.reviewDraft?.changeId === String(row.changeId) && this.reviewDraft?.identity === this.identityKey ? this.reviewDraft.reason : ''
      this.confirm = { visible: true, title: '驳回调停课', type: 'danger', confirmText: '确认驳回', requireReason: true, action: 'reject', row: { ...row }, identity: this.identityKey,
        message: `驳回「${row.courseName || ''}」的${row.changeTypeLabel}申请（原因≥5 字）` }
    },
    async onConfirm({ reason } = {}) {
      if (this.submitting || !this.confirm.visible || !this.confirm.row || this.confirm.identity !== this.identityKey) return
      const { action, row } = this.confirm
      if (this.selectedId && this.selectedId !== String(row.changeId)) return
      reason = reason ?? this.reviewReason
      if (action === 'reject' && String(reason || '').trim().length < 5) { toast.error('驳回原因不少于 5 字'); return }
      const identity = this.identityKey
      const seq = ++this.actionSeq
      const current = () => seq === this.actionSeq && identity === this.identityKey
      this.submitting = true
      try {
        const res = action === 'approve'
          ? await scheduleChangeApi.approve(row.changeId, row.version, reason || '')
          : await scheduleChangeApi.reject(row.changeId, row.version, reason || '')
        if (!current()) return
        if (res.code === 0) {
          const status = res.data.status
          this.receipt = {
            changeId: row.changeId,
            courseName: row.courseName || '课程',
            status,
            title: action === 'approve' ? (status === 'APPLIED' ? '终审完成，课表已生效' : '学院审核已通过') : '调停课申请已驳回',
            next: status === 'APPLIED'
              ? (row.changeType === 'STOP' ? '停课已生效，请核对正式课表及通知回执' : res.data.applied?.notified?.students != null
                ? `通知记录：${Number(res.data.applied?.notified?.students)} 名学生；新课位进入考勤，送达情况请核对通知回执`
                : '新课位进入考勤；接口未提供通知人数，请核对通知回执')
              : (status === 'REJECTED' ? '任课教师查看原因后重新发起' : '教务处终审')
          }
          toast.success(action === 'approve' ? (res.data.status === 'APPLIED' ? '已终审通过，课表已改写' : '已通过，转教务处') : '已驳回')
          this.confirm.visible = false
          this.closeEvidence()
          await this.load()
        } else {
          const code = Number(res.code), family = code < 1000 ? code : Math.floor(code / 1000)
          if (family === 409 || family === 403) {
            this.invalidateReview(row, reason || '', family === 409
              ? '单据版本已变化，旧确认已作废。正在重新读取，请核对最新证据后重新办理。'
              : '本次办理权限校验未通过，旧确认已作废。正在重新核对可读资料，请联系当前节点受理人。')
            await this.load()
          } else if (family >= 500 || !Number.isFinite(code)) {
            this.invalidateReview(row, reason || '', '审批结果未确认，已暂停当前版本的重复办理，请核对正式单据。')
          } else toast.error(res.message)
        }
      } catch { if (current()) this.invalidateReview(row, reason || '', '审批结果未确认，旧确认已作废，请核对正式单据。') }
      finally { if (current()) this.submitting = false }
    },
    goReceipt() {
      if (!this.receipt?.changeId) return
      this.$router.push(this.receipt.status === 'APPLIED'
        ? `/admin/academic-affairs/print/schedule-change/${this.receipt.changeId}/notice`
        : `/admin/academic-affairs/schedule-change?changeId=${encodeURIComponent(this.receipt.changeId)}`)
    },
    goNotice(row) { this.$router.push(`/admin/academic-affairs/print/schedule-change/${row.changeId}/notice`) }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.sc-slot { font-size: 12px; color: var(--t2, #475569); }
.sc-slot--to { color: var(--pri, #2563eb); font-weight: 600; }
.sc-arrow { margin: 0 6px; color: var(--t3, #94a3b8); }
.sc-stop { color: var(--warning, #d97706); font-weight: 600; font-size: 12px; }
.sc-stage-note { margin: 0; color: var(--t2, #52647a); font-size: 12px; }
.sc-review-notice { padding: 12px; background: #fffbeb; border: 1px solid #e7b95d; border-radius: 8px; }
.sc-review-reason { display: block; width: 100%; margin-top: 8px; }
.sc-review-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 16px; align-items: start; }
.sc-review-queue { border: 1px solid var(--line, #dce4ee); border-radius: 12px; overflow: hidden; background: var(--bg-card, #fff); }
.sc-review-queue h2 { margin: 0; padding: 16px; font-size: 15px; }
.sc-review-queue button { width: 100%; display: grid; gap: 6px; text-align: left; border: 0; border-top: 1px solid var(--line, #dce4ee); padding: 16px; background: transparent; color: inherit; cursor: pointer; }
.sc-review-queue button span { font-size: 12px; color: var(--t2, #52647a); }
.sc-review-queue .is-current { background: var(--fill-2, #e8effb); border-left: 3px solid var(--pri, #2b5bb4); }
.sc-review-object { min-width: 0; display: grid; gap: 16px; }
.sc-review-action { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 12px; padding: 16px; border: 1px solid var(--line, #dce4ee); border-radius: 12px; background: var(--bg-card, #fff); }
.sc-review-action strong { margin-right: auto; font-size: 14px; }
@media (max-width: 1000px) { .sc-review-layout { grid-template-columns: 1fr; } }
.mp-link--danger { color: var(--danger, #dc2626); }
.sc-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(180px,auto) auto; align-items: center; gap: 18px; padding: 13px 15px; border: 1px solid #a7d7b4; border-radius: 11px; background: #f3fbf5; }
.sc-receipt strong, .sc-receipt span, .sc-receipt small, .sc-receipt b { display: block; }.sc-receipt strong { color: #15803d; }.sc-receipt span, .sc-receipt small { margin-top: 3px; color: #64748b; font-size: 11px; }.sc-receipt b { margin-top: 3px; font-size: 12px; }
@media (max-width: 760px) { .sc-receipt { grid-template-columns: 1fr; gap: 10px; } }
</style>
