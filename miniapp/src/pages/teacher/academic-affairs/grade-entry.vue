<template>
  <view class="page-wrap">
    <MobileNavBar
      variant="teacher"
      :title="reviewMode ? '提交前核验' : active ? active.courseName : '成绩录入'"
      :subtitle="active ? ratioText : '我的授课任务'"
      :before-back="beforePageBack"
      show-back
    />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="!active && loaded">
        <MobileGlobalState v-if="!tasks.length" state="empty" title="暂无成绩录入任务" description="教务处下达录入任务后会显示在这里。" />
        <view class="list-group" v-else>
          <view v-for="t in tasks" :key="t.gradeTaskId" class="list-row" @click="openTask(t)">
            <view class="flex-1">
              <text class="t-md">{{ t.courseName || '—' }}</text>
              <text class="ge__sub">{{ t.termCode || '—' }} · {{ ratioOf(t) }} · 及格线{{ t.passLine }}</text>
              <text v-if="t.returnReason" class="ge__reason">退回原因：{{ t.returnReason }}</text>
            </view>
            <MobileStatusTag :status="t.status" />
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="active">
        <view class="ge__task-head">
          <text class="ge__back" @click="backToTasks">‹ 返回任务列表</text>
          <text v-if="dirtyCount" class="ge__dirty">{{ dirtyCount }}人待保存</text>
          <text v-else-if="roster.length" class="ge__saved">服务器已同步</text>
        </view>

        <view v-if="entryMode === 'COMPONENTS' && (hasGradePending || dynamicNeedsReview)" class="ge__pending">
          <text>{{ writeStorageBlocked ? '本机无法安全读取待核对记录，请先检查小程序存储后重试。' : dynamicNeedsReview ? '正式成绩已变化，请读取最新成绩并核对差异；当前修改仍保留。' : '上次保存或提交结果仍待服务器核对，已停止重复提交。' }}</text>
          <button v-if="!writeStorageBlocked" class="btn btn-ghost" :disabled="rosterState === 'loading' || saving !== null || savingAll || submitting" @click="recheckDynamicState">核对服务器结果</button>
        </view>

        <view v-if="canEdit && roster.length && !reviewMode" class="ge__notice">
          <template v-if="entryMode === 'COMPONENTS'">{{ dynamicNotice }}</template>
          <template v-else>
          正常成绩填写0—100整数；缺考、缓考、免修、作弊请选择特殊状态，系统不会把它们误记为0分。
          修改仅保留在当前页面内存中，点击“保存全部”后才写入学校服务器。
          </template>
        </view>
        <AppInlineAlert
          v-else-if="active && !canEdit"
          type="warning"
          :description="`任务当前为${statusLabel(active.status)}，移动端只读；已提交或已发布成绩不得直接修改。`"
        />

        <view v-if="qualityReport && reviewMode" class="ge__quality" :class="qualityReport.canSubmit ? 'is-ready' : 'is-blocked'">
          <text class="ge__review-course">{{ active.courseName }} · {{ active.termCode || '学期待确认' }}</text>
          <view class="ge__quality-head">
            <text class="ge__quality-title">{{ qualityReport.canSubmit ? '提交检查通过' : '提交检查未通过' }}</text>
            <text class="ge__quality-state">{{ qualityReport.canSubmit ? '可提交' : '需处理' }}</text>
          </view>
          <text class="ge__quality-summary">{{ qualityReport.summary }}</text>
          <view class="ge__quality-stats">
            <text>名单 {{ qualityReport.rosterCount }}</text>
            <text>未录 {{ qualityReport.missingCount }}</text>
            <text>未录全 {{ qualityReport.incompleteCount }}</text>
            <text>特殊状态 {{ qualityReport.specialCount }}</text>
          </view>
          <text v-if="qualityReport.deadline" class="ge__deadline" :class="{ 'is-overdue': qualityReport.isOverdue }">
            录入截止：{{ formatDeadline(qualityReport.deadline) }}{{ qualityReport.isOverdue ? '（已截止）' : '' }}
          </text>
          <view v-if="qualityReport.issues && qualityReport.issues.length" class="ge__issues">
            <text v-for="issue in qualityReport.issues.slice(0, 5)" :key="issue.studentId + issue.code" class="ge__issue">
              {{ issue.realName || issue.studentNo || issue.studentId }}：{{ issue.message }}
            </text>
            <text v-if="qualityReport.issues.length > 5" class="ge__issue-more">另有 {{ qualityReport.issues.length - 5 }} 项，请继续核对名单。</text>
          </view>
        </view>

        <template v-if="!reviewMode">
        <MobileGlobalState v-if="rosterState === 'loading'" state="loading" />
        <MobileGlobalState v-else-if="rosterState === 'error'" state="error" title="名单加载失败" @retry="entryMode === 'COMPONENTS' ? recheckDynamicState() : openTask(active)" />
        <MobileGlobalState v-else-if="!roster.length" state="empty" title="暂无名单" :description="rosterNote" />
        <view class="list-group" v-else>
          <view v-for="s in visibleRoster" :key="s.studentId" class="list-row ge__row">
            <view class="flex-1 ge__student">
              <text class="t-md">{{ s.realName }}</text>
              <text class="ge__sub">
                {{ s.studentNo }}
                <template v-if="scoreOf(s).exceptionFlag !== 'NORMAL'"> · {{ exceptionLabel(scoreOf(s).exceptionFlag) }}</template>
                <template v-else-if="scoreOf(s).totalScore !== null && scoreOf(s).totalScore !== ''"> · 总评 {{ scoreOf(s).totalScore }}</template>
              </text>
              <text v-if="s.source === 'RECHECK'" class="ge__sub">复查更正：{{ s.prevTotalScore == null ? '原总评未提供' : '原总评 ' + s.prevTotalScore }} → {{ scoreOf(s).totalScore }}。分项保留原录入，总评以正式复查结果为准。</text>
              <text v-if="rowErrors[s.studentId]" class="ge__reason">{{ rowErrors[s.studentId] }}</text>
              <button v-if="entryMode === 'COMPONENTS' && scoreOf(s).conflictFormal" class="btn btn-ghost" @click="reviewDynamicConflict(s)">核对成绩差异</button>
            </view>
            <view class="ge__editor">
              <picker
                class="ge__picker"
                :disabled="!canEdit || submitting"
                :range="exceptionOptions"
                range-key="label"
                :value="exceptionIndex(scoreOf(s).exceptionFlag)"
                @change="changeException(s, $event)"
              >
                <view class="ge__picker-value" :class="{ 'is-special': scoreOf(s).exceptionFlag !== 'NORMAL' }">
                  {{ exceptionLabel(scoreOf(s).exceptionFlag) }}⌄
                </view>
              </picker>
              <view v-if="entryMode === 'COMPONENTS'" class="ge__scores ge__scores--dynamic" :class="{ 'is-disabled': scoreOf(s).exceptionFlag !== 'NORMAL' }">
                <view v-for="component in components" :key="component.code" class="ge__field">
                  <text class="ge__field-label">{{ component.name }} · {{ component.weight }}%</text>
                  <input class="ge__score-input" type="digit" v-model="scores[s.studentId].components[component.code]" :placeholder="component.required ? requiredLabel : optionalLabel" placeholder-class="ge__ph" :disabled="!canEdit || submitting || scoreOf(s).exceptionFlag !== 'NORMAL'" @input="markDirty(s.studentId)" @blur="validateStudent(s)" />
                </view>
                <button class="btn btn-ghost ge__save" :disabled="!canEdit || saving === s.studentId || savingAll || hasGradePending" @click="saveScore(s, true)">
                  {{ saving === s.studentId ? '…' : saveLabel }}
                </button>
              </view>
              <view v-else class="ge__scores" :class="{ 'is-disabled': scoreOf(s).exceptionFlag !== 'NORMAL' }">
                <view class="ge__field"><text class="ge__field-label">平时</text><input class="ge__score-input" type="number" v-model="scores[s.studentId].usualScore" placeholder="平时" placeholder-class="ge__ph" :disabled="!canEdit || submitting || scoreOf(s).exceptionFlag !== 'NORMAL'" @input="markDirty(s.studentId)" @blur="validateStudent(s)" /></view>
                <view class="ge__field" v-if="showMid"><text class="ge__field-label">期中</text><input class="ge__score-input" type="number" v-model="scores[s.studentId].midtermScore" placeholder="期中" placeholder-class="ge__ph" :disabled="!canEdit || submitting || scoreOf(s).exceptionFlag !== 'NORMAL'" @input="markDirty(s.studentId)" @blur="validateStudent(s)" /></view>
                <view class="ge__field"><text class="ge__field-label">期末</text><input class="ge__score-input" type="number" v-model="scores[s.studentId].finalScore" placeholder="期末" placeholder-class="ge__ph" :disabled="!canEdit || submitting || scoreOf(s).exceptionFlag !== 'NORMAL'" @input="markDirty(s.studentId)" @blur="validateStudent(s)" /></view>
                <button class="btn btn-ghost ge__save" :disabled="!canEdit || saving === s.studentId || savingAll" @click="saveScore(s, true)">
                  {{ saving === s.studentId ? '…' : '保存' }}
                </button>
              </view>
            </view>
          </view>
          <view v-if="(entryMode === 'COMPONENTS' ? rosterTotal : roster.length) > ROSTER_WINDOW" class="ge__load-more">
            <button class="btn btn-ghost" :disabled="entryMode === 'COMPONENTS' ? rosterPage <= 1 || savingAll : rosterStart === 0" @click="showPreviousRoster">上一组</button>
            <text v-if="entryMode === 'COMPONENTS'">{{ pageLabel }}</text>
            <text v-else>{{ rosterStart + 1 }}–{{ Math.min(visibleCount, roster.length) }} / {{ roster.length }}</text>
            <button class="btn btn-ghost" :disabled="entryMode === 'COMPONENTS' ? !rosterHasMore || savingAll : !hasMoreRoster" @click="showMoreRoster">下一组</button>
          </view>
        </view>

        </template>
        <MobileSafeAreaBar v-if="canEdit && !reviewMode">
          <button class="btn btn-ghost ge__save-all" :disabled="savingAll || submitting || !dirtyCount || hasGradePending" @click="saveAll">
            {{ savingAll ? '保存中…' : `保存全部${dirtyCount ? '（' + dirtyCount + '）' : ''}` }}
          </button>
          <button class="btn btn-primary flex-1" :disabled="submitting || savingAll || qualityLoading || saving !== null || hasGradePending" @click="reviewForSubmit">
            {{ qualityLoading ? '检查中…' : '提交前核验' }}
          </button>
        </MobileSafeAreaBar>
        <MobileSafeAreaBar v-if="canEdit && reviewMode">
          <button class="btn btn-ghost" :disabled="submitting" @click="reviewMode = false">返回录入</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || qualityLoading || !qualityReport || !qualityReport.canSubmit" @click="submitTask">{{ submitting ? '提交中…' : '提交学院审核' }}</button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
/** V2 R5 教师微信成绩录入：名单分组 + 内存编辑 + 整批事务保存 + 提交前质量报告。 */
import { teacherApi } from '@/services/teacherApi'
import { academicGradeEntryApi } from '@/services/academicGradeEntryApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { useSessionStore } from '@/stores/session'
import { beginPersistentWrite, clearPersistentWrite, getPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, listPersistentWrites, persistWriteAck, teacherWriteContext } from './write-result'

const EXCEPTION_OPTIONS = [
  { value: 'NORMAL', label: '正常' },
  { value: 'ABSENT', label: '缺考' },
  { value: 'DEFERRED', label: '缓考' },
  { value: 'EXEMPT', label: '免修' },
  { value: 'CHEAT', label: '作弊' }
]

const STATUS_LABELS = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', RETURNED: '已退回', SUBMITTED: '已提交',
  COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务审核中', PUBLISHED: '已发布', ARCHIVED: '已归档'
}
const ROSTER_WINDOW = 30
const COMPONENT_SAVE = 'GRADE_COMPONENT_BATCH_SAVE'
const COMPONENT_SUBMIT = 'GRADE_TASK_SUBMIT'
let commandSequence = 0

function nextCommandKey() {
  commandSequence += 1
  return `gmp_${Date.now().toString(36)}_${commandSequence.toString(36)}_${Math.random().toString(36).slice(2, 12)}`
}

export default {
  data() {
    return {
      tasks: [], loaded: false, state: 'loading', active: null, requestedTaskId: '',
      roster: [], rosterState: 'loading', rosterNote: '', scores: {},
      midtermRatio: 0, saving: null, savingAll: false, submitting: false,
      dirty: {}, rowErrors: {}, rowVersions: {}, editVersion: 0, exceptionOptions: EXCEPTION_OPTIONS,
      qualityReport: null, qualityLoading: false, reviewMode: false,
      draftTimer: null, draftSavedAt: '', draftRestoredCount: 0,
      visibleCount: ROSTER_WINDOW, ROSTER_WINDOW,
      entryMode: 'FIXED', components: [], gradeIdentity: null, dynamicCanWrite: true,
      rosterPage: 1, rosterTotal: 0, rosterHasMore: false, rosterVersionId: '',
      gradePendingWrites: {}, writeStorageBlocked: false, dynamicReadDenied: false, dynamicNeedsReview: false
    }
  },
  computed: {
    showMid() { return Number(this.midtermRatio || (this.active && this.active.midtermRatio) || 0) > 0 },
    canEdit() {
      const st = (this.active && this.active.status) || ''
      return ['NOT_STARTED', 'INPUTTING', 'RETURNED'].includes(st) && (this.entryMode !== 'COMPONENTS' || this.dynamicCanWrite)
    },
    ratioText() { return this.active ? this.ratioOf(this.active) : '' },
    dirtyCount() { return Object.values(this.dirty).filter(Boolean).length },
    rosterStart() { return Math.floor((this.visibleCount - 1) / ROSTER_WINDOW) * ROSTER_WINDOW },
    visibleRoster() { return this.entryMode === 'COMPONENTS' ? this.roster : this.roster.slice(this.rosterStart, this.visibleCount) },
    hasMoreRoster() { return this.entryMode === 'COMPONENTS' ? this.rosterHasMore : this.visibleCount < this.roster.length },
    hasGradePending() { return this.writeStorageBlocked || Object.keys(this.gradePendingWrites).length > 0 },
    pageLabel() { return `\u7b2c ${this.rosterPage} \u9875 · ${this.roster.length} \u4eba / \u5171 ${this.rosterTotal} \u4eba` },
    dynamicNotice() { return '\u6b63\u5f0f\u6210\u7ee9\u9879 0—100，\u6700\u591a\u4e24\u4f4d\u5c0f\u6570；\u7279\u6b8a\u72b6\u6001\u6e05\u7a7a\u5206\u9879。' },
    requiredLabel() { return '\u5fc5\u586b' },
    optionalLabel() { return '\u9009\u586b' },
    saveLabel() { return '\u4fdd\u5b58' }
  },
  onLoad(options = {}) {
    this._pageActive = true
    this._viewContext = this.contextKey()
    this.syncGradePending(this._viewContext)
    this.requestedTaskId = String(options.id || options.taskId || '')
    this.load()
  },
  onShow() {
    this._pageActive = true
    const context = this.contextKey()
    if (this._viewContext !== context) {
      this._viewContext = context
      this._writeEpoch = (this._writeEpoch || 0) + 1
      this.saving = null
      this.savingAll = false
      this.submitting = false
      this.reviewMode = false
      this.active = null
      this.requestedTaskId = ''
      this.roster = []
      this.scores = {}
      this.dirty = {}
      this.rowErrors = {}
      this.qualityReport = null
      this.entryMode = 'FIXED'
      this.dynamicCanWrite = true
      this.components = []
      this.gradeIdentity = null
      this.rosterPage = 1
      this.rosterTotal = 0
      this.rosterHasMore = false
      this.rosterVersionId = ''
      this.syncGradePending(context)
      this._needsRefresh = false
      this.load()
      return
    }
    if (!this._needsRefresh) return
    this._needsRefresh = false
    if (!this.active) this.load()
    else if (!this.dirtyCount) this.openTask(this.active)
  },
  onHide() {
    this._pageActive = false
    this._needsRefresh = true
    this._loadEpoch = (this._loadEpoch || 0) + 1
    this._rosterEpoch = (this._rosterEpoch || 0) + 1
    this._qualityEpoch = (this._qualityEpoch || 0) + 1
    this.qualityLoading = false
  },
  onUnload() {
    this._pageActive = false
    this._loadEpoch = (this._loadEpoch || 0) + 1
    this._rosterEpoch = (this._rosterEpoch || 0) + 1
    this._qualityEpoch = (this._qualityEpoch || 0) + 1
    if (this.draftTimer) clearTimeout(this.draftTimer)
  },
  onBackPress() {
    if (this.reviewMode && !this.submitting) { this.reviewMode = false; return true }
    if (!this.active) return false
    this.leaveActiveTask()
    return true
  },
  methods: {
    contextKey() {
      return teacherWriteContext(useSessionStore())
    },
    syncGradePending(context = this.contextKey(), taskId = String(this.active && this.active.gradeTaskId || '')) {
      const result = listPersistentWrites(context)
      this.writeStorageBlocked = !result.ok
      this.gradePendingWrites = result.ok
        ? Object.fromEntries(result.records.filter((row) => [COMPONENT_SAVE, COMPONENT_SUBMIT].includes(row.action) && (!taskId || row.objectId === taskId)).map((row) => [row.action, row]))
        : {}
      return result
    },
    expectedGradeIdentity() {
      const value = this.gradeIdentity || {}
      return {
        expectedTaskVersion: Number(value.expectedTaskVersion),
        expectedSchemeId: String(value.expectedSchemeId == null ? '' : value.expectedSchemeId),
        expectedSchemeVersion: Number(value.expectedSchemeVersion),
        rosterIdentity: { ...(value.rosterIdentity || {}) }
      }
    },
    reserveGradeCommand(action, taskId, context) {
      this.syncGradePending(context, taskId)
      if (this.hasGradePending) return null
      const requestKey = nextCommandKey()
      const result = beginPersistentWrite(context, action, taskId, { requestKey })
      this.syncGradePending(context, taskId)
      if (!result.ok) {
        toast(result.storageError ? '\u65e0\u6cd5\u5b89\u5168\u4fdd\u5b58\u5f85\u6838\u5bf9\u5f15\u7528，\u672c\u6b21\u672a\u63d0\u4ea4' : '\u539f\u547d\u4ee4\u6b63\u5728\u7b49\u5f85\u6838\u5bf9')
        return null
      }
      return result.record
    },
    dynamicGuardMatches(guard) {
      return !!guard && this._pageActive && this.contextKey() === guard.context
        && String(this.active && this.active.gradeTaskId || '') === guard.taskId
        && this._rosterEpoch === guard.rosterEpoch
        && this.rosterPage === guard.viewPage
    },
    assertDynamicFormal(formal, expected = {}) {
      const scheme = (formal && formal.scheme) || {}
      const rosterVersionId = String(formal && formal.rosterIdentity && formal.rosterIdentity.rosterVersionId || '')
      if (!formal || formal.entryMode !== 'COMPONENTS' || String(formal.gradeTaskId || '') !== String(expected.taskId || '')) throw new Error('DYNAMIC_ROSTER_MISMATCH')
      if (expected.rosterVersionId && rosterVersionId !== expected.rosterVersionId) throw new Error('DYNAMIC_ROSTER_VERSION_MISMATCH')
      if (expected.schemeId && String(scheme.schemeId == null ? '' : scheme.schemeId) !== expected.schemeId) throw new Error('DYNAMIC_SCHEME_MISMATCH')
      if (expected.schemeVersion != null && Number(scheme.schemeVersion) !== Number(expected.schemeVersion)) throw new Error('DYNAMIC_SCHEME_VERSION_MISMATCH')
      return true
    },
    clearDynamicPrivateState() {
      this.roster = []
      this.scores = {}
      this.dirty = {}
      this.rowVersions = {}
      this.rowErrors = {}
      this.qualityReport = null
      this.rosterState = 'error'
      this.rosterNote = '\u540d\u5355\u8bbf\u95ee\u6743\u9650\u5df2\u5931\u6548，\u8bf7\u8fd4\u56de\u540e\u91cd\u65b0\u8fdb\u5165'
      this.dynamicCanWrite = false
      this.dynamicReadDenied = true
    },
    async reconcileGradeCommands(formal, guard) {
      if (this.entryMode !== 'COMPONENTS' || !formal) return false
      const context = guard ? guard.context : this.contextKey()
      const taskId = String(formal.gradeTaskId || '')
      const activeGuard = guard || { context, taskId, rosterEpoch: this._rosterEpoch, viewPage: this.rosterPage }
      if (!this.dynamicGuardMatches(activeGuard)) return false
      const pending = listPersistentWrites(context)
      if (!pending.ok) { this.syncGradePending(context, taskId); return false }
      const confirmed = {}
      for (const record of pending.records.filter((row) => [COMPONENT_SAVE, COMPONENT_SUBMIT].includes(row.action) && row.objectId === taskId && row.requestKey)) {
        try {
          const receipt = await academicGradeEntryApi.componentCommandReceipt(taskId, record.action, record.requestKey)
          if (!this.dynamicGuardMatches(activeGuard)) return false
          const result = receipt && receipt.state === 'SUCCESS' && receipt.result
          if (!result || String(result.gradeTaskId || '') !== taskId) continue
          const receiptMatches = String(receipt.operation || '') === record.action && String(receipt.commandKey || '') === record.requestKey
          const resultTaskVersion = Number(result.taskVersion)
          const taskVersionOk = Number.isFinite(resultTaskVersion) && resultTaskVersion > 0 && Number(formal.taskVersion) >= resultTaskVersion
          const submitStateOk = record.action !== COMPONENT_SUBMIT || !['NOT_STARTED', 'INPUTTING', 'RETURNED'].includes(String(formal.status || ''))
          if (!receiptMatches || !taskVersionOk || !submitStateOk) continue
          const currentRecord = getPersistentWrite(context, record.action, taskId)
          if (currentRecord.ok && currentRecord.record && currentRecord.record.requestKey === record.requestKey && clearPersistentWrite(context, record.action, taskId)) confirmed[record.requestKey] = result
        } catch (error) {
          if (isForbiddenResponse(error) && this.dynamicGuardMatches(activeGuard)) this.clearDynamicPrivateState()
          return false
        }
      }
      if (this.dynamicGuardMatches(activeGuard)) this.syncGradePending(context, taskId)
      return confirmed
    },
    formatDeadline(value) { return String(value || '').slice(0, 16).replace('T', ' ') },
    async showMoreRoster() {
      if (this.entryMode !== 'COMPONENTS') { this.visibleCount = Math.min(this.roster.length, this.visibleCount + ROSTER_WINDOW); return }
      if (this.dirtyCount && !await this.saveAll()) return
      if (this.rosterHasMore) await this.loadDynamicPage(this.rosterPage + 1)
    },
    async showPreviousRoster() {
      if (this.entryMode !== 'COMPONENTS') { this.visibleCount = Math.max(ROSTER_WINDOW, this.rosterStart); return }
      if (this.dirtyCount && !await this.saveAll()) return
      if (this.rosterPage > 1) await this.loadDynamicPage(this.rosterPage - 1)
    },
    async recheckDynamicState() {
      if (!this.active || this.entryMode !== 'COMPONENTS' || this.writeStorageBlocked || this.saving !== null || this.savingAll || this.submitting) return false
      const task = this.active
      const taskId = String(task.gradeTaskId || '')
      const context = this.contextKey()
      const epoch = (this._rosterEpoch || 0) + 1
      this._rosterEpoch = epoch
      const guard = { context, taskId, rosterEpoch: epoch, viewPage: this.rosterPage }
      const expected = this.expectedGradeIdentity()
      this.rosterState = 'loading'
      try {
        const formal = await academicGradeEntryApi.componentRoster(taskId, { page: guard.viewPage, pageSize: ROSTER_WINDOW, expectedRosterVersionId: this.rosterVersionId })
        if (!this.dynamicGuardMatches(guard)) return false
        this.assertDynamicFormal(formal, {
          taskId,
          rosterVersionId: String(expected.rosterIdentity && expected.rosterIdentity.rosterVersionId || ''),
          schemeId: expected.expectedSchemeId,
          schemeVersion: expected.expectedSchemeVersion
        })
        this.dynamicReadDenied = false
        await this.reconcileGradeCommands(formal, guard)
        if (!this.dynamicGuardMatches(guard) || this.dynamicReadDenied) return false
        if (this.hasGradePending) {
          this.rosterState = 'ready'
          toast('\u670d\u52a1\u5668\u4ecd\u672a\u7ed9\u51fa\u53ef\u786e\u8ba4\u7ed3\u679c，\u8bf7\u7a0d\u540e\u518d\u6838\u5bf9')
          return false
        }
        this.applyDynamicRoster(task, formal, { preserveAllDirty: true })
        this.rosterState = 'ready'
        toast('\u670d\u52a1\u5668\u7ed3\u679c\u5df2\u6838\u5bf9；\u9875\u9762\u4e2d\u7684\u672a\u4fdd\u5b58\u4fee\u6539\u4ecd\u4fdd\u7559')
        return true
      } catch (error) {
        if (this.dynamicGuardMatches(guard)) {
          if (isForbiddenResponse(error)) this.clearDynamicPrivateState()
          else this.rosterState = 'error'
        }
        return false
      }
    },
    statusLabel(status) { return STATUS_LABELS[status] || status || '未知状态' },
    ratioOf(t) {
      if (this.entryMode === 'COMPONENTS' && this.components.length) return this.components.map((item) => `${item.name}${item.weight}%`).join(' + ')
      const mid = Number(t.midtermRatio || 0)
      return mid > 0
        ? `平时${t.usualRatio}% + 期中${mid}% + 期末${t.finalRatio}%`
        : `平时${t.usualRatio}% + 期末${t.finalRatio}%`
    },
    scoreOf(s) {
      return this.scores[s.studentId] || { exceptionFlag: 'NORMAL', totalScore: '' }
    },
    exceptionIndex(flag) {
      const index = this.exceptionOptions.findIndex((item) => item.value === String(flag || 'NORMAL').toUpperCase())
      return index >= 0 ? index : 0
    },
    exceptionLabel(flag) {
      const item = this.exceptionOptions[this.exceptionIndex(flag)]
      return item ? item.label : '正常'
    },
    async load() {
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      const context = this.contextKey()
      this.state = 'loading'
      try {
        const data = await teacherApi.getGradeTasks()
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        this.tasks = (data && data.items) || []
        this.loaded = true
        this.state = 'ready'
        if (this.requestedTaskId) {
          const id = this.requestedTaskId
          this.requestedTaskId = ''
          const target = this.tasks.find((item) => String(item.gradeTaskId) === id)
          if (target) await this.openTask(target)
          else toast('该成绩任务不存在、已失效或不在本人授课范围内')
        }
      } catch (e) {
        if (!this._pageActive || this._loadEpoch !== epoch || this.contextKey() !== context) return
        this.loaded = true
        this.state = 'error'
      }
    },
    async confirmModal(title, content, confirmText = '确定') {
      return new Promise((resolve) => {
        uni.showModal({
          title, content, confirmText, cancelText: '取消',
          success: (result) => resolve(!!result.confirm),
          fail: () => resolve(false)
        })
      })
    },
    async beforePageBack() {
      if (this.reviewMode && !this.submitting) { this.reviewMode = false; return false }
      if (!this.active) return true
      await this.leaveActiveTask()
      return false
    },
    async backToTasks() {
      await this.leaveActiveTask()
    },
    async leaveActiveTask() {
      if (!this.active) return true
      const context = this.contextKey()
      const taskId = String(this.active.gradeTaskId || '')
      const revision = this.editVersion
      if (this.saving !== null || this.savingAll || this.submitting) {
        toast('正在保存或提交，请稍候再返回')
        return false
      }
      if (this.dirtyCount) {
        const leave = await this.confirmModal(
          '仍有未保存成绩',
          `还有${this.dirtyCount}人的修改尚未写入学校服务器，离开后将丢失。确认返回任务列表？`,
          '放弃修改并返回'
        )
        if (!leave) return false
      }
      if (!this._pageActive || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId || this.editVersion !== revision || this.saving !== null || this.savingAll || this.submitting) return false
      this.active = null
      this.reviewMode = false
      this.roster = []
      this.scores = {}
      this.dirty = {}
      this.rowErrors = {}
      this.qualityReport = null
      this.entryMode = 'FIXED'
      this.dynamicCanWrite = true
      this.components = []
      this.gradeIdentity = null
      this.rosterPage = 1
      this.rosterTotal = 0
      this.rosterHasMore = false
      this.rosterVersionId = ''
      this.syncGradePending(context, taskId)
      this.draftRestoredCount = 0
      this.draftSavedAt = ''
      this.visibleCount = ROSTER_WINDOW
      return true
    },
    applyDynamicRoster(task, data, options = {}) {
      const scheme = (data && data.scheme) || {}
      const previousScores = this.scores
      const previousDirty = this.dirty
      const previousVersions = this.rowVersions
      const previousErrors = this.rowErrors
      const submittedRevisions = options.submittedRevisions || null
      const confirmedRows = Array.isArray(options.confirmedRows) ? options.confirmedRows : []
      this.entryMode = 'COMPONENTS'
      this.dynamicReadDenied = false
      this.dynamicNeedsReview = false
      this.dynamicCanWrite = !!data.canWriteComponents
      this.components = (scheme.components || []).map((item) => ({ ...item, code: String(item.code || '').toUpperCase() }))
      this.gradeIdentity = {
        expectedTaskVersion: Number(data.taskVersion),
        expectedSchemeId: String(scheme.schemeId == null ? '' : scheme.schemeId),
        expectedSchemeVersion: Number(scheme.schemeVersion || 1),
        rosterIdentity: { ...(data.rosterIdentity || {}) }
      }
      this.rosterVersionId = String(data.rosterIdentity && data.rosterIdentity.rosterVersionId || '')
      this.rosterPage = Number(data.page || 1)
      this.rosterTotal = Number(data.total || 0)
      this.rosterHasMore = !!data.hasMore
      this.roster = (data.items || []).map((student) => ({ ...student, studentId: String(student.studentId) }))
      this.active = { ...task, status: data.status || task.status, courseName: data.courseName || task.courseName, passLine: data.passLine == null ? task.passLine : data.passLine }
      const nextScores = {}
      const nextDirty = {}
      const nextVersions = {}
      const nextErrors = {}
      this.roster.forEach((student) => {
        const studentId = student.studentId
        const values = {}
        this.components.forEach((component) => {
          const value = student.scores && student.scores[component.code]
          values[component.code] = value == null ? '' : String(value)
        })
        const flag = String(student.exceptionFlag || 'NORMAL').toUpperCase()
        const formalScore = {
          components: values,
          totalScore: student.totalScore == null ? '' : student.totalScore,
          exceptionFlag: this.exceptionOptions.some((item) => item.value === flag) ? flag : 'NORMAL',
          recordId: String(student.recordId || ''),
          rowVersion: student.rowVersion == null ? null : Number(student.rowVersion)
        }
        const wasDirty = !!previousDirty[studentId]
        const wasSubmitted = submittedRevisions && Object.prototype.hasOwnProperty.call(submittedRevisions, studentId)
        const changedAfterSubmit = wasSubmitted && Number(previousVersions[studentId] || 0) !== Number(submittedRevisions[studentId] || 0)
        const local = previousScores[studentId]
        const confirmedRow = confirmedRows.find(row => String(row.studentId) === studentId)
        const ownSavedVersion = wasSubmitted && confirmedRow && String(confirmedRow.recordId || '') === formalScore.recordId && confirmedRow.rowVersion === formalScore.rowVersion
        const formalChanged = local && (local.recordId !== formalScore.recordId || local.rowVersion !== formalScore.rowVersion)
        const needsReview = wasDirty && (formalChanged || wasSubmitted) && !ownSavedVersion
        const preserveDraft = wasDirty && (options.preserveAllDirty || !wasSubmitted || changedAfterSubmit || needsReview)
        if (preserveDraft && previousScores[studentId]) {
          nextScores[studentId] = {
            ...formalScore,
            ...local,
            components: { ...(local.components || {}) },
            recordId: needsReview ? local.recordId : formalScore.recordId,
            rowVersion: needsReview ? local.rowVersion : formalScore.rowVersion,
            conflictFormal: needsReview ? formalScore : null,
            totalScore: formalScore.totalScore
          }
          nextDirty[studentId] = true
          nextVersions[studentId] = Number(previousVersions[studentId] || 0)
          nextErrors[studentId] = needsReview ? '正式成绩已更新，请先核对差异。' : previousErrors[studentId] || ''
        } else {
          nextScores[studentId] = formalScore
          nextDirty[studentId] = false
          nextVersions[studentId] = Number(previousVersions[studentId] || 0)
          nextErrors[studentId] = ''
        }
      })
      this.scores = nextScores
      this.dirty = nextDirty
      this.rowVersions = nextVersions
      this.rowErrors = nextErrors
      this.qualityReport = null
      this.visibleCount = ROSTER_WINDOW
    },
    async reviewDynamicConflict(student) {
      const id = String(student.studentId)
      const score = this.scores[id]
      const formal = score && score.conflictFormal
      if (!formal || !this.canEdit || this.saving !== null || this.savingAll || this.submitting || this.hasGradePending) return false
      const guard = { context: this.contextKey(), taskId: String(this.active.gradeTaskId), rosterEpoch: this._rosterEpoch, viewPage: this.rosterPage }
      const revision = this.rowVersions[id]
      const comparison = this.components.map(item => `${item.name}：正式 ${formal.components[item.code] || '未填'} / 我的 ${score.components[item.code] || '未填'}`).join('\n')
      const confirmed = await this.confirmModal('核对成绩差异', `${student.realName || student.studentNo}\n${comparison}\n正式状态：${this.exceptionLabel(formal.exceptionFlag)}；我的状态：${this.exceptionLabel(score.exceptionFlag)}\n确认后保留我的修改，仍需另行保存。`, '已核对，保留修改')
      if (!confirmed || !this.dynamicGuardMatches(guard) || this.rowVersions[id] !== revision || this.scores[id] !== score || score.conflictFormal !== formal || this.hasGradePending || this.saving !== null || this.savingAll || this.submitting) return false
      score.recordId = formal.recordId
      score.rowVersion = formal.rowVersion
      score.conflictFormal = null
      this.markDirty(id)
      return true
    },
    async loadDynamicPage(page) {
      if (!this.active || this.entryMode !== 'COMPONENTS' || this.dirtyCount) return false
      const task = this.active
      const taskId = String(task.gradeTaskId || '')
      const context = this.contextKey()
      const epoch = (this._rosterEpoch || 0) + 1
      this._rosterEpoch = epoch
      const guard = { context, taskId, rosterEpoch: epoch, viewPage: this.rosterPage }
      const expected = {
        taskId,
        rosterVersionId: this.rosterVersionId,
        schemeId: String(this.gradeIdentity && this.gradeIdentity.expectedSchemeId || ''),
        schemeVersion: Number(this.gradeIdentity && this.gradeIdentity.expectedSchemeVersion)
      }
      this.rosterState = 'loading'
      try {
        const data = await academicGradeEntryApi.componentRoster(taskId, { page, pageSize: ROSTER_WINDOW, expectedRosterVersionId: this.rosterVersionId })
        if (!this.dynamicGuardMatches(guard)) return false
        this.assertDynamicFormal(data, expected)
        this.dynamicReadDenied = false
        await this.reconcileGradeCommands(data, guard)
        if (!this.dynamicGuardMatches(guard) || this.dynamicReadDenied) return false
        this.applyDynamicRoster(task, data)
        this.rosterState = 'ready'
        return true
      } catch (error) {
        if (this.dynamicGuardMatches(guard)) {
          if (isForbiddenResponse(error)) this.clearDynamicPrivateState()
          else this.rosterState = 'error'
          toast((error && error.message) || '\u540d\u5355\u52a0\u8f7d\u5931\u8d25')
        }
        return false
      }
    },
    async openTask(task) {
      if (this.saving !== null || this.savingAll || this.submitting) return
      this.reviewMode = false
      this._qualityEpoch = (this._qualityEpoch || 0) + 1
      this.qualityLoading = false
      const taskId = String(task.gradeTaskId || '')
      const epoch = (this._rosterEpoch || 0) + 1
      this._rosterEpoch = epoch
      const context = this.contextKey()
      this.active = task
      this.dynamicNeedsReview = false
      this.entryMode = 'FIXED'
      this.dynamicCanWrite = true
      this.components = []
      this.gradeIdentity = null
      this.rosterPage = 1
      this.rosterTotal = 0
      this.rosterHasMore = false
      this.rosterVersionId = ''
      this.syncGradePending(context, taskId)
      this.rosterState = 'loading'
      this.roster = []
      this.scores = {}
      this.dirty = {}
      this.rowVersions = {}
      this.editVersion += 1
      this.rowErrors = {}
      this.qualityReport = null
      this.draftRestoredCount = 0
      this.draftSavedAt = ''
      this.visibleCount = ROSTER_WINDOW
      const guard = { context, taskId, rosterEpoch: epoch, viewPage: 1 }
      try {
        const componentData = typeof academicGradeEntryApi.componentRoster === 'function'
          ? await academicGradeEntryApi.componentRoster(taskId, { page: 1, pageSize: ROSTER_WINDOW })
          : { entryMode: 'FIXED' }
        if (!this._pageActive || this._rosterEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return
        if (componentData && componentData.entryMode === 'COMPONENTS') {
          this.assertDynamicFormal(componentData, { taskId })
          this.applyDynamicRoster(task, componentData)
          await this.reconcileGradeCommands(componentData, guard)
          if (!this.dynamicGuardMatches(guard) || this.dynamicReadDenied) return
          this.rosterState = 'ready'
          return
        }
        const data = await teacherApi.getGradeRoster(taskId)
        if (!this._pageActive || this._rosterEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return
        this.roster = (data && data.items) || []
        this.rosterNote = (data && data.note) || '暂无名单'
        this.midtermRatio = Number((data && data.midtermRatio) != null ? data.midtermRatio : (task.midtermRatio || 0))
        if (data && data.status) this.active = { ...task, status: data.status, midtermRatio: this.midtermRatio }
        this.roster.forEach((student) => {
          const flag = String(student.exceptionFlag || 'NORMAL').toUpperCase()
          this.scores[student.studentId] = {
            usualScore: student.usualScore != null ? String(student.usualScore) : '',
            midtermScore: student.midtermScore != null ? String(student.midtermScore) : '',
            finalScore: student.finalScore != null ? String(student.finalScore) : '',
            totalScore: student.totalScore != null ? student.totalScore : '',
            exceptionFlag: this.exceptionOptions.some((item) => item.value === flag) ? flag : 'NORMAL'
          }
          this.dirty[student.studentId] = false
        })
        this.clearDraft()
        this.rosterState = 'ready'
      } catch (e) {
        if (!this._pageActive || this._rosterEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return
        if (isForbiddenResponse(e)) this.clearDynamicPrivateState()
        else this.rosterState = 'error'
        toast((e && e.message) || '名单加载失败')
      }
    },
    clearDraft() {
      // 成绩属于敏感教务数据：生产端禁止写入uni本地持久化存储。
      this.draftSavedAt = ''
      this.draftRestoredCount = 0
    },
    markDirty(studentId) {
      this.reviewMode = false
      this.rowVersions[studentId] = (this.rowVersions[studentId] || 0) + 1
      this.editVersion += 1
      this.dirty[studentId] = true
      this.rowErrors[studentId] = ''
      this.qualityReport = null
      this.draftRestoredCount = 0
    },
    changeException(student, event) {
      if (!this.canEdit || this.submitting) return
      const index = Number(event && event.detail && event.detail.value)
      const option = this.exceptionOptions[index] || this.exceptionOptions[0]
      const score = this.scoreOf(student)
      score.exceptionFlag = option.value
      if (option.value !== 'NORMAL') {
        if (this.entryMode === 'COMPONENTS') {
          Object.keys(score.components || {}).forEach((code) => { score.components[code] = '' })
        } else {
          score.usualScore = ''
          score.midtermScore = ''
          score.finalScore = ''
        }
        score.totalScore = ''
      }
      this.markDirty(student.studentId)
      this.validateStudent(student)
    },
    parseScore(value, label) {
      if (value === '' || value == null) return { value: null }
      const number = Number(value)
      if (!Number.isInteger(number) || number < 0 || number > 100) return { error: `${label}成绩须为0—100整数` }
      return { value: number }
    },
    buildScoreBody(student) {
      const score = this.scoreOf(student)
      const exceptionFlag = String(score.exceptionFlag || 'NORMAL').toUpperCase()
      if (this.entryMode === 'COMPONENTS') {
        if (score.conflictFormal || this.dynamicNeedsReview) return { error: '正式成绩已变化，请先核对差异。' }
        const body = {
          studentId: String(student.studentId),
          expectedRecordId: String(score.recordId || ''),
          expectedRowVersion: score.rowVersion == null ? null : Number(score.rowVersion),
          scores: {}, exceptionFlag
        }
        if (exceptionFlag !== 'NORMAL') return { body }
        for (const component of this.components) {
          const raw = score.components && score.components[component.code]
          if ((raw === '' || raw == null) && !component.required) continue
          if (raw === '' || raw == null) return { error: `${component.name}` + '\u5fc5\u987b\u586b\u5199' }
          const number = Number(raw)
          if (!Number.isFinite(number) || number < 0 || number > 100 || !/^(?:\d+(?:\.\d{1,2})?|\.\d{1,2})$/.test(String(raw).trim())) return { error: `${component.name}` + '\u987b\u4e3a0—100，\u6700\u591a\u4e24\u4f4d\u5c0f\u6570' }
          body.scores[component.code] = number
        }
        return { body }
      }
      if (exceptionFlag !== 'NORMAL') {
        return {
          body: {
            studentId: Number(student.studentId),
            usualScore: null,
            midtermScore: null,
            finalScore: null,
            exceptionFlag
          }
        }
      }
      const usual = this.parseScore(score.usualScore, '平时')
      const midterm = this.parseScore(score.midtermScore, '期中')
      const finalScore = this.parseScore(score.finalScore, '期末')
      const error = usual.error || (this.showMid && midterm.error) || finalScore.error
      if (error) return { error }
      return {
        body: {
          studentId: Number(student.studentId),
          usualScore: usual.value,
          midtermScore: this.showMid ? midterm.value : null,
          finalScore: finalScore.value,
          exceptionFlag: 'NORMAL'
        }
      }
    },
    validateStudent(student) {
      const result = this.buildScoreBody(student)
      this.rowErrors[student.studentId] = result.error || ''
      return !result.error
    },
    async saveDynamicRows(students, notify = false) {
      const rows = []
      for (const student of students) {
        const built = this.buildScoreBody(student)
        if (built.error) {
          this.rowErrors[student.studentId] = built.error
          if (notify) toast(built.error)
          return false
        }
        rows.push(built.body)
      }
      const taskId = String(this.active && this.active.gradeTaskId || '')
      const context = this.contextKey()
      const task = this.active
      const expectedIdentity = this.expectedGradeIdentity()
      const submittedRevisions = Object.fromEntries(students.map((student) => [String(student.studentId), Number(this.rowVersions[student.studentId] || 0)]))
      const command = this.reserveGradeCommand(COMPONENT_SAVE, taskId, context)
      if (!command) return false
      const one = students.length === 1
      if (one) this.saving = students[0].studentId
      else this.savingAll = true
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      const rosterEpoch = this._rosterEpoch
      const viewPage = this.rosterPage
      const guard = { context, taskId, rosterEpoch, viewPage }
      try {
        await academicGradeEntryApi.componentBatchSave(taskId, { ...expectedIdentity, rows }, command.requestKey)
        if (getPersistentWrite(context, COMPONENT_SAVE, taskId).record?.requestKey === command.requestKey) persistWriteAck(context, COMPONENT_SAVE, taskId, { ackId: command.requestKey, parentId: taskId })
      } catch (error) {
        if (isExplicitWriteRejection(error) && getPersistentWrite(context, COMPONENT_SAVE, taskId).record?.requestKey === command.requestKey) clearPersistentWrite(context, COMPONENT_SAVE, taskId)
        if (this._writeEpoch === writeEpoch && this.dynamicGuardMatches(guard)) {
          this.syncGradePending(context, taskId)
          if (isForbiddenResponse(error)) this.clearDynamicPrivateState()
          else if (isExplicitWriteRejection(error)) this.dynamicNeedsReview = true
          toast(isExplicitWriteRejection(error) ? ((error && error.message) || '\u4fdd\u5b58\u672a\u53d7\u7406') : '\u4fdd\u5b58\u7ed3\u679c\u672a\u786e\u8ba4，\u5df2\u505c\u6b62\u91cd\u590d\u63d0\u4ea4')
        }
        return false
      } finally {
        if (this._writeEpoch === writeEpoch) {
          if (one) this.saving = null
          else this.savingAll = false
        }
      }
      if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || this._rosterEpoch !== rosterEpoch || String(this.active && this.active.gradeTaskId || '') !== taskId) return false
      if (one) this.saving = students[0].studentId
      else this.savingAll = true
      try {
        const formal = await academicGradeEntryApi.componentRoster(taskId, { page: viewPage, pageSize: ROSTER_WINDOW, expectedRosterVersionId: this.rosterVersionId })
        if (this._writeEpoch !== writeEpoch || !this.dynamicGuardMatches(guard)) return false
        this.assertDynamicFormal(formal, {
          taskId,
          rosterVersionId: String(expectedIdentity.rosterIdentity && expectedIdentity.rosterIdentity.rosterVersionId || ''),
          schemeId: expectedIdentity.expectedSchemeId,
          schemeVersion: expectedIdentity.expectedSchemeVersion
        })
        const confirmed = await this.reconcileGradeCommands(formal, guard)
        if (this._writeEpoch !== writeEpoch || !this.dynamicGuardMatches(guard) || this.dynamicReadDenied) return false
        if (this.hasGradePending) { toast('\u539f\u547d\u4ee4\u5df2\u6536\u5230，\u6b63\u5f85\u6b63\u5f0f\u56de\u6267\u6838\u5bf9'); return false }
        this.applyDynamicRoster(task, formal, { submittedRevisions, confirmedRows: confirmed && confirmed[command.requestKey] && confirmed[command.requestKey].items })
        if (!this.dirtyCount) this.clearDraft()
        const allSubmittedRowsCleared = students.every((student) => !this.dirty[String(student.studentId)])
        if (notify) toast(allSubmittedRowsCleared ? '\u6210\u7ee9\u5df2\u4fdd\u5b58\u5e76\u6838\u5bf9' : '\u5148\u524d\u6210\u7ee9\u5df2\u4fdd\u5b58，\u65b0\u4fee\u6539\u4ecd\u5f85\u4fdd\u5b58')
        return allSubmittedRowsCleared
      } catch (error) {
        if (this._writeEpoch === writeEpoch && this.dynamicGuardMatches(guard)) {
          if (isForbiddenResponse(error)) this.clearDynamicPrivateState()
          else toast('\u4fdd\u5b58\u5df2\u6536\u5230，\u6b63\u5f0f\u8bb0\u5f55\u6682\u672a\u6838\u5bf9；\u8bf7\u5237\u65b0\u540e\u67e5\u770b')
        }
        return false
      } finally {
        if (this._writeEpoch === writeEpoch) {
          if (one) this.saving = null
          else this.savingAll = false
        }
      }
    },
    async saveScore(student, notify = false) {
      if (!this.canEdit || this.saving !== null || this.savingAll || this.submitting) return false
      if (this.entryMode === 'COMPONENTS') return this.saveDynamicRows([student], notify)
      const built = this.buildScoreBody(student)
      if (built.error) {
        this.rowErrors[student.studentId] = built.error
        if (notify) toast(built.error)
        return false
      }
      const taskId = String(this.active.gradeTaskId || '')
      const studentId = String(student.studentId || '')
      const context = this.contextKey()
      this.saving = student.studentId
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      const rosterEpoch = this._rosterEpoch
      const revision = this.rowVersions[student.studentId] || 0
      try {
        const data = await teacherApi.enterGradeScore(taskId, built.body)
        if (this._writeEpoch !== writeEpoch) return false
        if (!this._pageActive || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId || String(student.studentId || '') !== studentId) return false
        if (this._rosterEpoch !== rosterEpoch || (this.rowVersions[student.studentId] || 0) !== revision) {
          if (notify) toast('已保存先前版本，当前新修改仍待保存')
          return false
        }
        const score = this.scoreOf(student)
        score.totalScore = data && data.totalScore != null ? data.totalScore : ''
        score.exceptionFlag = String((data && data.exceptionFlag) || built.body.exceptionFlag || 'NORMAL').toUpperCase()
        if (score.exceptionFlag !== 'NORMAL') {
          score.usualScore = ''
          score.midtermScore = ''
          score.finalScore = ''
        }
        if (this.active && this.active.status === 'NOT_STARTED') this.active.status = 'INPUTTING'
        this.dirty[student.studentId] = false
        this.rowErrors[student.studentId] = ''
        this.qualityReport = null
        if (notify) toast(score.exceptionFlag === 'NORMAL' ? '成绩已保存' : `${this.exceptionLabel(score.exceptionFlag)}状态已保存`)
        return true
      } catch (error) {
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return false
        if (this._rosterEpoch !== rosterEpoch || (this.rowVersions[student.studentId] || 0) !== revision) return false
        const message = (error && error.message) || normalizeError(error).text || '保存失败'
        this.rowErrors[student.studentId] = message
        if (notify) toast(message)
        return false
      } finally {
        if (this._writeEpoch === writeEpoch) this.saving = null
      }
    },
    async saveAll() {
      if (!this.canEdit || this.savingAll || this.saving !== null || this.submitting) return false
      const pending = this.roster.filter((student) => this.dirty[student.studentId])
      if (!pending.length) return true
      const rows = []
      let invalid = 0
      pending.forEach((student) => {
        const built = this.buildScoreBody(student)
        if (built.error) {
          this.rowErrors[student.studentId] = built.error
          invalid += 1
        } else rows.push(built.body)
      })
      if (invalid) {
        toast(`${invalid}人成绩格式不正确，请查看红色提示`)
        return false
      }

      if (this.entryMode === 'COMPONENTS') return this.saveDynamicRows(pending)

      const taskId = String(this.active.gradeTaskId || '')
      const context = this.contextKey()
      const rosterEpoch = this._rosterEpoch
      const revisions = Object.fromEntries(pending.map((student) => [student.studentId, this.rowVersions[student.studentId] || 0]))
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      this.savingAll = true
      try {
        const data = await academicGradeEntryApi.batchSave(taskId, rows)
        if (this._writeEpoch !== writeEpoch) return false
        if (!this._pageActive || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return false
        if (this._rosterEpoch !== rosterEpoch) return false
        ;((data && data.items) || []).forEach((record) => {
          const score = this.scores[record.studentId]
          if (!score || (this.rowVersions[record.studentId] || 0) !== revisions[record.studentId]) return
          score.totalScore = record.totalScore != null ? record.totalScore : ''
          score.exceptionFlag = String(record.exceptionFlag || 'NORMAL').toUpperCase()
        })
        pending.forEach((student) => {
          if ((this.rowVersions[student.studentId] || 0) !== revisions[student.studentId]) return
          this.dirty[student.studentId] = false
          this.rowErrors[student.studentId] = ''
        })
        if (this.active.status === 'NOT_STARTED') this.active.status = 'INPUTTING'
        this.qualityReport = this.dirtyCount ? null : (data && data.qualityReport) || null
        this.clearDraft()
        toast(this.dirtyCount ? '已保存先前版本，当前新修改仍待保存' : `已一次保存${rows.length}人成绩`)
        return !this.dirtyCount
      } catch (error) {
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return false
        const message = (error && error.message) || normalizeError(error).text || '批量保存失败'
        toast(message)
        return false
      } finally {
        if (this._writeEpoch === writeEpoch) this.savingAll = false
      }
    },
    async loadQualityReport() {
      if (!this.active || this.qualityLoading || this.dirtyCount || this.saving !== null || this.savingAll) return null
      const taskId = String(this.active.gradeTaskId || '')
      const epoch = (this._qualityEpoch || 0) + 1
      this._qualityEpoch = epoch
      const context = this.contextKey()
      const revision = this.editVersion
      this.qualityLoading = true
      try {
        const report = await academicGradeEntryApi.qualityReport(taskId)
        if (!this._pageActive || this._qualityEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return null
        if (this.editVersion !== revision || this.dirtyCount) return null
        if (this.entryMode === 'COMPONENTS') {
          const expected = this.expectedGradeIdentity()
          const sameTask = Number(report && report.taskVersion) === expected.expectedTaskVersion
          const sameScheme = String(report && report.schemeId == null ? '' : report.schemeId) === expected.expectedSchemeId
            && Number(report && report.schemeVersion) === expected.expectedSchemeVersion
          const sameRoster = String(report && (report.rosterVersionId || (report.rosterIdentity && report.rosterIdentity.rosterVersionId)) || '') === String(expected.rosterIdentity.rosterVersionId || '')
          if (!sameTask || !sameScheme || !sameRoster) {
            toast('\u6210\u7ee9\u4efb\u52a1、\u65b9\u6848\u6216\u540d\u5355\u5df2\u6362\u7248，\u8bf7\u91cd\u65b0\u6253\u5f00\u540e\u6838\u5bf9')
            return null
          }
        }
        this.qualityReport = report
        return report
      } catch (error) {
        if (!this._pageActive || this._qualityEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return null
        if (this.entryMode === 'COMPONENTS' && isForbiddenResponse(error)) this.clearDynamicPrivateState()
        else toast((error && error.message) || '提交检查失败')
        return null
      } finally {
        if (this._pageActive && this._qualityEpoch === epoch && this.contextKey() === context && String(this.active && this.active.gradeTaskId || '') === taskId) this.qualityLoading = false
      }
    },
    async reviewForSubmit() {
      if (!this.canEdit || this.submitting || this.saving !== null || this.savingAll || this.qualityLoading) return
      if (this.dirtyCount && !await this.saveAll()) return
      const report = await this.loadQualityReport()
      if (report) this.reviewMode = true
    },
    async submitDynamicTask(taskId, context, revision) {
      const expectedIdentity = this.expectedGradeIdentity()
      const command = this.reserveGradeCommand(COMPONENT_SUBMIT, taskId, context)
      if (!command) return false
      this.submitting = true
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      const guard = { context, taskId, rosterEpoch: this._rosterEpoch, viewPage: this.rosterPage }
      try {
        await academicGradeEntryApi.componentSubmit(taskId, expectedIdentity, command.requestKey)
        if (getPersistentWrite(context, COMPONENT_SUBMIT, taskId).record?.requestKey === command.requestKey) persistWriteAck(context, COMPONENT_SUBMIT, taskId, { ackId: command.requestKey, parentId: taskId })
      } catch (error) {
        if (isExplicitWriteRejection(error) && getPersistentWrite(context, COMPONENT_SUBMIT, taskId).record?.requestKey === command.requestKey) clearPersistentWrite(context, COMPONENT_SUBMIT, taskId)
        if (this._writeEpoch === writeEpoch && this.dynamicGuardMatches(guard)) {
          this.syncGradePending(context, taskId)
          if (isForbiddenResponse(error)) this.clearDynamicPrivateState()
          else if (isExplicitWriteRejection(error)) this.dynamicNeedsReview = true
          toast(isExplicitWriteRejection(error) ? ((error && error.message) || '\u63d0\u4ea4\u672a\u53d7\u7406') : '\u63d0\u4ea4\u7ed3\u679c\u672a\u786e\u8ba4，\u5df2\u505c\u6b62\u91cd\u590d\u63d0\u4ea4')
        }
        return false
      } finally {
        if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.submitting = false
      }
      if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || this.editVersion !== revision || String(this.active && this.active.gradeTaskId || '') !== taskId) return false
      try {
        const formal = await academicGradeEntryApi.componentRoster(taskId, { page: guard.viewPage, pageSize: ROSTER_WINDOW, expectedRosterVersionId: this.rosterVersionId })
        if (this._writeEpoch !== writeEpoch || !this.dynamicGuardMatches(guard) || this.editVersion !== revision) return false
        this.assertDynamicFormal(formal, {
          taskId,
          rosterVersionId: String(expectedIdentity.rosterIdentity && expectedIdentity.rosterIdentity.rosterVersionId || ''),
          schemeId: expectedIdentity.expectedSchemeId,
          schemeVersion: expectedIdentity.expectedSchemeVersion
        })
        await this.reconcileGradeCommands(formal, guard)
        if (this._writeEpoch !== writeEpoch || !this.dynamicGuardMatches(guard) || this.dynamicReadDenied || this.editVersion !== revision) return false
        if (this.hasGradePending) { toast('\u539f\u63d0\u4ea4\u5df2\u6536\u5230，\u6b63\u5f85\u6b63\u5f0f\u56de\u6267\u6838\u5bf9'); return false }
        this.clearDraft()
        toast('\u5df2\u63d0\u4ea4\u5b66\u9662\u5ba1\u6838')
        this.active = null
        this.roster = []
        this.qualityReport = null
        await this.load()
        return true
      } catch (error) {
        if (this._writeEpoch === writeEpoch && this.dynamicGuardMatches(guard)) {
          if (isForbiddenResponse(error)) this.clearDynamicPrivateState()
          else toast('\u63d0\u4ea4\u5df2\u6536\u5230，\u6b63\u5f0f\u72b6\u6001\u6682\u672a\u6838\u5bf9；\u8bf7\u5237\u65b0\u540e\u67e5\u770b')
        }
        return false
      }
    },
    async submitTask() {
      if (!this.canEdit || this.submitting || this.saving !== null || this.savingAll || this.qualityLoading) return
      if (this.dirtyCount) {
        const saved = await this.saveAll()
        if (!saved || this.dirtyCount) return
      }
      const report = await this.loadQualityReport()
      if (!report) return
      if (!report.canSubmit) {
        toast(report.summary || '成绩尚未录全，暂不可提交')
        return
      }
      const taskId = String(this.active && this.active.gradeTaskId || '')
      const context = this.contextKey()
      const revision = this.editVersion
      const confirmed = await this.confirmModal(
        '提交学院审核',
        `${report.summary}。提交后教师端将只读，退回后方可继续修改。确认提交？`,
        '确认提交'
      )
      if (!confirmed || !taskId || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return
      if (!this._pageActive || this.submitting || this.editVersion !== revision || this.dirtyCount || this.saving !== null || this.savingAll) {
        toast('成绩已变化，请保存后重新检查')
        return
      }

      if (this.entryMode === 'COMPONENTS') return this.submitDynamicTask(taskId, context, revision)

      this.submitting = true
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      try {
        await teacherApi.submitGradeTask(taskId)
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || String(this.active && this.active.gradeTaskId || '') !== taskId) return
        this.clearDraft()
        toast('已提交学院审核')
        this.active = null
        this.roster = []
        this.qualityReport = null
        await this.load()
      } catch (error) {
        if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context && String(this.active && this.active.gradeTaskId || '') === taskId) {
          toast((error && error.message) || '提交失败')
        }
      } finally {
        if (this._writeEpoch === writeEpoch) this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.ge__field { display: flex; flex-direction: column; gap: 4px; align-items: center; }
.ge__field-label { color: var(--text-secondary); font-size: 12px; }
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.ge__review-course { display: block; padding-bottom: 16px; margin-bottom: 16px; border-bottom: 1px solid var(--border-light); font-size: 16px; font-weight: 600; }
.ge__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ge__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
.ge__task-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-3); }
.ge__back { color: var(--teacher-600); font-size: var(--font-size-sm); }
.ge__dirty { color: var(--warning-600); font-size: var(--font-size-xs); }
.ge__saved { color: var(--success-600); font-size: var(--font-size-xs); }
.ge__pending { display: flex; flex-direction: column; gap: 10px; padding: var(--space-3); margin-bottom: var(--space-3); border-radius: var(--radius-md); background: var(--warning-50); color: var(--warning-700); font-size: var(--font-size-xs); line-height: 1.6; }
.ge__pending .btn { align-self: flex-start; }
.ge__notice { padding: var(--space-3); margin-bottom: var(--space-3); background: var(--warning-50); color: var(--text-secondary); border-radius: var(--radius-md); font-size: var(--font-size-xs); line-height: 1.6; }
.ge__quality { margin: var(--space-3) 0; padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--surface-base); }
.ge__quality.is-ready { border-color: var(--success-300); background: var(--success-50); }
.ge__quality.is-blocked { border-color: var(--warning-300); background: var(--warning-50); }
.ge__quality-head { display: flex; align-items: center; justify-content: space-between; }
.ge__quality-title { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.ge__quality-state { font-size: var(--font-size-xs); color: var(--text-secondary); }
.ge__quality-summary { display: block; margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-secondary); line-height: 1.5; }
.ge__quality-stats { display: flex; gap: var(--space-3); flex-wrap: wrap; margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--text-secondary); }
.ge__deadline { display: block; margin-top: var(--space-2); color: var(--text-secondary); font-size: var(--font-size-xs); }
.ge__deadline.is-overdue { color: var(--danger-600); font-weight: 600; }
.ge__issues { margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px dashed var(--border-base); }
.ge__issue, .ge__issue-more { display: block; font-size: var(--font-size-xs); line-height: 1.6; color: var(--danger-600); }
.ge__issue-more { color: var(--text-secondary); }
.ge__row { align-items: flex-start; gap: var(--space-2); }
.ge__student { min-width: 92px; padding-top: 2px; }
.ge__editor { display: flex; flex-direction: column; align-items: flex-end; gap: var(--space-1); max-width: 68%; }
.ge__picker { min-width: 88px; }
.ge__picker-value { min-height: 44px; padding: 0 9px; line-height: 44px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); font-size: var(--font-size-xs); color: var(--text-secondary); text-align: center; background: var(--surface-base); }
.ge__picker-value.is-special { color: var(--warning-700); border-color: var(--warning-300); background: var(--warning-50); font-weight: 600; }
.ge__scores { display: flex; align-items: flex-end; gap: var(--space-1); flex-wrap: wrap; justify-content: flex-end; }
.ge__scores.is-disabled .ge__score-input { opacity: .5; }
.ge__score-input { width: 48px; height: 44px; text-align: center; font-size: var(--font-size-sm); border: 1px solid var(--border-base); border-radius: var(--radius-sm); }
.ge__ph { color: var(--text-tertiary); }
.ge__save { min-width: 48px; padding: 0 8px; min-height: 44px; line-height: 44px; font-size: var(--font-size-xs); }
.ge__save-all { min-width: 112px; }
.ge__load-more { display: flex; align-items: center; justify-content: space-between; min-height: 46px; padding: 0 var(--space-3); color: var(--teacher-700); font-size: var(--font-size-xs); }
</style>
