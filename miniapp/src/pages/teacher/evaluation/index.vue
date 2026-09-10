<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="submitTarget ? '填写教学评价' : appealTarget ? '评价结果申诉' : '教学评价'" subtitle="自评 · 同行 · 督导" :before-back="backToEvaluation" show-back />

    <view class="ev__tabs" v-if="!submitTarget && !appealTarget">
      <view class="ev__tab" :class="{ 'is-on': tab === 'tasks' }" @click="switchTab('tasks')">
        我的任务<text v-if="tasks.length" class="ev__tab-badge">{{ tasks.length }}</text>
        <text v-if="tab === 'tasks'" class="ev__tab-u" />
      </view>
      <view class="ev__tab" :class="{ 'is-on': tab === 'results' }" @click="switchTab('results')">
        我的结果
        <text v-if="tab === 'results'" class="ev__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="activeState" @retry="loadActive">
      <!-- 我的任务 -->
      <view class="page-pad" v-if="tab === 'tasks'">
        <template v-if="!submitTarget">
        <view class="card ev__type-row">
          <text class="ev__row-k">评价类型</text>
          <picker class="ev__picker" mode="selector" :disabled="submitting || acting" :range="typeLabels" :value="typeIndex" @change="onType">
            <view class="ev__pick-val">{{ typeLabels[typeIndex] }}<text class="ev__arrow">▾</text></view>
          </picker>
        </view>

        <MobileGlobalState v-if="!tasks.length" state="empty" :title="taskError || '暂无待评价任务'"
          :description="taskError ? '请下拉重试或切换评价类型。' : '轮到你评价的任务会出现在这里。'" />
        <view class="stack" v-else>
          <view v-for="t in visibleTasks" :key="t.taskId" class="card ev">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ t.courseName || '—' }}</text>
                <text class="ev__sub">{{ t.teacherName || '' }}</text>
              </view>
              <MobileStatusTag :label="t.status === 'SUBMITTED' ? '已提交' : '待提交'"
                :type="t.status === 'SUBMITTED' ? 'success' : 'warning'" />
            </view>
            <view class="ev__evidence">
              <text class="t-xs">评价身份：{{ typeLabels[typeIndex] }}</text>
              <text class="t-xs">批次状态：{{ t.batchStatus || '—' }}</text>
            </view>
            <view class="ev__actions" v-if="t.status !== 'SUBMITTED'">
              <button class="btn btn-primary flex-1" :disabled="acting || submitting" @click="openSubmit(t)">去评价</button>
            </view>
          </view>
        </view>

        <view v-if="tasks.length > 20" class="ev__pages">
          <button class="btn btn-ghost" :disabled="taskPageIndex === 0" @click="taskPage = taskPageIndex - 1">上一组</button>
          <text>{{ taskPageIndex + 1 }} / {{ Math.ceil(tasks.length / 20) }}</text>
          <button class="btn btn-ghost" :disabled="(taskPageIndex + 1) * 20 >= tasks.length" @click="taskPage = taskPageIndex + 1">下一组</button>
        </view>
        </template>
        <!-- 提交表单 -->
        <template v-if="submitTarget">
          <button class="btn btn-ghost" :disabled="submitting" @click="backToEvaluation">‹ 返回评价任务</button>
          <view v-if="hasUnknownWrite('evaluation', submitTarget.taskId)" class="ev__uncertain">本次提交未收到明确回执。已停止重复提交，请下拉刷新并核对任务状态。</view>
          <view class="card ev__object"><text>评价人身份：{{ typeLabels[typeIndex] }}</text><text>评价对象：{{ submitTarget.teacherName || '未提供' }}</text><text>任务编号：{{ submitTarget.taskId }}</text></view>
          <view class="section-head"><text class="section-head__title">评价「{{ submitTarget.courseName }}」</text></view>
          <view class="card ev__form">
            <view class="ev__row">
              <text class="ev__row-k">评分</text>
              <input class="ev__input" type="number" :disabled="submitting" v-model="score" placeholder="0-100" />
            </view>
            <view class="ev__row" style="border-bottom:none; align-items:flex-start;">
              <text class="ev__row-k" style="padding-top:10px;">评语</text>
              <textarea class="ev__textarea" :disabled="submitting" v-model="comment" placeholder="可选，填写具体评价意见" />
            </view>
          </view>
          <MobileSafeAreaBar>
            <button class="btn btn-ghost flex-1" :disabled="submitting" @click="backToEvaluation">取消</button>
            <button class="btn btn-primary flex-1" :disabled="submitting || hasUnknownWrite('evaluation', submitTarget.taskId)" @click="doSubmitEvaluation">{{ submitting ? '提交中…' : hasUnknownWrite('evaluation', submitTarget.taskId) ? '等待核对结果' : '提交评价' }}</button>
          </MobileSafeAreaBar>
        </template>
      </view>

      <!-- 我的结果 -->
      <view class="page-pad" v-if="tab === 'results'">
        <template v-if="!appealTarget">
        <MobileGlobalState v-if="!results.length" state="empty" title="暂无已发布结果"
          description="批次出结果并发布后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="r in visibleResults" :key="r.resultId" class="card ev">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ r.courseName || '—' }}</text>
                <text class="ev__sub">{{ r.batchName || '' }}</text>
              </view>
              <text class="ev__score">{{ r.studentAvg != null ? r.studentAvg : '—' }}</text>
            </view>
            <view class="ev__row"><text class="ev__row-k">等级</text><text class="flex-1 t-sm">{{ levelLabel(r.level) }}（{{ r.studentCount }} 人评）</text></view>
            <view class="ev__actions">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doAppeal(r)">对结果申诉</button>
            </view>
          </view>
        </view>
        </template>
        <template v-if="!appealTarget && results.length > 20">
          <view class="ev__pages">
            <button class="btn btn-ghost" :disabled="resultPageIndex === 0" @click="resultPage = resultPageIndex - 1">上一组</button>
            <text>{{ resultPageIndex + 1 }} / {{ Math.ceil(results.length / 20) }}</text>
            <button class="btn btn-ghost" :disabled="(resultPageIndex + 1) * 20 >= results.length" @click="resultPage = resultPageIndex + 1">下一组</button>
          </view>
        </template>
        <template v-if="appealTarget">
          <button class="btn btn-ghost" :disabled="acting" @click="backToEvaluation">‹ 返回评价结果</button>
          <view v-if="hasUnknownWrite('appeal', appealTarget.resultId)" class="ev__uncertain">申诉提交结果未确认。已停止重复提交，请刷新结果后核对学校的复核记录。</view>
          <view class="card ev__object">
            <text class="t-md t-bold">{{ appealTarget.courseName || '课程名称未提供' }}</text>
            <text>{{ appealTarget.batchName || '评价批次未提供' }}</text>
            <view class="row-between"><text>已发布得分</text><text class="ev__score">{{ appealTarget.studentAvg == null ? '—' : appealTarget.studentAvg }}</text></view>
            <view class="row-between"><text>评价等级</text><text>{{ levelLabel(appealTarget.level) }}</text></view>
            <text>结果编号 {{ appealTarget.resultId }}</text>
          </view>
          <view class="card ev__object">
            <text class="t-md t-bold">申诉理由</text>
            <textarea class="ev__appeal-note" :disabled="acting" v-model="appealReason" maxlength="1000" placeholder="请说明需要复核的具体事项与依据，至少 5 个字" />
            <text class="ev__sub">提交后由学校按评价复核流程处理。</text>
          </view>
          <MobileSafeAreaBar><button class="btn btn-primary flex-1" :disabled="acting || appealReason.trim().length < 5 || hasUnknownWrite('appeal', appealTarget.resultId)" @click="submitAppeal">{{ acting ? '提交中…' : hasUnknownWrite('appeal', appealTarget.resultId) ? '等待核对结果' : '提交结果申诉' }}</button></MobileSafeAreaBar>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { useSessionStore } from '@/stores/session'
import { toast } from '@/utils/nav'
import { beginPersistentWrite, clearPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, listPersistentWrites, persistWriteAck, teacherWriteContext } from '../academic-affairs/write-result'

const TYPES = [{ key: 'SELF', label: '自评' }, { key: 'PEER', label: '同行评价' }, { key: 'SUPERVISOR', label: '督导评价' }]
const LEVEL_LABELS = { EXCELLENT: '优秀', GOOD: '良好', QUALIFIED: '合格', UNQUALIFIED: '不合格' }

export default {
  data() {
    return {
      tab: 'tasks', tasksState: 'loading', resultsState: 'idle', tasks: [], results: [], taskError: '', taskPage: 0, resultPage: 0,
      typeIndex: 0, acting: false, submitTarget: null, score: '', comment: '', submitting: false, appealTarget: null, appealReason: '', unknownWrites: {}, writeStorageBlocked: false
    }
  },
  onLoad() { this._pageActive = true; this._viewContext = this.contextKey(); this.syncUnknownWrites(); this.loadTasks() },
  onShow() {
    this._pageActive = true
    this.syncUnknownWrites()
    const context = this.contextKey()
    if (this._viewContext !== context) {
      this._viewContext = context
      this._submitEpoch = (this._submitEpoch || 0) + 1
      this._appealEpoch = (this._appealEpoch || 0) + 1
      this.submitTarget = null
      this.appealTarget = null
      this.appealReason = ''
      this.tasks = []
      this.results = []
      this.taskPage = 0
      this.resultPage = 0
      this.score = ''; this.comment = ''
      this.syncUnknownWrites()
      this.resultsState = 'idle'
      this._needsRefresh = false
      this.tasksState = 'idle'
      this.submitting = false
      this.acting = false
      this.loadActive()
      return
    }
    if (!this._needsRefresh) return
    this._needsRefresh = false
    this.loadActive()
  },
  onHide() {
    this._pageActive = false
    this._needsRefresh = true
    this._tasksEpoch = (this._tasksEpoch || 0) + 1
    this._resultsEpoch = (this._resultsEpoch || 0) + 1
  },
  onUnload() {
    this._pageActive = false
    this._tasksEpoch = (this._tasksEpoch || 0) + 1
    this._resultsEpoch = (this._resultsEpoch || 0) + 1
  },
  onPullDownRefresh() {
    if (this.activeState === 'loading') { uni.stopPullDownRefresh(); return }
    this.loadActive(() => uni.stopPullDownRefresh())
  },
  computed: {
    taskPageIndex() { return Math.min(this.taskPage, Math.max(0, Math.ceil(this.tasks.length / 20) - 1)) },
    resultPageIndex() { return Math.min(this.resultPage, Math.max(0, Math.ceil(this.results.length / 20) - 1)) },
    visibleTasks() { return this.tasks.slice(this.taskPageIndex * 20, (this.taskPageIndex + 1) * 20) },
    visibleResults() { return this.results.slice(this.resultPageIndex * 20, (this.resultPageIndex + 1) * 20) },
    typeLabels() { return TYPES.map((t) => t.label) },
    activeState() { return this.tab === 'tasks' ? this.tasksState : this.resultsState }
  },
  onBackPress() { if (!this.submitTarget && !this.appealTarget) return false; this.backToEvaluation(); return true },
  methods: {
    async backToEvaluation() {
      if (!this.submitTarget && !this.appealTarget) return true
      if (this.submitting || this.acting) return false
      const target = this.submitTarget || this.appealTarget
      const context = this.contextKey()
      const draft = JSON.stringify([this.score, this.comment, this.appealReason])
      const hasDraft = this.submitTarget ? !!(this.score || this.comment) : !!this.appealReason
      if (hasDraft) {
        const leave = await new Promise((resolve) => uni.showModal({ title: '返回列表', content: '当前填写内容尚未提交，确认放弃本次填写？', success: (r) => resolve(!!r.confirm), fail: () => resolve(false) }))
        if (!leave || !this._pageActive || this.submitting || this.acting || this.contextKey() !== context || (this.submitTarget || this.appealTarget) !== target || JSON.stringify([this.score, this.comment, this.appealReason]) !== draft) return false
      }
      this.submitTarget = null
      this.appealTarget = null
      this.score = ''; this.comment = ''; this.appealReason = ''
      return false
    },
    contextKey() {
      return teacherWriteContext(useSessionStore())
    },
    levelLabel(l) { return LEVEL_LABELS[l] || l || '—' },
    writeKey(action, objectId) { return `${action}|${String(objectId || '')}` },
    hasUnknownWrite(action, objectId) { return this.writeStorageBlocked || !!this.unknownWrites[this.writeKey(action, objectId)] },
    syncUnknownWrites(context = this.contextKey()) { const result = listPersistentWrites(context); this.writeStorageBlocked = !result.ok; this.unknownWrites = result.ok ? Object.fromEntries(result.records.map((row) => [this.writeKey(row.action, row.objectId), row])) : {}; return result },
    beginWrite(context, action, objectId) { const result = beginPersistentWrite(context, action, objectId); this.syncUnknownWrites(); if (!result.ok) toast(result.storageError ? '无法安全保存待核对记录，本次未提交' : '该操作正在等待正式记录核对'); return result.ok },
    ackWrite(context, action, objectId, ack) { const ok = persistWriteAck(context, action, objectId, ack); this.syncUnknownWrites(); return ok },
    clearWrite(context, action, objectId) { const ok = clearPersistentWrite(context, action, objectId); this.syncUnknownWrites(); return ok },
    reconcileEvaluationTasks(rows) {
      const pending = listPersistentWrites(this.contextKey())
      if (!pending.ok) { this.syncUnknownWrites(); return }
      const done = new Set(['SUBMITTED', 'COMPLETED', 'FINISHED'])
      pending.records.forEach((record) => {
        if (record.action === 'evaluation' && record.state === 'ACK' && rows.some((row) => String(row.taskId || '') === record.objectId && done.has(String(row.status || '').toUpperCase()))) this.clearWrite(record.context, record.action, record.objectId)
      })
    },
    reconcileAppeals(rows) {
      const pending = listPersistentWrites(this.contextKey())
      if (!pending.ok) { this.syncUnknownWrites(); return }
      pending.records.forEach((record) => {
        if (record.action !== 'appeal' || record.state !== 'ACK') return
        const row = rows.find((item) => String(item.resultId || '') === record.objectId)
        const appealStatus = String(row && (row.appealStatus || row.reviewStatus) || '').toUpperCase()
        const appealId = String(row && (row.appealId || row.reviewId) || '')
        if (row && ((record.ackId && appealId === record.ackId) || ['PENDING', 'SUBMITTED', 'PROCESSING', 'APPROVED', 'REJECTED'].includes(appealStatus))) this.clearWrite(record.context, record.action, record.objectId)
      })
    },
    switchTab(t) {
      if (this.submitting || this.acting) { toast('正在提交，请稍候'); return }
      this.tab = t
      this.submitTarget = null
      if (t === 'results' && this.resultsState === 'idle') this.loadResults()
      if (t === 'tasks' && this.tasksState === 'idle') this.loadTasks()
    },
    onType(e) {
      if (this.submitting || this.acting) return
      this.typeIndex = Number(e.detail.value)
      this.taskPage = 0
      this.submitTarget = null
      this.loadTasks()
    },
    loadActive(done) {
      if (this.tab === 'results') this.loadResults(done)
      else this.loadTasks(done)
    },
    async loadTasks(done) {
      const epoch = (this._tasksEpoch || 0) + 1
      this._tasksEpoch = epoch
      const context = this.contextKey()
      const evaluatorType = TYPES[this.typeIndex].key
      this.taskError = ''
      this.tasksState = 'loading'
      try {
        const d = await teacherApi.getAcademicEvaluationMyTasks(evaluatorType)
        if (!this._pageActive || this._tasksEpoch !== epoch || this.contextKey() !== context || TYPES[this.typeIndex].key !== evaluatorType) return
        this.tasks = (d && d.list) || []
        this.reconcileEvaluationTasks(this.tasks)
        this.tasksState = 'ready'
      } catch (e) {
        if (!this._pageActive || this._tasksEpoch !== epoch || this.contextKey() !== context || TYPES[this.typeIndex].key !== evaluatorType) return
        this.tasks = []
        if (isForbiddenResponse(e)) { this.submitTarget = null; this.score = ''; this.comment = '' }
        this.taskError = (e && e.message) || '任务加载失败'
        this.tasksState = 'error'
      } finally { if (done) done() }
    },
    async loadResults(done) {
      const epoch = (this._resultsEpoch || 0) + 1
      this._resultsEpoch = epoch
      const context = this.contextKey()
      this.resultsState = 'loading'
      try {
        const d = await teacherApi.getAcademicEvaluationResults()
        if (!this._pageActive || this._resultsEpoch !== epoch || this.contextKey() !== context) return
        this.results = (d && d.list) || []
        this.reconcileAppeals(this.results)
        this.resultsState = 'ready'
      } catch (e) {
        if (!this._pageActive || this._resultsEpoch !== epoch || this.contextKey() !== context) return
        this.results = []
        if (isForbiddenResponse(e)) { this.appealTarget = null; this.appealReason = '' }
        this.resultsState = 'error'
        toast((e && e.message) || '结果加载失败')
      } finally { if (done) done() }
    },
    openSubmit(t) { if (this.submitting || this.acting) return; this.submitTarget = t; this.score = ''; this.comment = '' },
    async doSubmitEvaluation() {
      if (this.submitting || !this.submitTarget || this.hasUnknownWrite('evaluation', this.submitTarget.taskId)) return
      const score = this.score === '' ? null : Number(this.score)
      if (score === null || Number.isNaN(score) || score < 0 || score > 100) {
        toast('请填写 0-100 的评分'); return
      }
      const taskId = String(this.submitTarget.taskId || '')
      const context = this.contextKey()
      const comment = this.comment.trim() || null
      const tasksEpoch = this._tasksEpoch
      const target = this.submitTarget
      const snapshot = JSON.stringify(target)
      const confirmed = await new Promise((resolve) => uni.showModal({
        title: '提交教学评价',
        content: `确认提交「${this.submitTarget.courseName || '本课程'}」的评价？提交后不可再次修改。`,
        confirmText: '确认提交',
        success: (result) => resolve(!!result.confirm),
        fail: () => resolve(false)
      }))
      if (!confirmed || !this._pageActive || this.submitting || !taskId || this.contextKey() !== context || String(this.submitTarget && this.submitTarget.taskId || '') !== taskId) return
      if (Number(this.score) !== score || (this.comment.trim() || null) !== comment) { toast('评价内容已变化，请重新确认'); return }
      if (this._tasksEpoch !== tasksEpoch || !this.tasks.includes(target) || this.submitTarget !== target || JSON.stringify(target) !== snapshot) { toast('评价任务已变化，请重新打开'); return }
      if (!this.beginWrite(context, 'evaluation', taskId)) return
      const epoch = (this._submitEpoch || 0) + 1
      this._submitEpoch = epoch
      this.submitting = true
      teacherApi.submitAcademicEvaluation(taskId, {
        answers: [], objectiveScore: score, comment
      }).then((ack) => {
        this.ackWrite(context, 'evaluation', taskId, { ackId: ack && (ack.submissionId || ack.evaluationId || ack.id), parentId: taskId })
        if (!this._pageActive || this._submitEpoch !== epoch || this.contextKey() !== context || String(this.submitTarget && this.submitTarget.taskId || '') !== taskId) return
        toast('已提交')
        this.submitTarget = null
        this.loadTasks()
      }).catch((e) => {
        if (isExplicitWriteRejection(e)) this.clearWrite(context, 'evaluation', taskId)
        if (!this._pageActive || this._submitEpoch !== epoch || this.contextKey() !== context) return
        const code = e && String(e.code)
        if (code === 'DATA_CONFLICT' || isExplicitWriteRejection(e)) toast((e && e.message) || '该任务已提交，不可重复提交')
        else { toast('提交结果未确认，已停止重复提交；请刷新后核对任务状态') }
      }).finally(() => { if (this._submitEpoch === epoch && this.contextKey() === context) this.submitting = false })
    },
    doAppeal(r) {
      if (this.acting || this.submitting || !this.results.includes(r)) return
      this.appealTarget = r
      this.appealReason = ''
    },
    async submitAppeal() {
      const target = this.appealTarget
      const reason = this.appealReason.trim()
      if (!target || this.acting || reason.length < 5 || this.hasUnknownWrite('appeal', target.resultId)) return
      const resultId = String(target.resultId || '')
      const context = this.contextKey()
      const resultsEpoch = this._resultsEpoch
      const snapshot = JSON.stringify(target)
      const confirmed = await new Promise((resolve) => uni.showModal({
        title: '提交结果申诉', content: '确认提交本条评价结果的复核申请？',
        success: (r) => resolve(!!r.confirm), fail: () => resolve(false)
      }))
      if (!confirmed || !this._pageActive || this.acting || !resultId || this.contextKey() !== context || this.appealTarget !== target || this.appealReason.trim() !== reason || this._resultsEpoch !== resultsEpoch || !this.results.includes(target) || JSON.stringify(target) !== snapshot) return
      if (!this.beginWrite(context, 'appeal', resultId)) return
      const epoch = (this._appealEpoch || 0) + 1
      this._appealEpoch = epoch
      this.acting = true
      try {
        const ack = await teacherApi.appealAcademicEvaluation(resultId, reason)
        this.ackWrite(context, 'appeal', resultId, { ackId: ack && (ack.appealId || ack.reviewId || ack.id), parentId: resultId })
        if (!this._pageActive || this._appealEpoch !== epoch || this.contextKey() !== context) return
        toast('申诉已提交')
        this.appealTarget = null
        this.appealReason = ''
        this.loadResults()
      } catch (e) {
        if (isExplicitWriteRejection(e)) this.clearWrite(context, 'appeal', resultId)
        if (this._pageActive && this._appealEpoch === epoch && this.contextKey() === context) {
          if (isExplicitWriteRejection(e)) toast((e && e.message) || '申诉未受理')
          else { toast('申诉结果未确认，已停止重复提交；请刷新后核对结果') }
        }
      } finally { if (this._appealEpoch === epoch && this.contextKey() === context) this.acting = false }
    }
  }
}
</script>

<style scoped>
.ev__pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0; }
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.ev__object { display: flex; flex-direction: column; gap: 14px; margin: 16px 0; font-size: 14px; }
.ev__appeal-note { width: 100%; min-height: 160px; box-sizing: border-box; padding: 12px; border: 1px solid var(--border-light); border-radius: 12px; font-size: 14px; }
.ev__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ev__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ev__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ev__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ev__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ev__type-row { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.ev__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); flex-shrink: 0; width: 64px; }
.ev__picker { flex: 1; }
.ev__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ev__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.ev { display: flex; flex-direction: column; gap: var(--space-2); }
.ev__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ev__evidence { display: flex; justify-content: space-between; gap: var(--space-2); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); background: var(--gray-50); color: var(--text-secondary); }
.ev__uncertain { margin: 12px 0; padding: 10px 12px; border-radius: 10px; background: var(--warning-50); color: var(--warning-700); font-size: 13px; line-height: 1.5; }
.ev__score { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--teacher-600); }
.ev__row { display: flex; align-items: center; gap: var(--space-3); min-height: 44px; border-bottom: 1px solid var(--border-light); }
.ev__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ev__form { display: flex; flex-direction: column; }
.ev__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ev__textarea { flex: 1; min-height: 72px; font-size: var(--font-size-base); color: var(--text-primary); padding: 10px 0; }
</style>
