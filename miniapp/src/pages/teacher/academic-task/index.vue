<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="教学任务确认" subtitle="确认 · 退回" :before-back="backToQueue" show-back />

    <view v-if="unresolvedCount" class="card at__pending" role="status">
      <text class="t-md t-bold">有 {{ unresolvedCount }} 笔任务结果待确认</text>
      <text class="t-sm">原命令没有明确回执，暂不可重复提交。这里只读刷新正式任务，不会重发命令。</text>
      <button class="btn btn-ghost" :disabled="state === 'loading' || acting" @click="load()">只读核对任务</button>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad">
        <view v-if="detailId" class="at__detail-head">
          <button class="btn btn-ghost" :disabled="acting" @click="backToQueue">‹ 返回列表</button>
          <text class="t-md t-bold">教学任务核对</text>
        </view>
        <MobileGlobalState v-if="!tasks.length" state="empty" title="暂无教学任务"
          description="分配给你的教学任务会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="t in displayedRows" :key="t.taskId" class="card at" :class="{ 'is-target': isTarget(t) }">
            <view v-if="isTarget(t)" class="at__target">从工作台直达的任务</view>
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ t.courseName || '—' }}</text>
                <text class="at__sub">{{ t.courseCode || '' }} · {{ t.teachingClassName || t.teachingClassCode || '' }}</text>
              </view>
              <MobileStatusTag :label="statusLabel(t.status)" :type="statusTone(t.status)" />
            </view>
            <template v-if="detailId">
            <view class="at__object-id"><text>单据 {{ t.taskId }}</text></view>
            <view class="at__row"><text class="at__row-k">学时</text><text class="flex-1 t-sm">周{{ t.weeklyHours == null ? '—' : t.weeklyHours }}节 · 共{{ t.totalHours == null ? '—' : t.totalHours }}节（第{{ t.startWeek || '-' }}~{{ t.endWeek || '-' }}周）</text></view>
            <view class="at__row" v-if="t.expectedStudents"><text class="at__row-k">人数</text><text class="flex-1 t-sm">{{ t.expectedStudents }} 人</text></view>
            <view class="at__row"><text class="at__row-k">课程版本</text><text class="flex-1 t-sm">{{ t.courseVersion || '未提供' }}</text></view>
            <view class="at__row"><text class="at__row-k">当前责任</text><text class="flex-1 t-sm">{{ responsibilityText(t) }}</text></view>
            <view class="at__row" v-if="t.status === 'REJECTED_BY_TEACHER' && t.rejectReason"><text class="at__row-k">退回原因</text><text class="flex-1 t-sm">{{ t.rejectReason }}</text></view>

            <text v-if="reviewLocked(t)" class="at__pending-note">{{ reviewObservation(t) }}</text>
            <view class="at__actions" v-if="t.status === 'ASSIGNED'">
              <button class="at__reject flex-1" :disabled="acting || reviewLocked(t)" @click="doReject(t)">退回</button>
              <button class="at__confirm flex-1" :disabled="acting || reviewLocked(t)" @click="doConfirm(t)">确认</button>
            </view>
            </template>
            <button v-else class="btn btn-primary" @click="openEvidence(t)">核对并处理 ›</button>
          </view>
        </view>
        <view v-if="!detailId && (queueTotal > queuePageSize || queuePage > 1)" class="at__pager">
          <button class="btn btn-ghost" :disabled="queuePage <= 1 || state === 'loading'" @click="load(queuePage - 1)">上一组</button>
          <text>{{ queuePage }} / {{ Math.max(1, Math.ceil(queueTotal / queuePageSize)) }}</text>
          <button class="btn btn-ghost" :disabled="!queueHasMore || state === 'loading'" @click="load(queuePage + 1)">下一组</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { normalizeError } from '@/services/request'
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'
import { useSessionStore } from '@/stores/session'
import { approvalContextKey, approvalReceiptChanged, hasExplicitApprovalReceipt, isApprovalConflict, isApprovalForbidden } from '../academic-affairs/approval-recovery'

const RECOVERY_SCOPE = 'academic-task-review'

const STATUS_LABELS = {
  ASSIGNED: '待确认', TEACHER_CONFIRMED: '已确认', REJECTED_BY_TEACHER: '已退回',
  READY: '已入库', MERGED: '已合班'
}
const STATUS_TONES = {
  ASSIGNED: 'warning', TEACHER_CONFIRMED: 'success', REJECTED_BY_TEACHER: 'danger',
  READY: 'success', MERGED: 'default'
}

export default {
  data() { return { tasks: [], state: 'loading', acting: false, targetTaskId: '', detailId: '', queuePage: 1, queueTotal: 0, queuePageSize: 20, queueHasMore: false, reviewAttempts: {}, recoveryStorageBlocked: false } },
  onLoad(options = {}) {
    this._pageActive = true
    this.targetTaskId = String(options.id || options.taskId || '')
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
    displayedRows() { return this.detailId ? this.tasks.filter((row) => String(row.taskId) === this.detailId) : this.tasks }
  },
  onBackPress() { if (!this.detailId) return false; this.backToQueue(); return true },
  methods: {
    reviewKey(taskId, context = this.contextKey()) { return JSON.stringify([context, String(taskId)]) },
    reviewLocked(row) { return this.recoveryStorageBlocked || !!this.reviewAttempts[this.reviewKey(row.taskId)] },
    reviewObservation(row) {
      if (this.recoveryStorageBlocked) return '本机待核对记录暂时无法读取，已停止发送新命令；请恢复存储后只读刷新。'
      const attempt = this.reviewAttempts[this.reviewKey(row.taskId)]
      if (!attempt) return ''
      return attempt.observation || (attempt.state === 'SENDING' ? '提交仍在处理，请等待原命令回执。' : '未取得明确处理回执；请只读核对，不要重复提交。')
    },
    clearPrivateReview() {
      this._loadEpoch = (this._loadEpoch || 0) + 1
      this.acting = false
      this.tasks = []; this.detailId = ''; this.targetTaskId = ''; this.queuePage = 1
      this.queueTotal = 0; this.queueHasMore = false
      for (const attempt of Object.values(this.reviewAttempts)) if (attempt.context === this.contextKey()) attempt.observation = ''
      this.state = 'error'
    },
    observeReviewAttempts(rows) {
      for (const attempt of Object.values(this.reviewAttempts)) {
        if (attempt.context !== this.contextKey() || attempt.state !== 'UNKNOWN') continue
        const row = rows.find((item) => String(item.taskId) === attempt.objectId)
        attempt.observation = row ? `只读观察：${this.statusLabel(row.status)}；仍未确认上次命令结果。` : '当前任务队列未返回原对象，不能据此确认命令成功。'
      }
    },
    openEvidence(row) {
      if (this.acting || !this.tasks.includes(row)) return
      this.detailId = String(row.taskId)
    },
    backToQueue() {
      if (!this.detailId) return true
      if (this.acting) { toast('正在处理，请稍候'); return false }
      const wasTargeted = !!this.targetTaskId
      this.detailId = ''
      this.targetTaskId = ''
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
    responsibilityText(task) {
      const owner = task.currentAssigneeName || task.assigneeName || task.teacherName || '当前登录教师'
      return task.status === 'ASSIGNED' ? `${owner}核对并确认授课任务` : `${owner} · ${this.statusLabel(task.status)}`
    },
    statusLabel(s) { return STATUS_LABELS[s] || s },
    statusTone(s) { return STATUS_TONES[s] || 'default' },
    isTarget(task) { return !!this.targetTaskId && String(task.taskId || task.teachingTaskId || '') === this.targetTaskId },
    focusTarget(rows) {
      if (!this.targetTaskId) return rows
      const index = rows.findIndex((task) => this.isTarget(task))
      if (index < 0) {
        toast('该教学任务不存在、已处理或不在当前身份范围内')
        this.targetTaskId = ''
        return rows
      }
      this.detailId = String(rows[index].taskId)
      if (index === 0) return rows
      return [rows[index], ...rows.slice(0, index), ...rows.slice(index + 1)]
    },
    async load(page, done) {
      if (typeof page === 'function') { done = page; page = undefined }
      const requestedPage = Math.max(1, Number(page || this.queuePage || 1))
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      if (this._actionContext !== context) {
        this._actionContext = context
        this._writeEpoch = (this._writeEpoch || 0) + 1
        this.acting = false
        this.tasks = []
        this.detailId = ''
        this.queuePage = 1
        this.queueTotal = 0
        this.queueHasMore = false
        this.restoreReviewAttempts(context)
      } else if (this.recoveryStorageBlocked) this.restoreReviewAttempts(context)
      this.state = 'loading'
      try {
        const d = await teacherApi.getAcademicMyTasks({
          page: this.targetTaskId ? 1 : requestedPage,
          pageSize: this.queuePageSize,
          taskId: this.targetTaskId || undefined
        })
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        const rows = (d && (d.list || d.items)) || []
        if (this.targetTaskId && !rows.some((row) => this.isTarget(row))) {
          toast('该教学任务不存在、已处理或不在当前身份范围内')
          this.targetTaskId = ''
          this.detailId = ''
          this.tasks = []
          this.queuePage = 1
          this.queueTotal = 0
          this.queueHasMore = false
          this.state = 'loading'
          this.load(1)
          return
        }
        this.tasks = this.focusTarget(rows)
        this.queueTotal = Number((d && d.total) || 0)
        this.queuePage = Number((d && d.page) || requestedPage)
        this.queuePageSize = Number((d && d.pageSize) || this.queuePageSize || 20)
        this.queueHasMore = !!(d && d.hasMore)
        this.observeReviewAttempts(this.tasks)
        if (this.detailId && !this.tasks.some((row) => String(row.taskId) === this.detailId)) this.detailId = ''
        this.state = 'ready'
      } catch (error) {
        if (this._pageActive && this._loadEpoch === epoch && this.contextKey() === context) {
          if (isApprovalForbidden(error)) this.clearPrivateReview()
          this.state = normalizeError(error).pageState || 'error'
        }
      } finally { if (done) done() }
    },
    submitAction(taskId, action, reason, context, writeEpoch, successLabel, before) {
      const key = this.reviewKey(taskId, context)
      const storedAttempt = approvalContextKey.createAttempt(RECOVERY_SCOPE, context, taskId, action, before)
      if (!approvalContextKey.persistAttempt(RECOVERY_SCOPE, storedAttempt)) {
        this.recoveryStorageBlocked = true
        this.acting = false
        toast('本机无法保存待核对记录，本次命令未发送')
        return
      }
      this.reviewAttempts[key] = { context, objectId: String(storedAttempt.objectId), action, epoch: writeEpoch, state: 'SENDING', observation: '' }
      teacherApi.actAcademicTask(taskId, action, reason)
        .then((receipt) => {
          if (!hasExplicitApprovalReceipt(receipt, taskId, ['taskId', 'id']) || !approvalReceiptChanged(receipt, before)) {
            const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, receipt)
            if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
            if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
            if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) { toast('任务结果待确认，请只读核对；不会自动重发原命令'); this.load() }
            return
          }
          if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, taskId, storedAttempt)) {
            if (this.reviewAttempts[key]) this.reviewAttempts[key].state = 'UNKNOWN'
            if (this.contextKey() === context) this.recoveryStorageBlocked = true
            if (this._pageActive && this.contextKey() === context) toast('已收到回执，但本机待核对记录无法清除，请勿重复提交')
            return
          }
          delete this.reviewAttempts[key]
          if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
          toast(successLabel); this.targetTaskId = ''; this.load()
        })
        .catch((error) => {
          if (isApprovalConflict(error)) {
            if (!approvalContextKey.clearAttempt(RECOVERY_SCOPE, context, taskId, storedAttempt)) {
              if (this.reviewAttempts[key]) this.reviewAttempts[key].state = 'UNKNOWN'
              if (this.contextKey() === context) this.recoveryStorageBlocked = true
              if (this._pageActive && this.contextKey() === context) toast('状态冲突已返回，但本机待核对记录无法清除')
              return
            }
            delete this.reviewAttempts[key]
            if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) { toast((error && error.message) || '任务状态已变化，正在刷新'); this.load() }
            return
          }
          const saved = approvalContextKey.persistReceipt(RECOVERY_SCOPE, storedAttempt, error)
          if (this.reviewAttempts[key] && this.reviewAttempts[key].epoch === writeEpoch) this.reviewAttempts[key].state = 'UNKNOWN'
          if (!saved && this.contextKey() === context) this.recoveryStorageBlocked = true
          if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
          if (isApprovalForbidden(error)) this.clearPrivateReview()
          toast('任务结果待确认，请只读核对；不会自动重发原命令')
        })
        .finally(() => { if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.acting = false })
    },
    doConfirm(t) {
      if (this._actionContext && this._actionContext !== this.contextKey()) { this.load(); return }
      if (this.acting || this.reviewLocked(t)) return
      const taskId = String(t.taskId || '')
      const context = this.contextKey()
      const epoch = this._loadEpoch
      const snapshot = JSON.stringify(t)
      const courseName = t.courseName || '本课程'
      uni.showModal({
        title: '确认教学任务', content: `确认承担「${courseName}」${t.teachingClassName || ''}的教学任务？`,
        success: (r) => {
          if (!r.confirm || !this._pageActive || this.acting || this._loadEpoch !== epoch || this.contextKey() !== context || !this.tasks.includes(t) || JSON.stringify(t) !== snapshot || String(t.taskId || '') !== taskId) return
          const writeEpoch = (this._writeEpoch || 0) + 1
          this._writeEpoch = writeEpoch
          this.acting = true
          this.submitAction(taskId, 'CONFIRM', '', context, writeEpoch, '已确认', t)
        }
      })
    },
    doReject(t) {
      if (this._actionContext && this._actionContext !== this.contextKey()) { this.load(); return }
      if (this.acting || this.reviewLocked(t)) return
      const taskId = String(t.taskId || '')
      const context = this.contextKey()
      const epoch = this._loadEpoch
      const snapshot = JSON.stringify(t)
      uni.showModal({
        title: '退回教学任务', editable: true, placeholderText: '请填写退回原因（≥5 字）', content: '',
        success: (r) => {
          if (!r.confirm || !this._pageActive || this.acting || this._loadEpoch !== epoch || this.contextKey() !== context || !this.tasks.includes(t) || JSON.stringify(t) !== snapshot || String(t.taskId || '') !== taskId) return
          const reason = (r.content || '').trim()
          if (reason.length < 5) { toast('退回原因至少 5 个字'); return }
          const writeEpoch = (this._writeEpoch || 0) + 1
          this._writeEpoch = writeEpoch
          this.acting = true
          this.submitAction(taskId, 'REJECT', reason, context, writeEpoch, '已退回', t)
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
.at__pending { margin: 12px; display: flex; flex-direction: column; gap: 8px; }
.at__pending-note { color: var(--text-secondary); font-size: 12px; }
.at__detail-head, .at__pager { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 16px; }
.at__pager { margin-top: 16px; font-size: 12px; color: var(--text-secondary); }
.at__object-id { color: var(--text-tertiary); font-size: 12px; padding: 8px 0; border-bottom: 1px solid var(--border-light); }
.at { display: flex; flex-direction: column; gap: var(--space-2); }
.at.is-target { border: 1px solid var(--teacher-500); box-shadow: 0 0 0 2px var(--teacher-50); }
.at__target { color: var(--teacher-700); font-size: var(--font-size-xs); font-weight: 600; }
.at__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.at__row { display: flex; gap: var(--space-3); }
.at__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 56px; flex-shrink: 0; }
.at__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.at__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.at__reject::after { border: none; }
.at__confirm { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.at__confirm::after { border: none; }
</style>
