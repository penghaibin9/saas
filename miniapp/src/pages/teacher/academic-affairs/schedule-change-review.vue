<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="调停课审批" :subtitle="completedTasks.length ? '本人审批记录' : '待我审批'" :before-back="backToQueue" show-back />
    <view v-if="unresolvedCount" class="card ed__pending" role="status">
      <text class="t-md t-bold">有 {{ unresolvedCount }} 笔审批结果待确认</text>
      <text class="t-sm">原命令没有明确回执，暂不可重复提交。这里只读刷新正式待审队列。</text>
      <button class="btn btn-ghost" :disabled="state === 'loading' || acting" @click="load()">只读核对队列</button>
    </view>
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <MobileCompletedApprovalReceipt v-if="completedTasks.length" :tasks="completedTasks" />
        <MobileGlobalState v-else-if="targetUnavailable" state="empty" title="当前身份下未找到该事项"
          description="当前待审队列及本人已办记录均未返回原事项，请返回核对身份或联系学校管理员。" />
        <template v-else>
        <view v-if="detailId" class="ed__detail-head">
          <button class="btn btn-ghost" :disabled="acting" @click="backToQueue">‹ 返回列表</button>
          <text class="t-md t-bold">调停课证据核对</text>
        </view>
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审批调停课"
          description="轮到你审批的调课/停课/补课会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in displayedRows" :key="x.changeId" class="card ed" :class="{ 'is-target': isTarget(x) }">
            <text v-if="isTarget(x)" class="ed__target">从工作台直达的申请</text>
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.courseName || '—' }}</text>
                <text class="ed__sub">{{ changeTypeLabel(x) }} · {{ x.teacherName || x.teacherKey || '' }}</text>
              </view>
              <MobileStatusTag :label="reviewStatus(x.status)" type="warning" />
            </view>
            <template v-if="detailId">
            <view class="ed__object-id"><text>单据 {{ x.changeId }}</text></view>
            <view class="ed__evidence">
              <view class="ed__row">
                <text class="ed__row-k">原课位</text>
                <text class="flex-1 t-sm">{{ slotText(x.origin) }}</text>
              </view>
              <view class="ed__row">
                <text class="ed__row-k">拟调整</text>
                <text class="flex-1 t-sm">{{ x.changeType === 'STOP' ? (x.makeupPlan || '停课，后续安排待补充') : slotText(x.target) }}</text>
              </view>
              <view class="ed__row"><text class="ed__row-k">审批节点</text><text class="flex-1 t-sm">{{ nodeLabel(x.currentNode) }}</text></view>
              <view class="ed__row"><text class="ed__row-k">当前责任</text><text class="flex-1 t-sm">{{ responsibilityText(x) }}</text></view>
            </view>
            <view class="ed__row" v-if="x.reason"><text class="ed__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <text v-if="reviewLocked(x)" class="ed__pending-note">{{ reviewObservation(x) }}</text>
            <view class="ed__actions">
              <button class="ed__reject flex-1" :disabled="acting || reviewLocked(x)" @click="doAct(x, 'REJECT')">驳回</button>
              <button class="ed__approve flex-1" :disabled="acting || reviewLocked(x)" @click="doAct(x, 'APPROVE')">通过</button>
            </view>
            </template>
            <button v-else class="btn btn-primary" @click="openEvidence(x)">核对并处理 ›</button>
          </view>
        </view>
        <view v-if="!detailId && (pendingTotal > pendingPageSize || queuePage > 1)" class="ed__pager">
          <button class="btn btn-ghost" :disabled="queuePage <= 1 || state === 'loading'" @click="load(queuePage - 1)">上一组</button>
          <text>{{ queuePage }} / {{ Math.max(1, Math.ceil(pendingTotal / pendingPageSize)) }}</text>
          <button class="btn btn-ghost" :disabled="!pendingHasMore || state === 'loading'" @click="load(queuePage + 1)">下一组</button>
        </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>
<script>
import { normalizeError } from '@/services/request'
import { teacherApi } from '@/services/teacherApi'
import { getDoneApprovals } from '@/services/approvalApi'
import { useSessionStore } from '@/stores/session'
import { toast } from '@/utils/nav'
import { approvalContextKey, approvalReceiptChanged, hasExplicitApprovalReceipt, isApprovalConflict, isApprovalForbidden } from './approval-recovery'
const RECOVERY_SCOPE = 'schedule-change-review'
export default {
  data() { return { list: [], completedTasks: [], targetUnavailable: false, state: 'loading', acting: false, targetChangeId: '', detailId: '', queuePage: 1, pendingTotal: 0, pendingPageSize: 20, pendingHasMore: false, reviewAttempts: {}, recoveryStorageBlocked: false } },
  onLoad(options = {}) {
    this._pageActive = true
    this.targetChangeId = String(options.id || options.changeId || options.recordId || '')
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
    displayedRows() { return this.detailId ? this.list.filter((row) => String(row.changeId) === this.detailId) : this.list }
  },
  onBackPress() { if (!this.detailId) return false; this.backToQueue(); return true },
  methods: {
    reviewKey(changeId, context = this.contextKey()) { return JSON.stringify([context, String(changeId)]) },
    reviewLocked(row) { return this.recoveryStorageBlocked || !!this.reviewAttempts[this.reviewKey(row.changeId)] },
    reviewObservation(row) {
      if (this.recoveryStorageBlocked) return '本机待核对记录暂时无法读取，已停止发送新命令；请恢复存储后只读刷新。'
      const attempt = this.reviewAttempts[this.reviewKey(row.changeId)]
      if (!attempt) return ''
      return attempt.observation || (attempt.state === 'SENDING' ? '提交仍在处理，请等待原命令回执。' : '未取得明确审批回执；请只读核对，不要重复提交。')
    },
    clearPrivateReview() {
      this._loadEpoch = (this._loadEpoch || 0) + 1
      this.acting = false
      this.list = []; this.detailId = ''; this.targetChangeId = ''; this.queuePage = 1
      this.completedTasks = []; this.targetUnavailable = false
      this.pendingTotal = 0; this.pendingHasMore = false
      for (const attempt of Object.values(this.reviewAttempts)) if (attempt.context === this.contextKey()) attempt.observation = ''
      this.state = 'error'
    },
    observeReviewAttempts(rows) {
      for (const attempt of Object.values(this.reviewAttempts)) {
        if (attempt.context !== this.contextKey() || attempt.state !== 'UNKNOWN') continue
        const row = rows.find((item) => String(item.changeId) === attempt.objectId)
        attempt.observation = row ? `只读观察：${this.reviewStatus(row.status)} · ${this.nodeLabel(row.currentNode)}；仍未确认上次审批结果。` : '当前待审队列未返回原对象，不能据此确认审批成功。'
      }
    },
    reviewStatus(status) { return { SUBMITTED: '待学院审核', COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务审核中', APPROVED: '已通过', APPLIED: '已生效', REJECTED: '已驳回', CANCELLED: '已撤销' }[status] || '状态待核对' },
    changeTypeLabel(row) { return row.changeTypeLabel || ({ ADJUST: '调课', STOP: '停课', MAKEUP: '补课' })[row.changeType] || '调停课事项' },
    openEvidence(row) {
      if (this.acting || !this.list.includes(row)) return
      this.detailId = String(row.changeId)
    },
    backToQueue() {
      if (this.completedTasks.length || this.targetUnavailable) {
        this.completedTasks = []; this.targetUnavailable = false; this.targetChangeId = ''; this.load(1); return false
      }
      if (!this.detailId) return true
      if (this.acting) { toast('正在处理，请稍候'); return false }
      const wasTargeted = !!this.targetChangeId
      this.detailId = ''
      this.targetChangeId = ''
      if (wasTargeted) this.load(1)
      return false
    },
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
    slotText(slot = {}) {
      if (!slot || slot.weekday == null || slot.slotNo == null) return '—'
      const parity = slot.weekParity === 'ODD' ? '单周' : slot.weekParity === 'EVEN' ? '双周' : '每周'
      return `周${slot.weekday} 第${slot.slotNo}节 · ${slot.startWeek || '?'}-${slot.endWeek || '?'}周 ${parity}${slot.classroom ? ` · ${slot.classroom}` : ''}`
    },
    nodeLabel(node) { return node === 'COLLEGE_REVIEW' ? '学院审核' : node === 'ACADEMIC_REVIEW' ? '教务终审' : '审批节点待核对' },
    responsibilityText(row) { return `${row.currentAssigneeName || row.assigneeName || '当前审批人'} · ${this.nodeLabel(row.currentNode)}` },
    isTarget(item) { return !!this.targetChangeId && String(item.changeId || item.scheduleChangeId || '') === this.targetChangeId },
    focusTarget(rows) {
      if (!this.targetChangeId) return rows
      const index = rows.findIndex((item) => this.isTarget(item))
      if (index < 0) {
        toast('该调停课申请不存在、已处理或不在当前审批范围内')
        this.targetChangeId = ''
        return rows
      }
      this.detailId = String(rows[index].changeId)
      if (index === 0) return rows
      return [rows[index], ...rows.slice(0, index), ...rows.slice(index + 1)]
    },
    async load(page, done) {
      if (typeof page === 'function') { done = page; page = undefined }
      let requestedPage = Math.max(1, Number(page || this.queuePage) || 1)
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      if (this._actionContext !== context) {
        requestedPage = 1
        this._actionContext = context
        this._writeEpoch = (this._writeEpoch || 0) + 1
        this.acting = false
        this.list = []
        this.detailId = ''
        this.queuePage = 1
        this.pendingTotal = 0
        this.pendingHasMore = false
        this.restoreReviewAttempts(context)
      } else if (this.recoveryStorageBlocked) this.restoreReviewAttempts(context)
      this.state = 'loading'
      this.completedTasks = []; this.targetUnavailable = false
      try {
        const d = await teacherApi.getScheduleChangePending(requestedPage, this.pendingPageSize, this.targetChangeId || undefined)
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        const rows = (d && (d.list || d.items)) || []
        if (this.targetChangeId && !rows.some(row => this.isTarget(row))) {
          const doneTasks = await getDoneApprovals(1, 100, this.targetChangeId, 'AA_SCHEDULE_CHANGE')
          if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
          this.completedTasks = (doneTasks?.items || []).filter(task =>
            task.sourceBizType === 'AA_SCHEDULE_CHANGE' && String(task.sourceBizId) === this.targetChangeId)
          this.targetUnavailable = !this.completedTasks.length
          this.list = rows
        } else this.list = this.focusTarget(rows)
        this.pendingTotal = Number((d && d.total) || 0)
        this.queuePage = Number((d && d.page) || requestedPage)
        this.pendingPageSize = Number((d && d.pageSize) || this.pendingPageSize || 20)
        this.pendingHasMore = !!(d && d.hasMore)
        this.observeReviewAttempts(this.list)
        if (this.detailId && !this.list.some((row) => String(row.changeId) === this.detailId)) this.detailId = ''
        this.state = 'ready'
      } catch (error) {
        if (this._pageActive && this._loadEpoch === epoch && this.contextKey() === context) {
          if (isApprovalForbidden(error)) this.clearPrivateReview()
          this.state = normalizeError(error).pageState || 'error'
        }
      } finally { if (done) done() }
    },
    doAct(x, action) {
      if (this.completedTasks.length || this.targetUnavailable) return
      if (this._actionContext && this._actionContext !== this.contextKey()) { this.load(); return }
      if (this.acting || this.reviewLocked(x)) return
      const changeId = String(x.changeId || '')
      const context = this.contextKey()
      const epoch = this._loadEpoch
      const snapshot = JSON.stringify(x)
      const need = action === 'REJECT'
      uni.showModal({
        title: action === 'APPROVE' ? '通过调停课' : '驳回调停课',
        editable: need, placeholderText: need ? '驳回原因（≥5字）' : '',
        success: (r) => {
          if (!r.confirm || !this._pageActive || this.acting || this._loadEpoch !== epoch || this.contextKey() !== context || !this.list.includes(x) || JSON.stringify(x) !== snapshot || String(x.changeId || '') !== changeId) return
          const comment = (r.content || '').trim()
          if (need && comment.length < 5) { toast('原因至少 5 字'); return }
          const expectedVersion = Number(x.version)
          if (!Number.isInteger(expectedVersion) || expectedVersion < 0) { toast('当前单据版本缺失，请刷新后再处理'); return }
          const writeEpoch = (this._writeEpoch || 0) + 1
          this._writeEpoch = writeEpoch
          this.acting = true
          const key = this.reviewKey(changeId, context)
          const storedAttempt = approvalContextKey.createAttempt(RECOVERY_SCOPE, context, changeId, action, x)
          if (!approvalContextKey.persistAttempt(RECOVERY_SCOPE, storedAttempt)) {
            this.recoveryStorageBlocked = true
            this.acting = false
            toast('本机无法保存待核对记录，本次命令未发送')
            return
          }
          this.reviewAttempts[key] = { context, objectId: String(storedAttempt.objectId), action, epoch: writeEpoch, state: 'SENDING', observation: '' }
          teacherApi.reviewScheduleChange(changeId, action, comment, expectedVersion)
            .then((receipt) => {
              if (!hasExplicitApprovalReceipt(receipt, changeId, ['changeId', 'scheduleChangeId', 'id']) || !approvalReceiptChanged(receipt, x)) {
                const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, receipt)
                if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
                if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
                if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) { toast('审批结果待确认，请只读核对；不会自动重发原命令'); this.load() }
                return
              }
              if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, changeId, storedAttempt)) {
                if (this.reviewAttempts[key]) this.reviewAttempts[key].state = 'UNKNOWN'
                if (this.contextKey() === context) this.recoveryStorageBlocked = true
                if (this._pageActive && this.contextKey() === context) toast('已收到回执，但本机待核对记录无法清除，请勿重复提交')
                return
              }
              delete this.reviewAttempts[key]
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              toast(action === 'APPROVE' ? '已通过' : '已驳回'); this.targetChangeId = ''; this.load(1)
            })
            .catch((e) => {
              if (isApprovalConflict(e)) {
                if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, changeId, storedAttempt)) {
                  if (this.reviewAttempts[key]) this.reviewAttempts[key].state = 'UNKNOWN'
                  if (this.contextKey() === context) this.recoveryStorageBlocked = true
                  if (this._pageActive && this.contextKey() === context) toast('状态冲突已返回，但本机待核对记录无法清除')
                  return
                }
                delete this.reviewAttempts[key]
                if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) { toast((e && e.message) || '申请状态已变化，正在刷新'); this.load() }
                return
              }
              const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, e)
              if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
              if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              if (isApprovalForbidden(e)) this.clearPrivateReview()
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
.ed__sub { display:block; color: var(--text-tertiary); font-size: var(--font-size-xs); margin-top: 4px; }
.ed__row { display:flex; gap: var(--space-2); margin-top: 6px; }
.ed__row-k { color: var(--text-tertiary); font-size: var(--font-size-xs); width: 48px; }
.ed__evidence { padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--gray-50); }
.ed__actions { display:flex; gap: var(--space-2); margin-top: 10px; }
.ed__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ed__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ed__reject::after, .ed__approve::after { border: none; }
</style>
