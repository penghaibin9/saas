<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="缓考审批" subtitle="待我审批" :before-back="backToQueue" fallback-url="/pages/teacher/workbench/index" show-back />

    <view v-if="unresolvedCount" class="card ed__pending" role="status">
      <text class="t-md t-bold">有 {{ unresolvedCount }} 笔审批结果待确认</text>
      <text class="t-sm">原命令没有明确回执，暂不可重复提交。这里只读刷新正式待审队列。</text>
      <button class="btn btn-ghost" :disabled="state === 'loading' || acting" @click="load()">只读核对队列</button>
    </view>

    <MobileGlobalState :state="state" :title="state === 'noLicense' ? '本校未开通教务管理' : ''" @retry="load" @back="goBack">
      <template #actions>
        <button v-if="state === 'error'" class="btn btn-primary" @click="load()">重试</button>
        <button class="btn btn-ghost" @click="goBack">返回</button>
      </template>
      <view class="page-pad">
        <view v-if="detailId" class="ed__detail-head">
          <button class="btn btn-ghost" :disabled="acting" @click="backToQueue">‹ 返回列表</button>
          <text class="t-md t-bold">缓考申请核对</text>
        </view>
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批缓考申请"
          description="轮到你审批的缓考申请会出现在这里。" @back="goBack" />
        <view class="stack" v-else>
          <view v-for="x in displayedRows" :key="x.deferId" class="card ed" :class="{ 'is-target': isTarget(x) }">
            <text v-if="isTarget(x)" class="ed__target">从工作台直达的申请</text>
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.studentName || '—' }}</text>
                <text class="ed__sub">{{ x.courseName || '' }}</text>
              </view>
              <MobileStatusTag :label="statusLabel(x.status)" type="warning" />
            </view>
            <template v-if="detailId">
            <view class="ed__object-id"><text>单据 {{ x.deferId }}</text></view>
            <view class="ed__evidence">
              <view class="ed__row" v-if="x.reasonType"><text class="ed__row-k">原因类型</text><text class="flex-1 t-sm">{{ reasonLabel(x.reasonType) }}</text></view>
              <view class="ed__row" v-if="x.reason"><text class="ed__row-k">申请事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
              <view class="ed__row"><text class="ed__row-k">申请时间</text><text class="flex-1 t-sm">{{ fmt(x.applyAt) }}</text></view>
              <view class="ed__row"><text class="ed__row-k">当前节点</text><text class="flex-1 t-sm">{{ statusLabel(x.status) }}</text></view>
              <view class="ed__row"><text class="ed__row-k">当前责任</text><text class="flex-1 t-sm">{{ responsibilityText(x) }}</text></view>
            </view>
            <text v-if="reviewLocked(x)" class="ed__pending-note">{{ reviewObservation(x) }}</text>
            <view class="ed__actions">
              <button class="ed__reject flex-1" :disabled="acting || reviewLocked(x)" @click="doAct(x, 'RETURN')">退回</button>
              <button class="ed__reject flex-1" :disabled="acting || reviewLocked(x)" @click="doAct(x, 'REJECT')">驳回</button>
              <button class="ed__approve flex-1" :disabled="acting || reviewLocked(x)" @click="doAct(x, 'APPROVE')">通过</button>
            </view>
            </template>
            <button v-else class="btn btn-primary" @click="openEvidence(x)">核对并处理 ›</button>
          </view>
        </view>
        <view v-if="!detailId && list.length > 20" class="ed__pager">
          <button class="btn btn-ghost" :disabled="queuePage === 0" @click="queuePage--">上一组</button>
          <text>{{ queuePage + 1 }} / {{ Math.ceil(list.length / 20) }}</text>
          <button class="btn btn-ghost" :disabled="(queuePage + 1) * 20 >= list.length" @click="queuePage++">下一组</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { useSessionStore } from '@/stores/session'
import { toast, back } from '@/utils/nav'
import { approvalContextKey, approvalReceiptChanged, hasExplicitApprovalReceipt, isApprovalConflict, isApprovalForbidden } from '../academic-affairs/approval-recovery'
import { normalizeError } from '@/services/request'

const RECOVERY_SCOPE = 'exam-defer-review'

const STATUS_LABELS = { COUNSELOR_REVIEW: '辅导员审批中', TEACHER_CONFIRM: '任课教师确认中', COLLEGE_REVIEW: '学院审核中', ACADEMIC_FINAL: '教务终审中', APPROVED: '已通过', RETURNED: '已退回补材料', REJECTED: '已驳回' }
const REASON_LABELS = { ILLNESS: '疾病', SICK: '疾病', MEDICAL: '疾病', OFFICIAL: '公务或学校安排', EMERGENCY: '突发事件', FAMILY: '家庭重大事项', OTHER: '其他' }

export default {
  data() { return { list: [], state: 'loading', acting: false, targetDeferId: '', detailId: '', queuePage: 0, reviewAttempts: {}, recoveryStorageBlocked: false } },
  onLoad(options = {}) {
    this._pageActive = true
    this.targetDeferId = String(options.id || options.deferId || options.recordId || '')
    this.restoreReviewAttempts()
    this.load()
  },
  onShow() {
    this._pageActive = true
    if (this._actionContext && this._actionContext !== this.contextKey()) this._needsRefresh = true
    if (this._needsRefresh) { this._needsRefresh = false; this.load() }
  },
  onHide() { this._pageActive = false; this._needsRefresh = true; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    unresolvedCount() { return Object.values(this.reviewAttempts).filter((attempt) => attempt.context === this.contextKey() && attempt.state === 'UNKNOWN').length + (this.recoveryStorageBlocked ? 1 : 0) },
    displayedRows() { return this.detailId ? this.list.filter((row) => String(row.deferId) === this.detailId) : this.list.slice(this.queuePage * 20, (this.queuePage + 1) * 20) }
  },
  onBackPress() { if (!this.detailId) return false; this.backToQueue(); return true },
  methods: {
    reviewKey(deferId, context = this.contextKey()) { return JSON.stringify([context, String(deferId)]) },
    reviewLocked(row) { return this.recoveryStorageBlocked || !!this.reviewAttempts[this.reviewKey(row.deferId)] },
    reviewObservation(row) {
      if (this.recoveryStorageBlocked) return '本机待核对记录暂时无法读取，已停止发送新命令；请恢复存储后只读刷新。'
      const attempt = this.reviewAttempts[this.reviewKey(row.deferId)]
      if (!attempt) return ''
      return attempt.observation || (attempt.state === 'SENDING' ? '提交仍在处理，请等待原命令回执。' : '未取得明确审批回执；请只读核对，不要重复提交。')
    },
    clearPrivateReview() {
      this._loadEpoch = (this._loadEpoch || 0) + 1
      this.acting = false
      this.list = []; this.detailId = ''; this.targetDeferId = ''; this.queuePage = 0
      for (const attempt of Object.values(this.reviewAttempts)) if (attempt.context === this.contextKey()) attempt.observation = ''
      this.state = 'error'
    },
    observeReviewAttempts(rows) {
      for (const attempt of Object.values(this.reviewAttempts)) {
        if (attempt.context !== this.contextKey() || attempt.state !== 'UNKNOWN') continue
        const row = rows.find((item) => String(item.deferId) === attempt.objectId)
        attempt.observation = row ? `只读观察：${this.statusLabel(row.status)}；仍未确认上次审批结果。` : '当前待审队列未返回原对象，不能据此确认审批成功。'
      }
    },
    openEvidence(row) {
      if (this.acting || !this.list.includes(row)) return
      this.detailId = String(row.deferId)
    },
    backToQueue() {
      if (!this.detailId) return true
      if (this.acting) { toast('正在处理，请稍候'); return false }
      this.detailId = ''
      this.targetDeferId = ''
      return false
    },
    goBack() { if (this.backToQueue() !== false) back('/pages/teacher/workbench/index') },
    contextKey() {
      return approvalContextKey(useSessionStore())
    },
    restoreReviewAttempts(context = this.contextKey()) {
      const restored = approvalContextKey.restoreAttempts(RECOVERY_SCOPE, context)
      this.reviewAttempts = {}
      this.recoveryStorageBlocked = !restored.ok
      for (const attempt of restored.attempts) this.reviewAttempts[this.reviewKey(attempt.objectId, context)] = { context, objectId: attempt.objectId, action: attempt.action, state: 'UNKNOWN', observation: '' }
      return restored.ok
    },
    fmt(v) { return (v || '').slice(0, 16).replace('T', ' ') },
    reasonLabel(value) { return REASON_LABELS[String(value || '').toUpperCase()] || '其他' },
    statusLabel(s) { return STATUS_LABELS[s] || s },
    responsibilityText(row) {
      return `${row.currentAssigneeName || row.assigneeName || row.teacherName || '当前审批人'} · ${this.statusLabel(row.status)}`
    },
    isTarget(item) { return !!this.targetDeferId && String(item.deferId || item.id || '') === this.targetDeferId },
    focusTarget(rows) {
      if (!this.targetDeferId) return rows
      const index = rows.findIndex((item) => this.isTarget(item))
      if (index < 0) {
        toast('该缓考申请不存在、已处理或不在当前审批范围内')
        this.targetDeferId = ''
        return rows
      }
      this.detailId = String(rows[index].deferId)
      if (index === 0) return rows
      return [rows[index], ...rows.slice(0, index), ...rows.slice(index + 1)]
    },
    async load(done) {
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      if (this._actionContext !== context) {
        this._actionContext = context
        this._writeEpoch = (this._writeEpoch || 0) + 1
        this.acting = false
        this.list = []
        this.detailId = ''
        this.queuePage = 0
        this.restoreReviewAttempts(context)
      } else if (this.recoveryStorageBlocked) this.restoreReviewAttempts(context)
      this.state = 'loading'
      try {
        const d = await teacherApi.getAcademicDeferPending()
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        this.list = this.focusTarget((d && (d.list || d.items)) || [])
        this.observeReviewAttempts(this.list)
        if (this.detailId && !this.list.some((row) => String(row.deferId) === this.detailId)) this.detailId = ''
        this.queuePage = Math.min(this.queuePage, Math.max(0, Math.ceil(this.list.length / 20) - 1))
        this.state = 'ready'
      } catch (error) {
        if (this._pageActive && this._loadEpoch === epoch && this.contextKey() === context) {
          if (isApprovalForbidden(error)) this.clearPrivateReview()
          this.state = normalizeError(error).pageState || 'error'
        }
      } finally { if (done) done() }
    },
    doAct(x, action) {
      if (this._actionContext && this._actionContext !== this.contextKey()) { this.load(); return }
      if (this.acting || this.reviewLocked(x)) return
      const deferId = String(x.deferId || '')
      const context = this.contextKey()
      const epoch = this._loadEpoch
      const snapshot = JSON.stringify(x)
      const needReason = action !== 'APPROVE'
      const title = { APPROVE: '通过缓考申请', RETURN: '退回补材料', REJECT: '驳回缓考申请' }[action]
      uni.showModal({
        title, editable: needReason, placeholderText: needReason ? '请填写原因（≥5 字）' : '', content: '',
        success: (r) => {
          if (!r.confirm || !this._pageActive || this.acting || this._loadEpoch !== epoch || this.contextKey() !== context || !this.list.includes(x) || JSON.stringify(x) !== snapshot || String(x.deferId || '') !== deferId) return
          const reason = (r.content || '').trim()
          if (needReason && reason.length < 5) { toast('原因至少 5 个字'); return }
          const writeEpoch = (this._writeEpoch || 0) + 1
          this._writeEpoch = writeEpoch
          this.acting = true
          const key = this.reviewKey(deferId, context)
          const storedAttempt = approvalContextKey.createAttempt(RECOVERY_SCOPE, context, deferId, action, x)
          if (!approvalContextKey.persistAttempt(RECOVERY_SCOPE, storedAttempt)) {
            this.recoveryStorageBlocked = true
            this.acting = false
            toast('本机无法保存待核对记录，本次命令未发送')
            return
          }
          this.reviewAttempts[key] = { context, objectId: String(storedAttempt.objectId), action, epoch: writeEpoch, state: 'SENDING', observation: '' }
          teacherApi.reviewAcademicDefer(deferId, action, reason, x.version)
            .then((receipt) => {
              if (!hasExplicitApprovalReceipt(receipt, deferId, ['deferId', 'id']) || !approvalReceiptChanged(receipt, x)) {
                const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, receipt)
                if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
                if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
                if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) { toast('审批结果待确认，请只读核对；不会自动重发原命令'); this.load() }
                return
              }
              if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, deferId, storedAttempt)) {
                if (this.reviewAttempts[key]) this.reviewAttempts[key].state = 'UNKNOWN'
                if (this.contextKey() === context) this.recoveryStorageBlocked = true
                if (this._pageActive && this.contextKey() === context) toast('已收到回执，但本机待核对记录无法清除，请勿重复提交')
                return
              }
              delete this.reviewAttempts[key]
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              toast(action === 'APPROVE' ? '已通过' : action === 'RETURN' ? '已退回' : '已驳回'); this.targetDeferId = ''; this.load()
            })
            .catch((error) => {
              if (isApprovalConflict(error)) {
                if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, deferId, storedAttempt)) {
                  if (this.reviewAttempts[key]) this.reviewAttempts[key].state = 'UNKNOWN'
                  if (this.contextKey() === context) this.recoveryStorageBlocked = true
                  if (this._pageActive && this.contextKey() === context) toast('状态冲突已返回，但本机待核对记录无法清除')
                  return
                }
                delete this.reviewAttempts[key]
                if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) { toast((error && error.message) || '申请状态已变化，正在刷新'); this.load() }
                return
              }
              const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, error)
              if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
              if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              if (isApprovalForbidden(error)) this.clearPrivateReview()
              toast('审批结果待确认，请只读核对；不会自动重发原命令')
            })
            .finally(() => { if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.ed__pending { margin: 12px; display: flex; flex-direction: column; gap: 8px; }
.ed__pending-note { color: var(--text-secondary); font-size: 12px; }
.ed__detail-head, .ed__pager { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.ed__pager { margin-top: 16px; font-size: 12px; color: var(--text-secondary); }
.ed__object-id { color: var(--text-tertiary); font-size: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.ed { display: flex; flex-direction: column; gap: var(--space-2); }
.ed.is-target { border: 1px solid var(--teacher-500); box-shadow: 0 0 0 2px var(--teacher-50); }
.ed__target { color: var(--teacher-700); font-size: var(--font-size-xs); font-weight: 600; }
.ed__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ed__row { display: flex; gap: var(--space-3); }
.ed__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 64px; flex-shrink: 0; }
.ed__evidence { padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--gray-50); }
.ed__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ed__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ed__reject::after { border: none; }
.ed__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ed__approve::after { border: none; }
</style>
