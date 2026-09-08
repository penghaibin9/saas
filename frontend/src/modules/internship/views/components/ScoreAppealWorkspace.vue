<template>
  <section class="appeal-workspace" aria-label="成绩申诉办理">
    <header class="appeal-workspace__header">
      <div><h2>成绩申诉办理</h2><p v-if="record">{{ record.studentName }} · {{ record.studentNo || '未登记学号' }}</p></div>
      <AppButton variant="ghost" :disabled="submitting" @click="$emit('back')">返回申诉列表</AppButton>
    </header>
    <ActionReceipt :receipt="receipt" @close="receipt = null" />
    <div v-if="loading" class="appeal-workspace__state" role="status">正在读取申诉与成绩…</div>
    <div v-else-if="error" class="appeal-workspace__state is-error" role="alert">{{ error }} <AppButton variant="ghost" @click="load()">重试</AppButton></div>
    <div v-if="conflict" class="appeal-workspace__notice" role="alert"><p>申诉或原成绩已变化，意见已保留。请先核对最新状态。</p><AppButton v-if="record?.status === 'PENDING'" variant="secondary" :disabled="loading || !!error" @click="acknowledgeLatest">已核对，继续编辑意见</AppButton></div>
    <p v-if="error && reason" class="appeal-workspace__kept">未提交意见：{{ reason }}</p>
    <template v-if="!loading && !error && record">
      <div class="appeal-workspace__meta"><AppStatusTag :status="record.status">{{ record.statusLabel }}</AppStatusTag><span>提交于 {{ record.createdAt || '—' }}</span><span v-if="record.handler">处理人 {{ record.handler }}</span></div>
      <section class="appeal-workspace__section"><h3>学生申诉理由</h3><p class="appeal-workspace__reason">{{ record.reason || '未填写' }}</p></section>
      <div class="appeal-workspace__comparison">
        <section><h3>申诉时冻结成绩</h3><p class="appeal-workspace__score">{{ record.scoreSnapshot?.totalScore ?? '—' }}<small>分</small></p><p>成绩版本 {{ record.scoreSnapshot?.scoreVersion ?? '—' }}</p><p>发布于 {{ record.scoreSnapshot?.publishedAt || '—' }}</p></section>
        <section><h3>当前成绩</h3><p class="appeal-workspace__score">{{ record.currentScore?.totalScore ?? '—' }}<small>分</small></p><p>{{ scoreStatusLabel }} · 版本 {{ record.currentScore?.version ?? '—' }}</p><p>发布于 {{ record.currentScore?.publishedAt || '—' }}</p></section>
      </div>
      <AppButton v-if="record.currentScore?.id" variant="secondary" :disabled="submitting" @click="$emit('score', record)">核对关联成绩</AppButton>
      <p v-if="record.status === 'APPROVED_RECALCULATING'" class="appeal-workspace__notice">原成绩已撤回，等待重新核算、独立复核并发布。</p>
      <p v-else-if="record.status === 'CLOSED'" class="appeal-workspace__notice">申诉后成绩已重新发布，学生可查看新的正式成绩。</p>
      <p v-else-if="record.status === 'REJECTED'" class="appeal-workspace__notice">本次申诉已驳回，处理意见见下方记录。</p>

      <section v-if="record.status === 'PENDING' && !completed" class="appeal-workspace__section">
        <h3>处理申诉</h3>
        <p v-if="!canManage" class="appeal-workspace__notice">当前账号无成绩申诉办理权限。</p>
        <p v-else-if="!canApprove" class="appeal-workspace__notice">原成绩状态或版本已变化，暂不可受理撤回。请核对当前成绩；仍可按实际情况填写驳回意见。</p>
        <fieldset class="appeal-workspace__form" :disabled="!canManage || submitting || confirmVisible || conflict">
          <legend>处理结论</legend>
          <div class="appeal-workspace__choices">
            <label :class="{ selected: decision === 'approve' }"><input v-model="decision" type="radio" value="approve" :disabled="!canApprove" />受理并撤回原成绩</label>
            <label :class="{ selected: decision === 'reject' }"><input v-model="decision" type="radio" value="reject" />驳回申诉</label>
          </div>
          <label for="appeal-decision-reason">{{ decision === 'approve' ? '受理意见' : decision === 'reject' ? '驳回原因' : '处理意见' }} <span aria-hidden="true">*</span></label>
          <textarea id="appeal-decision-reason" v-model="reason" rows="4" placeholder="至少填写 5 字，说明处理依据及学生需要了解的结果" :aria-invalid="!!submitError" />
        </fieldset>
        <p v-if="submitError" class="is-error" role="alert">{{ submitError }}</p>
        <div class="appeal-workspace__footer"><span>受理后仍需完成核算、独立复核与发布。</span><AppButton variant="primary" :disabled="!canSubmit" @click="openConfirmation">{{ decision === 'approve' ? '受理并撤回原成绩' : decision === 'reject' ? '驳回申诉' : '提交处理结果' }}</AppButton></div>
      </section>
      <section v-if="auditRecords.length" class="appeal-workspace__section"><h3>处理记录</h3><AppAuditTrail :records="auditRecords" :show-ip="false" compact /></section>
      <p v-if="reason && (record.status !== 'PENDING' || completed)" class="appeal-workspace__kept">本次填写意见：{{ reason }}</p>
    </template>

    <AppConfirmDialog v-model:visible="confirmVisible" title="确认处理成绩申诉" :content="confirmMessage" :confirm-text="pending?.decision === 'approve' ? '确认受理并撤回' : '确认驳回'" :danger="true" :submitting="submitting" :confirm-disabled="conflict || !pending" @confirm="submit" @cancel="pending = null">
      <p class="appeal-workspace__reason">{{ pending?.reason }}</p><p v-if="submitError" class="is-error" role="alert">{{ submitError }}</p>
    </AppConfirmDialog>
  </section>
</template>

<script>
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppAuditTrail, AppConfirmDialog } from '@/components/common'
import ActionReceipt from './ActionReceipt.vue'
import { scoreApi } from '@/modules/internship/api/score.api'
import { canCode } from '@/modules/internship/composables/permission'
import { isConflict } from '@/modules/internship/composables/conflictGuard'

const SCORE_STATUS = { PENDING_CALC: '待核算', PENDING_REVIEW: '待复核', PENDING_PUBLISH: '待发布', PUBLISHED: '已发布', WITHDRAWN: '已撤回', ARCHIVED: '已归档' }
export default {
  name: 'ScoreAppealWorkspace',
  components: { AppButton, AppStatusTag, AppAuditTrail, AppConfirmDialog, ActionReceipt },
  props: { appealId: { type: String, required: true }, batchId: { type: String, required: true }, ctx: { type: Object, default: () => ({}) } },
  emits: ['back', 'handled', 'score'],
  data() { return { record: null, loading: false, error: '', sequence: 0, decision: '', reason: '', submitting: false, submitError: '', conflict: false, confirmVisible: false, pending: null, receipt: null, completed: false, removeGuard: null } },
  computed: {
    contextKey() { return `${this.batchId}:${this.appealId}` },
    canManage() { return canCode(this.ctx, 'internship.score.publish') },
    canApprove() { const d = this.record; return d?.currentScore?.status === 'PUBLISHED' && d.scoreSnapshot?.scoreVersion != null && String(d.currentScore.version) === String(d.scoreSnapshot.scoreVersion) },
    canSubmit() { return this.canManage && this.record?.status === 'PENDING' && !this.loading && !this.error && !this.submitting && !this.conflict && !this.completed && ['approve', 'reject'].includes(this.decision) && (this.decision !== 'approve' || this.canApprove) },
    dirty() { return !this.completed && !!this.reason.trim() },
    scoreStatusLabel() { return SCORE_STATUS[this.record?.currentScore?.status] || '状态待确认' },
    confirmMessage() { return this.pending?.decision === 'approve' ? `受理「${this.record?.studentName || ''}」的申诉并撤回原正式成绩？之后需重新核算、独立复核和发布。` : `驳回「${this.record?.studentName || ''}」的成绩申诉？处理意见将保存到申诉记录。` },
    auditRecords() { return (this.record?.trail || []).filter(t => ['SUBMIT', 'APPROVE', 'REJECT'].includes(t.action)).map((t, i) => ({ id: i, action: t.action, actionLabel: ({ SUBMIT: '提交申诉', APPROVE: '受理并撤回成绩', REJECT: '驳回申诉' })[t.action], actor: t.operator || '', reason: t.note || '', at: t.at })) }
  },
  watch: {
    contextKey: { immediate: true, handler() { this.load(true) } },
    ctx: { deep: true, handler() { this.load(true) } }
  },
  mounted() {
    this.removeGuard = this.$router.beforeEach((to, from) => {
      if (to.fullPath === from.fullPath) return true
      if (to.path === from.path && to.query.stage === 'appeal' && String(to.query.appealId || '') === this.appealId && String(to.query.batchId || '') === this.batchId) return true
      if (this.submitting) return false
      return !this.dirty || window.confirm('处理意见尚未提交，离开会丢失这些内容。仍要离开吗？')
    })
    window.addEventListener('beforeunload', this.beforeUnload)
  },
  beforeUnmount() { this.sequence++; this.pending = null; this.removeGuard?.(); window.removeEventListener('beforeunload', this.beforeUnload) },
  methods: {
    beforeUnload(event) { if (this.dirty || this.submitting) { event.preventDefault(); event.returnValue = '' } },
    async load(reset = false) {
      if (this.submitting && !reset) return false
      const sequence = ++this.sequence, context = this.contextKey
      this.record = null; this.error = ''; this.loading = false
      if (reset) { this.reason = ''; this.decision = ''; this.conflict = false; this.submitError = ''; this.completed = false; this.receipt = null; this.pending = null; this.confirmVisible = false; this.submitting = false }
      if (!this.canManage) { this.error = '当前账号无成绩申诉查看和办理权限'; return false }
      if (!this.appealId || !this.batchId) { this.error = '请选择批次和申诉记录'; return false }
      this.loading = true
      const res = await scoreApi.getAppeal(this.appealId)
      if (sequence !== this.sequence || context !== this.contextKey) return false
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '申诉读取失败'; return false }
      if (String(res.data?.batchId || '') !== this.batchId || String(res.data?.id || '') !== this.appealId) { this.error = '该申诉不属于当前批次或记录，请返回列表重新选择'; return false }
      this.record = res.data
      return true
    },
    acknowledgeLatest() { if (!this.record || this.loading || this.error || this.submitting || this.record.status !== 'PENDING') return; this.conflict = false; this.submitError = ''; this.pending = null; this.decision = '' },
    openConfirmation() {
      if (!this.canSubmit || this.confirmVisible) return
      this.submitError = ''
      if (this.reason.trim().length < 5) { this.submitError = '处理意见至少填写 5 字'; this.$nextTick(() => this.$el.querySelector('textarea')?.focus()); return }
      const item = this.record
      this.pending = { id: String(item.id), expectedVersion: item.version, decision: this.decision, reason: this.reason.trim(), context: this.contextKey }
      this.confirmVisible = true
    },
    async submit() {
      const pending = this.pending, sequence = this.sequence
      if (!pending || !this.confirmVisible || !this.canSubmit || pending.context !== this.contextKey || String(this.record.id) !== pending.id || String(this.record.version) !== String(pending.expectedVersion)) return
      this.submitting = true; this.submitError = ''
      const approve = pending.decision === 'approve', fn = approve ? scoreApi.approveAppeal : scoreApi.rejectAppeal
      const res = await fn(pending.id, { reason: pending.reason, expectedVersion: pending.expectedVersion })
      if (sequence !== this.sequence || pending !== this.pending || pending.context !== this.contextKey) return
      this.submitting = false
      if (res.code !== 0) {
        this.submitError = res.message || '处理失败，意见已保留'
        if (isConflict(res)) { this.conflict = true; this.confirmVisible = false; await this.load() }
        return
      }
      this.completed = true; this.confirmVisible = false
      this.receipt = { actionLabel: approve ? '申诉已受理并撤回原成绩' : '申诉已驳回', objectLabel: this.record.studentName, id: res.data.id, version: res.data.version,
        statusLabel: approve ? '待重新核算' : '已驳回', auditText: `成绩 ${res.data.scoreId || '—'} / v${res.data.scoreVersion ?? '—'}`,
        nextStep: approve ? '重新核算、独立复核并发布' : '学生可查看申诉处理结果' }
      this.$emit('handled', this.receipt)
      await this.load()
    }
  }
}
</script>

<style scoped>
.appeal-workspace { border: 1px solid var(--border-base); border-radius: 12px; background: var(--card, #fff); padding: 24px; color: var(--text-primary); }
.appeal-workspace__header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 20px; }
h2 { margin: 0; font-size: 18px; } h3 { margin: 0 0 12px; font-size: 14px; font-weight: 600; }
.appeal-workspace__header p, .appeal-workspace__comparison p { margin: 8px 0 0; color: var(--text-secondary); font-size: 13px; }
.appeal-workspace__meta { display: flex; align-items: center; flex-wrap: wrap; gap: 16px; font-size: 12px; color: var(--text-secondary); }
.appeal-workspace__section { padding-top: 24px; margin-top: 24px; border-top: 1px solid var(--border-base); }
.appeal-workspace__reason { white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.7; font-size: 14px; }
.appeal-workspace__comparison { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 24px; }
.appeal-workspace__comparison section { padding: 20px; border-radius: 8px; background: var(--bg-subtle, #f6f8fc); }
.appeal-workspace__comparison .appeal-workspace__score { margin: 12px 0; font-size: 30px; color: var(--text-primary); font-weight: 600; font-variant-numeric: tabular-nums; }
.appeal-workspace__score small { margin-left: 6px; font-size: 12px; font-weight: 400; }
.appeal-workspace__form { padding: 0; margin: 16px 0; border: 0; min-width: 0; display: flex; flex-direction: column; gap: 10px; font-size: 14px; }
.appeal-workspace__form legend { margin-bottom: 8px; color: var(--text-secondary); }
.appeal-workspace__choices { display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 10px; }
.appeal-workspace__choices label { display: inline-flex; gap: 8px; align-items: center; padding: 10px 14px; border: 1px solid var(--border-base); border-radius: 6px; }
.appeal-workspace__choices label.selected { border-color: var(--primary-500, #2563eb); background: var(--primary-50, #eff6ff); }
input { accent-color: var(--primary-500, #2563eb); }
textarea { resize: vertical; min-height: 100px; border: 1px solid var(--border-base); border-radius: 6px; padding: 12px; font: inherit; line-height: 1.6; color: inherit; background: var(--card, #fff); }
textarea:focus-visible, input:focus-visible { outline: 2px solid var(--primary-500, #2563eb); outline-offset: 2px; }
.appeal-workspace__footer { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.appeal-workspace__footer span, .appeal-workspace__notice, .appeal-workspace__kept { font-size: 13px; color: var(--text-secondary); line-height: 1.7; }
.appeal-workspace__notice { padding: 12px 16px; background: var(--warning-bg, #fffbeb); border-radius: 6px; }
.appeal-workspace__kept { white-space: pre-wrap; overflow-wrap: anywhere; }
.appeal-workspace__state { padding: 32px 12px; text-align: center; color: var(--text-secondary); }
.is-error { color: var(--danger-600, #dc2626); font-size: 13px; }
@media (max-width: 720px) { .appeal-workspace { padding: 16px; } .appeal-workspace__comparison { grid-template-columns: 1fr; } .appeal-workspace__footer { align-items: flex-start; flex-direction: column; } }
</style>
