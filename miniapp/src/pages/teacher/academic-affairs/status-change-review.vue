<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学籍异动审批" subtitle="待我审批" :before-back="backToQueue" show-back />
    <view v-if="unresolvedCount" class="card ed__pending" role="status">
      <text class="t-md t-bold">有 {{ unresolvedCount }} 笔审批结果待确认</text>
      <text class="t-sm">原审批暂不可重复提交。核对会读取待审队列和本人已处理任务，不会重发审批。</text>
      <text v-for="attempt in unresolvedAttempts" :key="attempt.attemptKey || attempt.objectId" class="t-sm">单据 {{ attempt.objectId }} · {{ nodeLabel(attempt.beforeNode) }}：{{ attempt.observation || '等待核对正式任务' }}</text>
      <button class="btn btn-ghost" :disabled="state === 'loading' || acting" @click="load()">只读核对审批结果</button>
    </view>
    <view v-if="recoveredNotice" class="card ed__pending" role="status"><text>{{ recoveredNotice }}</text></view>
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view v-if="detailId" class="ed__detail-head">
          <button class="btn btn-ghost" :disabled="acting" @click="backToQueue">‹ 返回列表</button>
          <text class="t-md t-bold">异动证据核对</text>
        </view>
        <MobileGlobalState v-if="!list.length" state="empty" title="暂无待审异动"
          description="轮到你节点的学籍异动会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="x in displayedRows" :key="x.changeId" class="card ed" :class="{ 'is-target': isTarget(x) }">
            <text v-if="isTarget(x)" class="ed__target">从工作台直达的申请</text>
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.realName || '—' }}</text>
                <text class="ed__sub">{{ x.changeTypeLabel || '学籍异动' }} · {{ nodeLabel(x.currentNode) }}</text>
              </view>
              <MobileStatusTag :label="reviewStatus(x.status)" type="warning" />
            </view>
            <template v-if="detailId">
            <view class="ed__object-id"><text>单据 {{ x.changeId }}</text></view>
            <view class="ed__evidence">
              <view class="ed__row"><text class="ed__row-k">状态变化</text><text class="flex-1 t-sm">{{ x.fromStatus || '—' }} → {{ x.toStatus || '—' }}</text></view>
              <view class="ed__row"><text class="ed__row-k">生效日期</text><text class="flex-1 t-sm">{{ fmt(x.effectiveDate) || '—' }}</text></view>
              <view class="ed__row"><text class="ed__row-k">审批节点</text><text class="flex-1 t-sm">{{ nodeLabel(x.currentNode) }}</text></view>
            </view>
            <view class="ed__row" v-if="x.reason"><text class="ed__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
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
import { normalizeError } from '@/services/request'
import { teacherApi } from '@/services/teacherApi'
import { getDoneApprovals } from '@/services/approvalApi'
import { matchCompletedStatusTask } from './status-review-recovery'
import { useSessionStore } from '@/stores/session'
import { toast } from '@/utils/nav'
import { approvalContextKey, approvalReceiptChanged, hasExplicitApprovalReceipt, isApprovalConflict, isApprovalForbidden } from './approval-recovery'
const RECOVERY_SCOPE = 'status-change-review'
export default {
  data() { return { list: [], state: 'loading', acting: false, targetChangeId: '', detailId: '', queuePage: 0, reviewAttempts: {}, recoveryStorageBlocked: false, recoveredNotice: '' } },
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
    unresolvedAttempts() { return Object.values(this.reviewAttempts).filter(attempt => attempt.context === this.contextKey() && attempt.state === 'UNKNOWN') },
    unresolvedCount() { return Object.values(this.reviewAttempts).filter((attempt) => attempt.context === this.contextKey() && attempt.state === 'UNKNOWN').length + (this.recoveryStorageBlocked ? 1 : 0) },
    displayedRows() { return this.detailId ? this.list.filter((row) => String(row.changeId) === this.detailId) : this.list.slice(this.queuePage * 20, (this.queuePage + 1) * 20) }
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
    isForbidden(error) {
      return isApprovalForbidden(error)
    },
    clearPrivateReview() {
      this._loadEpoch = (this._loadEpoch || 0) + 1
      this.acting = false
      this.list = []; this.detailId = ''; this.targetChangeId = ''; this.queuePage = 0
      this.recoveredNotice = ''
      for (const attempt of Object.values(this.reviewAttempts)) if (attempt.context === this.contextKey()) attempt.observation = ''
      this.state = 'error'
    },
    observeReviewAttempts(rows) {
      for (const attempt of Object.values(this.reviewAttempts)) {
        if (attempt.context !== this.contextKey() || attempt.state !== 'UNKNOWN') continue
        const row = rows.find((item) => String(item.changeId) === attempt.objectId)
        attempt.observation = row
          ? `只读观察：${this.reviewStatus(row.status)} · ${this.nodeLabel(row.currentNode)}；仍未确认上次提交结果。`
          : '当前待审队列未返回原对象，不能据此确认本次审批成功。'
      }
    },
    async recoverCompletedTasks(context, epoch) {
      for (const [key, attempt] of Object.entries(this.reviewAttempts)) {
        if (attempt.context !== context || attempt.state !== 'UNKNOWN') continue
        const current = () => this._pageActive && this._loadEpoch === epoch && this.contextKey() === context && this.reviewAttempts[key] === attempt
        // A fresh loop through the same node cannot be identified by an old reference lacking taskId.
        if (!attempt.beforeTaskId && this.list.some(row => String(row.changeId) === attempt.objectId && row.currentNode === attempt.beforeNode)) continue
        try {
          const done = await getDoneApprovals(1, 100, attempt.beforeTaskId || attempt.objectId, 'AA_STATUS_CHANGE')
          if (!current()) return
          const task = matchCompletedStatusTask(attempt, done)
          if (!task) { attempt.observation = '尚未找到可唯一匹配的本人已办任务，保留待确认。'; continue }
          if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, attempt.objectId, attempt)) {
            this.recoveryStorageBlocked = true
            attempt.observation = '已查到正式结果，但本机待确认记录暂时无法更新。'
            continue
          }
          delete this.reviewAttempts[key]
          const outcome = { APPROVED: '已通过', REJECTED: '已驳回', TRANSFERRED: '已退回', RETURNED: '已退回' }[task.status]
          this.recoveredNotice = `已核对本人正式任务 ${task.taskId}：单据 ${attempt.objectId} ${outcome}。未重发审批；该任务结果不代表整张申请已终审。`
        } catch (_) {
          if (!current()) return
          attempt.observation = '本人已办任务读取失败，保留待确认，可稍后重试。'
        }
      }
    },
    reviewStatus(status) { return { SUBMITTED: '已提交', IN_REVIEW: '审核中', APPROVED: '已通过', REJECTED: '已驳回', RETURNED: '已退回', CANCELLED: '已撤销' }[status] || '状态待核对' },
    openEvidence(row) {
      if (this.acting || !this.list.includes(row)) return
      this.detailId = String(row.changeId)
    },
    backToQueue() {
      if (!this.detailId) return true
      if (this.acting) { toast('正在处理，请稍候'); return false }
      this.detailId = ''
      this.targetChangeId = ''
      return false
    },
    contextKey() {
      return approvalContextKey(useSessionStore())
    },
    restoreReviewAttempts(context = this.contextKey()) {
      const restored = approvalContextKey.restoreAttempts(RECOVERY_SCOPE, context)
      this.reviewAttempts = {}
      this.recoveryStorageBlocked = !restored.ok
      for (const attempt of restored.attempts) this.reviewAttempts[this.reviewKey(attempt.objectId, context)] = { ...attempt, context, state: 'UNKNOWN', observation: '' }
      return restored.ok
    },
    fmt(value) { return String(value || '').slice(0, 10) },
    nodeLabel(node) {
      return {
        COUNSELOR_REVIEW: '辅导员审核', COLLEGE_REVIEW: '学院审核',
        OUT_COLLEGE_REVIEW: '转出学院审核', COLLEGE_ASSIGN_CLASS: '转入学院分班',
        IN_COLLEGE_REVIEW: '转入学院审核', AA_OFFICE_FINAL: '教务终审'
      }[node] || node || '—'
    },
    isTarget(item) { return !!this.targetChangeId && String(item.changeId || '') === this.targetChangeId },
    focusTarget(rows) {
      if (!this.targetChangeId) return rows
      const index = rows.findIndex((item) => this.isTarget(item))
      if (index < 0) {
        toast('该学籍异动不存在、已处理或不在当前审批范围内')
        this.targetChangeId = ''
        return rows
      }
      this.detailId = String(rows[index].changeId)
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
        this.recoveredNotice = ''
        this.restoreReviewAttempts(context)
      } else if (this.recoveryStorageBlocked) this.restoreReviewAttempts(context)
      this.state = 'loading'
      try {
        const d = await teacherApi.getStatusChangePending()
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        this.list = this.focusTarget((d && (d.list || d.items)) || [])
        this.observeReviewAttempts(this.list)
        await this.recoverCompletedTasks(context, epoch)
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        if (this.detailId && !this.list.some((row) => String(row.changeId) === this.detailId)) this.detailId = ''
        this.queuePage = Math.min(this.queuePage, Math.max(0, Math.ceil(this.list.length / 20) - 1))
        this.state = 'ready'
      } catch (error) {
        if (this._pageActive && this._loadEpoch === epoch && this.contextKey() === context) {
          if (this.isForbidden(error)) this.clearPrivateReview()
          this.state = normalizeError(error).pageState || 'error'
        }
      } finally { if (done) done() }
    },
    doAct(x, action) {
      if (this._actionContext && this._actionContext !== this.contextKey()) { this.load(); return }
      if (this.acting || this.reviewLocked(x)) return
      const changeId = String(x.changeId || '')
      const context = this.contextKey()
      const epoch = this._loadEpoch
      const snapshot = JSON.stringify(x)
      const need = action !== 'APPROVE'
      uni.showModal({
        title: { APPROVE: '通过异动', RETURN: '退回异动', REJECT: '驳回异动' }[action],
        editable: need, placeholderText: need ? '原因（≥5字）' : '',
        success: (r) => {
          if (this.contextKey() !== context) { this.load(); return }
          if (!r.confirm || !this._pageActive || this.acting || this.reviewLocked(x) || this._loadEpoch !== epoch || this.contextKey() !== context || !this.list.includes(x) || JSON.stringify(x) !== snapshot || String(x.changeId || '') !== changeId) return
          const reason = (r.content || '').trim()
          if (need && reason.length < 5) { toast('原因至少 5 字'); return }
          const writeEpoch = (this._writeEpoch || 0) + 1
          this._writeEpoch = writeEpoch
          this.acting = true
          const key = this.reviewKey(changeId, context)
          // Local transport receipt only; a queue observation never proves which command changed a node.
          const storedAttempt = approvalContextKey.createAttempt(RECOVERY_SCOPE, context, changeId, action, x)
          if (!approvalContextKey.persistAttempt(RECOVERY_SCOPE, storedAttempt)) {
            this.recoveryStorageBlocked = true
            this.acting = false
            toast('本机无法保存待核对记录，本次命令未发送')
            return
          }
          this.reviewAttempts[key] = { ...storedAttempt, context, objectId: String(storedAttempt.objectId), action, epoch: writeEpoch, state: 'SENDING', observation: '' }
          teacherApi.reviewStatusChange(changeId, action, reason, x.decisionVersion)
            .then((receipt) => {
              if (!hasExplicitApprovalReceipt(receipt, changeId, ['changeId', 'id']) || !approvalReceiptChanged(receipt, x)) {
                const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, receipt)
                if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
                if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
                if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) {
                  toast('审批结果待确认，请只读核对；不会自动重发原命令')
                  this.load()
                }
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
              toast('已处理'); this.targetChangeId = ''; this.load()
            })
            .catch((e) => {
              // 403/409 are explicit non-write responses. The original command reference may be
              // cleared; retaining it would falsely present a transport-uncertain result forever.
              if (isApprovalConflict(e) || isApprovalForbidden(e)) {
                if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, changeId, storedAttempt)) {
                  if (this.reviewAttempts[key]) this.reviewAttempts[key].state = 'UNKNOWN'
                  if (this.contextKey() === context) this.recoveryStorageBlocked = true
                  if (this._pageActive && this.contextKey() === context) toast('明确拒绝已返回，但本机待核对记录无法清除')
                  return
                }
                delete this.reviewAttempts[key]
                if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) {
                  if (isApprovalForbidden(e)) this.clearPrivateReview()
                  else this.load()
                  toast((e && e.message) || '审批事实已变化，正在刷新')
                }
                return
              }
              // Transport failure does not prove zero writes. Keep only the command reference, never the entered reason.
              const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, e)
              if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
              if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
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
.ed__evidence { padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--gray-50); }
.ed__row { display:flex; gap: var(--space-2); margin-top: 6px; }
.ed__row-k { color: var(--text-tertiary); font-size: var(--font-size-xs); width: 64px; flex-shrink: 0; }
.ed__actions { display:flex; gap: var(--space-2); margin-top: 10px; }
.ed__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ed__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ed__reject::after, .ed__approve::after { border: none; }
</style>
