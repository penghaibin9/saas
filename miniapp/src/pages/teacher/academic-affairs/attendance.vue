<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? '本课次点名' : '课堂考勤'" :before-back="backToSessions" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="!active && loaded">
        <view class="section-head">
          <text class="section-head__title">我的考勤场次</text>
          <text class="section-head__more" @click="toggleCreateForm">{{ showForm ? '收起' : '+ 新建场次' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <picker mode="selector" :range="taskLabels" :value="taskIndex" @change="onTaskPick">
            <view class="at__input at__date">{{ selectedTask ? taskLabels[taskIndex] : '选择当前教学任务（必填）' }}</view>
          </picker>
          <view v-if="selectedTask" class="at__task-note">
            <text>{{ selectedTask.courseName || '未命名课程' }}</text>
            <text>{{ selectedTask.className || '未关联班级' }} · {{ selectedTask.termCode || '当前学期' }}</text>
            <text v-if="!selectedTask.formalOccurrenceReady" class="at__source-note">{{ selectedTask.formalScheduleIssue || '当前教学任务尚无可点名的正式课次' }}</text>
          </view>
          <picker
            mode="selector"
            :range="formalPatternLabels"
            :value="patternIndex < 0 ? 0 : patternIndex"
            :disabled="!formalPatterns.length"
            @change="onPatternPick"
          >
            <view class="at__input at__date">{{ selectedPatternLabel || '选择正式上课节次（必填）' }}</view>
          </picker>
          <picker mode="date" :value="form.sessionDate" @change="onDateChange">
            <view class="at__input at__date">{{ form.sessionDate || '选择考勤日期（必填）' }}</view>
          </picker>
          <text v-if="selectedPattern" class="at__source-note">所选节次来自当前正式课表；具体日期仍以校历、调课与补课实时校验为准。</text>
          <picker mode="selector" :range="sessionTypes" @change="onTypeChange">
            <view class="at__input at__date">点名类别：{{ form.sessionType || '常规' }}</view>
          </picker>
          <button class="btn btn-primary" :disabled="!form.teachingTaskId || !form.sessionDate || !hasValidSlot || creating" @click="createSession">
            {{ creating ? '创建中…' : hasUnknownWrite('create', occurrenceKey) ? '等待核对场次' : '按教学任务圈定名单并新建' }}
          </button>
          <text v-if="!taskOptions.length" class="at__sub">暂无可用教学任务：请确认当前学期教学任务已分配到本人并完成教师确认。</text>
        </view>

        <MobileGlobalState v-if="!sessions.length" state="empty" title="暂无考勤场次" description="点击右上角新建场次。" />
        <view class="list-group" v-else>
          <view v-for="session in visibleSessions" :key="session.sessionId" class="list-row" @click="openSession(session)">
            <view class="flex-1">
              <view class="at__title-row">
                <text class="t-md">{{ session.courseName || '（未命名课程）' }}</text>
                <text v-if="session.sourceType === 'ADMIN_SPECIAL'" class="at__source-tag">管理员特殊补录</text>
              </view>
              <text class="at__sub">{{ session.sessionDate }}{{ session.slotNo ? ' 第' + session.slotNo + '节' : '' }} · 出勤 {{ session.presentCount }}/{{ session.totalCount }}</text>
            </view>
            <MobileStatusTag :status="session.status" />
          </view>
        </view>
      </view>

      <view v-if="!active && sessions.length > 20" class="page-pad at__pages">
        <button class="btn btn-ghost" :disabled="sessionPageIndex === 0" @click="sessionPage = sessionPageIndex - 1">上一组</button>
        <text>{{ sessionPageIndex + 1 }} / {{ Math.ceil(sessions.length / 20) }}</text>
        <button class="btn btn-ghost" :disabled="(sessionPageIndex + 1) * 20 >= sessions.length" @click="sessionPage = sessionPageIndex + 1">下一组</button>
      </view>
        <view class="page-pad" v-if="active">
          <text class="at__back" @click="closeSession">‹ 返回场次列表</text>
        <view v-if="hasUnknownWrite('submit', active.sessionId)" class="at__uncertain">本场考勤提交结果未确认。已停止重复提交，请刷新场次列表核对状态。</view>
        <view class="card row-between">
          <view class="flex-1">
            <view class="at__title-row">
              <text class="t-md t-bold">{{ active.courseName || '（未命名课程）' }}</text>
              <text v-if="active.sourceType === 'ADMIN_SPECIAL'" class="at__source-tag">管理员特殊补录</text>
            </view>
            <text class="at__sub">{{ active.className || active.teachingClassName || '班级待确认' }} · {{ active.sessionDate || '日期待确认' }}{{ active.slotNo ? ' 第' + active.slotNo + '节' : '' }}</text>
            <text v-if="active.sourceType === 'ADMIN_SPECIAL'" class="at__source-note">该场次来自管理员特殊补录，普通教师端不会提供此创建入口。</text>
          </view>
          <MobileStatusTag :status="active.status" />
        </view>

        <view v-if="!detailLoading && items.length" class="at__progress card">
          <view>
            <text class="at__progress-title">已核对 {{ markedCount }} / {{ items.length }} 人</text>
            <text class="at__source-note">{{ unmarkedCount ? `还有 ${unmarkedCount} 人未点名。未操作不会按出勤提交。` : '全班已完成点名，请核对后提交。' }}</text>
            <text class="at__source-note">正式名单：出勤 {{ statusCounts.PRESENT }} · 迟到 {{ statusCounts.LATE }} · 缺勤 {{ statusCounts.ABSENT }} · 请假 {{ statusCounts.LEAVE }}</text>
          </view>
          <text class="at__progress-value">{{ attendanceProgress }}%</text>
        </view>

        <MobileGlobalState v-if="detailLoading" state="loading" title="正在读取本场考勤名单" />
        <template v-else>
          <MobileGlobalState v-if="!items.length" state="empty" title="本场暂无学生名单" description="请检查教学任务正式名单是否已锁定。" />
          <view class="list-group" v-else>
            <view v-for="item in visibleStudents" :key="item.studentId" class="list-row at__row">
              <view class="flex-1">
                <text class="t-md">{{ item.realName }}</text>
                <text class="at__sub">{{ item.studentNo }}</text>
              </view>
              <view class="at__seg" :class="{ 'is-pending': marking[item.studentId] || hasUnknownWrite(`mark:${active.sessionId}`, item.studentId) }">
                <text
                  v-for="option in STATUS_OPTS" :key="option.value"
                  class="at__seg-item" :class="{ 'is-active': item.status === option.value }"
                  @click="active.status === 'DRAFT' && mark(item, option.value)"
                >{{ option.label }}</text>
              </view>
            </view>
          </view>
          <view v-if="items.length > 30" class="at__pages">
            <button class="btn btn-ghost" :disabled="studentPageIndex === 0" @click="studentPage = studentPageIndex - 1">上一组</button>
            <text>{{ studentPageIndex * 30 + 1 }}–{{ Math.min((studentPageIndex + 1) * 30, items.length) }} / {{ items.length }} 人</text>
            <button class="btn btn-ghost" :disabled="(studentPageIndex + 1) * 30 >= items.length" @click="studentPage = studentPageIndex + 1">下一组</button>
          </view>
          <text v-if="items.length > 30" class="at__source-note">页面每组显示 30 人；提交时核对并提交本场完整正式名单 {{ items.length }} 人。</text>
          <button v-if="unmarkedCount && items.length > 30" class="btn btn-ghost" @click="showNextUnmarked">定位下一位未点名学生所在分组</button>
        </template>

        <MobileSafeAreaBar v-if="!detailLoading && active.status === 'DRAFT' && items.length">
          <button class="btn btn-primary flex-1" :disabled="submitting || hasPendingMarks || hasUnknownMarks || unmarkedCount || hasUnknownWrite('submit', active.sessionId)" @click="submitSession">
            {{ submitting ? '提交中…' : hasUnknownWrite('submit', active.sessionId) ? '等待核对结果' : hasUnknownMarks ? '请先核对待确认的学生标记' : hasPendingMarks ? '正在保存标记…' : unmarkedCount ? `还有${unmarkedCount}人未点名` : '提交考勤（提交后不可再改）' }}
          </button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { useSessionStore } from '@/stores/session'
import { beginPersistentWrite, clearPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, listPersistentWrites, persistWriteAck, teacherWriteContext } from './write-result'

const STATUS_OPTS = [
  { value: 'PRESENT', label: '出勤' },
  { value: 'LATE', label: '迟到' },
  { value: 'ABSENT', label: '缺勤' },
  { value: 'LEAVE', label: '请假' }
]
const ALLOWED_TASK_STATUSES = new Set(['TEACHER_CONFIRMED', 'COLLEGE_REVIEW', 'APPROVED', 'READY'])

export default {
  data() {
    return {
      sessions: [], loaded: false, state: 'loading', showForm: false, creating: false, sessionPage: 0, studentPage: 0,
      sessionTypes: ['常规', '实训', '晚自习', '其他'],
      taskOptions: [], taskIndex: 0, patternIndex: -1, taskSelectionInvalid: false, routeSeed: null, sessionSeed: null,
      form: { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', scheduleItemId: '', sessionType: '' },
      active: null, items: [], detailLoading: false, marking: {}, submitting: false, unknownWrites: {}, writeStorageBlocked: false, STATUS_OPTS
    }
  },
  computed: {
    sessionPageIndex() { return Math.min(this.sessionPage, Math.max(0, Math.ceil(this.sessions.length / 20) - 1)) },
    studentPageIndex() { return Math.min(this.studentPage, Math.max(0, Math.ceil(this.items.length / 30) - 1)) },
    visibleSessions() { return this.sessions.slice(this.sessionPageIndex * 20, (this.sessionPageIndex + 1) * 20) },
    visibleStudents() { return this.items.slice(this.studentPageIndex * 30, (this.studentPageIndex + 1) * 30) },
    taskLabels() {
      return (this.taskOptions || []).map((task) => `${task.courseName || '未命名课程'} · ${task.className || '未关联班级'}`)
    },
    selectedTask() {
      if (this.taskSelectionInvalid) return null
      return (this.taskOptions || [])[this.taskIndex] || null
    },
    formalPatterns() {
      return (this.selectedTask && this.selectedTask.formalSchedulePatterns) || []
    },
    formalPatternLabels() {
      const weekdayLabels = ['', '一', '二', '三', '四', '五', '六', '日']
      return this.formalPatterns.map((pattern) => {
        const parity = pattern.weekParity === 'ODD' ? '单周' : pattern.weekParity === 'EVEN' ? '双周' : '每周'
        const weekday = weekdayLabels[Number(pattern.weekday)] || String(pattern.weekday || '?')
        return `周${weekday} · 第${pattern.slotNo}节 · ${pattern.startWeek}-${pattern.endWeek}周 ${parity}`
      })
    },
    selectedPattern() {
      if (this.patternIndex < 0) return null
      return this.formalPatterns[this.patternIndex] || null
    },
    selectedPatternLabel() {
      if (this.patternIndex < 0) return ''
      return this.formalPatternLabels[this.patternIndex] || ''
    },
    hasValidSlot() {
      const pattern = this.selectedPattern
      const slot = Number(this.form.slotNo)
      const scheduleItemId = Number(this.form.scheduleItemId)
      return !!pattern
        && Number.isInteger(slot)
        && slot > 0
        && slot === Number(pattern.slotNo)
        && Number.isInteger(scheduleItemId)
        && scheduleItemId > 0
        && String(pattern.scheduleItemId || '') === String(this.form.scheduleItemId || '')
    },
    hasPendingMarks() {
      return Object.values(this.marking).some(Boolean)
    },
    hasUnknownMarks() {
      const sessionId = String(this.active && this.active.sessionId || '')
      return !!sessionId && Object.values(this.unknownWrites).some((record) => record && record.action === `mark:${sessionId}`)
    },
    markedCount() { return this.items.filter((item) => STATUS_OPTS.some((option) => option.value === item.status)).length },
    statusCounts() {
      const counts = { PRESENT: 0, LATE: 0, ABSENT: 0, LEAVE: 0 }
      this.items.forEach((item) => { if (Object.prototype.hasOwnProperty.call(counts, item.status)) counts[item.status] += 1 })
      return counts
    },
    unmarkedCount() { return Math.max(0, this.items.length - this.markedCount) },
    attendanceProgress() { return this.items.length ? Math.round(this.markedCount * 100 / this.items.length) : 0 },
    occurrenceKey() { return [this.form.teachingTaskId, this.form.sessionDate, this.form.slotNo, this.form.scheduleItemId, this.form.sessionType].map((value) => String(value || '')).join('|') }
  },
  onLoad(options = {}) {
    this._pageActive = true
    this._viewContext = this.contextKey()
    this.syncUnknownWrites()
    this.sessionSeed = this.parseSessionSeed(options)
    this.routeSeed = this.sessionSeed ? null : this.parseOccurrenceSeed(options)
    this.load()
    if (this.routeSeed) this.loadTasks()
  },
  onShow() {
    this._pageActive = true
    this.syncUnknownWrites()
    const context = this.contextKey()
    if (this._viewContext !== context) {
      this._viewContext = context
      this._writeEpoch = (this._writeEpoch || 0) + 1
      this.creating = false
      this.submitting = false
      this.taskOptions = []
      this.form = { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', scheduleItemId: '', sessionType: '' }
      this.active = null
      this.items = []
      this.sessionPage = 0
      this.studentPage = 0
      this.marking = {}
      this.showForm = false
      this.sessionSeed = null
      this.routeSeed = null
      this.syncUnknownWrites()
      this._needsRefresh = false
      this.load()
      return
    }
    if (!this._needsRefresh) return
    this._needsRefresh = false
    this.load()
    if (this.showForm || this.routeSeed) this.loadTasks()
    if (this.active && this.active.sessionId) this.openSession(this.active)
  },
  onHide() {
    this._pageActive = false
    this._needsRefresh = true
    this._listEpoch = (this._listEpoch || 0) + 1
    this._taskEpoch = (this._taskEpoch || 0) + 1
    this._detailEpoch = (this._detailEpoch || 0) + 1
  },
  onUnload() {
    this._pageActive = false
    this._listEpoch = (this._listEpoch || 0) + 1
    this._taskEpoch = (this._taskEpoch || 0) + 1
    this._detailEpoch = (this._detailEpoch || 0) + 1
  },
  onBackPress() { if (!this.active) return false; this.backToSessions(); return true },
  methods: {
    toggleCreateForm() { if (this.creating) return; this.showForm = !this.showForm; if (this.showForm) this.loadTasks() },
    backToSessions() { if (!this.active) return true; this.closeSession(); return false },
    showNextUnmarked() {
      const start = (this.studentPageIndex + 1) * 30
      const unmarked = (item) => !STATUS_OPTS.some((option) => option.value === item.status)
      let index = this.items.findIndex((item, i) => i >= start && unmarked(item))
      if (index < 0) index = this.items.findIndex(unmarked)
      if (index >= 0) this.studentPage = Math.floor(index / 30)
    },
    contextKey() {
      return teacherWriteContext(useSessionStore())
    },
    writeKey(action, objectId) { return `${action}|${String(objectId || '')}` },
    hasUnknownWrite(action, objectId) { return this.writeStorageBlocked || !!this.unknownWrites[this.writeKey(action, objectId)] },
    syncUnknownWrites(context = this.contextKey()) { const result = listPersistentWrites(context); this.writeStorageBlocked = !result.ok; this.unknownWrites = result.ok ? Object.fromEntries(result.records.map((row) => [this.writeKey(row.action, row.objectId), row])) : {}; return result },
    beginWrite(context, action, objectId) { const result = beginPersistentWrite(context, action, objectId); this.syncUnknownWrites(); if (!result.ok) toast(result.storageError ? '无法安全保存待核对记录，本次未提交' : '该操作正在等待正式记录核对'); return result.ok },
    ackWrite(context, action, objectId, ack) { const ok = persistWriteAck(context, action, objectId, ack); this.syncUnknownWrites(); return ok },
    clearWrite(context, action, objectId) { const ok = clearPersistentWrite(context, action, objectId); this.syncUnknownWrites(); return ok },
    reconcileSessions(rows) {
      const pending = listPersistentWrites(this.contextKey())
      if (!pending.ok) { this.syncUnknownWrites(); return }
      const terminal = new Set(['SUBMITTED', 'LOCKED', 'FINALIZED', 'CLOSED'])
      pending.records.forEach((record) => {
        if (record.state !== 'ACK') return
        if (record.action === 'create') {
          const parts = record.objectId.split('|')
          const found = rows.some((row) => (record.ackId && String(row.sessionId || '') === record.ackId) ||
            (String(row.teachingTaskId || '') === parts[0] && String(row.sessionDate || '') === parts[1] && String(row.slotNo || '') === parts[2] && (!parts[3] || String(row.scheduleItemId || '') === parts[3])))
          if (found) this.clearWrite(record.context, record.action, record.objectId)
        }
        if (record.action === 'submit' && rows.some((row) => String(row.sessionId || '') === record.objectId && terminal.has(String(row.status || '').toUpperCase()))) this.clearWrite(record.context, record.action, record.objectId)
      })
    },
    reconcileMarks(sessionId, detail) {
      const pending = listPersistentWrites(this.contextKey())
      if (!pending.ok) { this.syncUnknownWrites(); return }
      pending.records.forEach((record) => {
        if (record.state !== 'ACK' || record.action !== `mark:${sessionId}`) return
        const item = ((detail && detail.items) || []).find((row) => String(row.studentId || '') === record.objectId)
        if (item && String(item.status || '') === String(record.ackId || '')) this.clearWrite(record.context, record.action, record.objectId)
      })
    },
    clearPrivateAttendance() {
      this._listEpoch = (this._listEpoch || 0) + 1
      this._taskEpoch = (this._taskEpoch || 0) + 1
      this._detailEpoch = (this._detailEpoch || 0) + 1
      this._writeEpoch = (this._writeEpoch || 0) + 1
      this.sessions = []; this.taskOptions = []; this.active = null; this.items = []; this.marking = {}
      this.showForm = false; this.creating = false; this.submitting = false; this.detailLoading = false
      this.form = { teachingTaskId: '', classId: '', sessionDate: '', slotNo: '', scheduleItemId: '', sessionType: '' }
      this.state = 'error'
    },
    exactCreateReceipt(ack, body) {
      const sessionId = String(ack && (ack.sessionId || ack.id) || '')
      const occurrence = (ack && ack.occurrenceEvidence) || {}
      return sessionId && String(ack.teachingTaskId || '') === String(body.teachingTaskId || '')
        && String(ack.sessionDate || '') === String(body.sessionDate || '')
        && Number(ack.slotNo) === Number(body.slotNo)
        && (!body.scheduleItemId || String(occurrence.scheduleItemId || '') === String(body.scheduleItemId))
        ? sessionId : ''
    },
    exactMarkReceipt(ack, sessionId, studentId, status) {
      if (String(ack && (ack.sessionId || ack.id) || '') !== String(sessionId)) return false
      const row = ((ack && ack.items) || []).find((item) => String(item.studentId || '') === String(studentId))
      return !!row && String(row.status || '') === String(status)
    },
    exactSubmitReceipt(ack, sessionId) {
      const terminal = new Set(['SUBMITTED', 'LOCKED', 'FINALIZED', 'CLOSED'])
      return String(ack && (ack.sessionId || ack.id) || '') === String(sessionId) && terminal.has(String(ack && ack.status || '').toUpperCase())
    },
    async readBackSession(sessionId, context, writeEpoch, terminalOnly = false) {
      const listEpoch = (this._listEpoch || 0) + 1
      this._listEpoch = listEpoch
      try {
        const data = await teacherApi.getAttendanceSessions()
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this._listEpoch !== listEpoch || this.contextKey() !== context) return null
        this.sessions = (data && data.items) || []
        this.loaded = true
        this.reconcileSessions(this.sessions)
        const row = this.sessions.find((item) => String(item.sessionId || '') === String(sessionId))
        if (!row) return null
        if (terminalOnly && !new Set(['SUBMITTED', 'LOCKED', 'FINALIZED', 'CLOSED']).has(String(row.status || '').toUpperCase())) return null
        return row
      } catch (error) {
        if (this._pageActive && this._writeEpoch === writeEpoch && this._listEpoch === listEpoch && this.contextKey() === context && isForbiddenResponse(error)) this.clearPrivateAttendance()
        return null
      }
    },
    parseSessionSeed(options = {}) {
      const sessionRaw = String(options.sessionId || '').trim()
      if (!sessionRaw) return null
      const occurrenceFields = [options.teachingTaskId, options.sessionDate, options.slotNo, options.scheduleItemId]
      if (occurrenceFields.some((value) => String(value || '').trim())) {
        return { invalid: true, message: '考勤链接参数冲突，请重新从教师今日课次进入' }
      }
      const sessionId = Number(sessionRaw)
      if (!Number.isInteger(sessionId) || sessionId <= 0) {
        return { invalid: true, message: '考勤场次链接无效，请重新从教师今日课次进入' }
      }
      return { invalid: false, sessionId: String(sessionId) }
    },
    parseOccurrenceSeed(options = {}) {
      const taskIdRaw = String(options.teachingTaskId || '').trim()
      const sessionDate = String(options.sessionDate || '').trim()
      const slotRaw = String(options.slotNo || '').trim()
      const scheduleItemId = String(options.scheduleItemId || '').trim()
      const anySeed = Boolean(taskIdRaw || sessionDate || slotRaw || scheduleItemId)
      if (!anySeed) return null

      const taskId = Number(taskIdRaw)
      const slotNo = Number(slotRaw)
      const dateValid = /^\d{4}-\d{2}-\d{2}$/.test(sessionDate)
      if (!Number.isInteger(taskId) || taskId <= 0 || !dateValid || !Number.isInteger(slotNo) || slotNo <= 0) {
        return {
          invalid: true,
          message: '点名链接缺少有效的教学任务、日期或节次，请重新从正式课次进入'
        }
      }
      return {
        invalid: false,
        teachingTaskId: String(taskId),
        sessionDate,
        slotNo: String(slotNo),
        scheduleItemId
      }
    },
    applySessionSeed() {
      const seed = this.sessionSeed
      if (!seed) return
      this.sessionSeed = null
      if (seed.invalid) {
        toast(seed.message)
        return
      }
      const index = this.sessions.findIndex((row) => String(row.sessionId || '') === seed.sessionId)
      if (index >= 0) {
        this.sessionPage = Math.floor(index / 20)
        this.openSession(this.sessions[index])
        return
      }
      this.openSession({ sessionId: seed.sessionId })
    },
    applyOccurrenceSeed() {
      const seed = this.routeSeed
      if (!seed) {
        this.taskSelectionInvalid = false
        this.taskIndex = 0
        this.applyTask(this.taskOptions[0])
        return
      }

      this.showForm = true
      if (seed.invalid) {
        this.taskSelectionInvalid = true
        this.applyTask(null)
        this.form.sessionDate = ''
        this.form.slotNo = ''
        toast(seed.message)
        return
      }

      const index = this.taskOptions.findIndex((task) => String(task.teachingTaskId) === seed.teachingTaskId)
      if (index < 0) {
        this.taskSelectionInvalid = true
        this.applyTask(null)
        this.form.sessionDate = ''
        this.form.slotNo = ''
        toast('该正式课次不在本人当前可点名教学任务范围内')
        return
      }

      this.taskSelectionInvalid = false
      this.taskIndex = index
      this.applyTask(this.taskOptions[index])
      const matchingPatternIndexes = []
      this.formalPatterns.forEach((pattern, patternIndex) => {
        if (Number(pattern.slotNo) === Number(seed.slotNo)) matchingPatternIndexes.push(patternIndex)
      })
      let patternIndex = -1
      if (seed.scheduleItemId) {
        patternIndex = matchingPatternIndexes.find((candidateIndex) =>
          String(this.formalPatterns[candidateIndex].scheduleItemId || '') === seed.scheduleItemId)
        if (patternIndex === undefined) patternIndex = -1
      } else if (matchingPatternIndexes.length === 1) {
        patternIndex = matchingPatternIndexes[0]
      }
      if (patternIndex < 0) {
        const ambiguous = !seed.scheduleItemId && matchingPatternIndexes.length > 1
        this.taskSelectionInvalid = true
        this.applyTask(null)
        this.form.sessionDate = ''
        toast(ambiguous ? '该节次对应多个正式课表项，请从教师今日课次重新进入' : '该正式课次已不在当前发布课表中')
        return
      }
      this.patternIndex = patternIndex
      this.form.sessionDate = seed.sessionDate
      this.form.slotNo = String(this.formalPatterns[patternIndex].slotNo)
      this.form.scheduleItemId = String(this.formalPatterns[patternIndex].scheduleItemId || '')
    },
    onDateChange(event) { this.form.sessionDate = event.detail.value },
    onTypeChange(event) { this.form.sessionType = this.sessionTypes[Number(event.detail.value)] || '' },
    applyTask(task) {
      this.form.teachingTaskId = task ? task.teachingTaskId : ''
      this.form.classId = task ? task.classId : ''
      this.patternIndex = -1
      this.form.slotNo = ''
      this.form.scheduleItemId = ''
    },
    onTaskPick(event) {
      this.routeSeed = null
      this.taskSelectionInvalid = false
      this.taskIndex = Number(event.detail.value)
      this.applyTask(this.taskOptions[this.taskIndex])
    },
    onPatternPick(event) {
      this.patternIndex = Number(event.detail.value)
      const pattern = this.formalPatterns[this.patternIndex]
      this.form.slotNo = pattern ? String(pattern.slotNo) : ''
      this.form.scheduleItemId = pattern ? String(pattern.scheduleItemId || '') : ''
    },
    confirmModal(title, content, confirmText = '确定') {
      return new Promise((resolve) => {
        uni.showModal({
          title, content, confirmText, cancelText: '取消',
          success: (result) => resolve(!!result.confirm),
          fail: () => resolve(false)
        })
      })
    },
    async loadTasks() {
      const epoch = (this._taskEpoch || 0) + 1
      this._taskEpoch = epoch
      const context = this.contextKey()
      try {
        const data = await teacherApi.getAttendanceClassOptions()
        if (!this._pageActive || this._taskEpoch !== epoch || this.contextKey() !== context) return
        this.taskOptions = ((data && data.items) || [])
          .filter((task) => ALLOWED_TASK_STATUSES.has(String(task.taskStatus || '').toUpperCase()))
          .sort((left, right) => Number(Boolean(right.formalOccurrenceReady)) - Number(Boolean(left.formalOccurrenceReady)))
        this.applyOccurrenceSeed()
      } catch (error) {
        if (!this._pageActive || this._taskEpoch !== epoch || this.contextKey() !== context) return
        if (isForbiddenResponse(error)) { this.clearPrivateAttendance(); return }
        this.taskOptions = []
        this.taskSelectionInvalid = Boolean(this.routeSeed)
        this.applyTask(null)
      }
    },
    async load() {
      const epoch = (this._listEpoch || 0) + 1
      this._listEpoch = epoch
      const context = this.contextKey()
      this.state = 'loading'
      try {
        const data = await teacherApi.getAttendanceSessions()
        if (!this._pageActive || this._listEpoch !== epoch || this.contextKey() !== context) return
        this.sessions = (data && data.items) || []
        this.reconcileSessions(this.sessions)
        this.loaded = true
        this.state = 'ready'
        this.applySessionSeed()
      } catch (error) {
        if (this._pageActive && this._listEpoch === epoch && this.contextKey() === context) {
          if (isForbiddenResponse(error)) this.clearPrivateAttendance()
          else this.state = 'error'
        }
      }
    },
    createSession() {
      if (this.creating || !this.form.teachingTaskId || !this.form.sessionDate || !this.hasValidSlot) return
      const context = this.contextKey()
      const body = {
        teachingTaskId: Number(this.form.teachingTaskId),
        classId: this.form.classId ? Number(this.form.classId) : undefined,
        sessionDate: this.form.sessionDate,
        slotNo: Number(this.form.slotNo),
        scheduleItemId: this.form.scheduleItemId || undefined,
        sessionType: this.form.sessionType || undefined
      }
      const requestKey = this.occurrenceKey
      if (this.hasUnknownWrite('create', requestKey)) { toast('创建结果未确认，请先刷新核对场次列表'); return }
      if (!this.beginWrite(context, 'create', requestKey)) return
      this.creating = true
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      const snapshot = JSON.stringify(this.form)
      teacherApi.createAttendanceSession(body).then(async (ack) => {
        const sessionId = this.exactCreateReceipt(ack, body)
        if (!sessionId) {
          if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) { toast('创建结果未确认，已停止重复提交；请只读核对场次列表'); this.load() }
          return
        }
        this.ackWrite(context, 'create', requestKey, { ackId: sessionId, parentId: requestKey })
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
        const formal = await this.readBackSession(sessionId, context, writeEpoch)
        if (!formal) {
          if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) toast('已收到场次编号，正式列表尚未核对，请勿重复创建')
          return
        }
        if (JSON.stringify(this.form) !== snapshot) { toast('原场次已创建，当前新填写内容已保留'); return }
        uni.showToast({ title: '考勤场次已创建', icon: 'success' })
        this.showForm = false
        this.form.sessionDate = ''
        this.form.slotNo = ''
        this.form.sessionType = ''
        this.applyTask(this.taskOptions[this.taskIndex])
      }).catch((error) => {
        if (isExplicitWriteRejection(error)) this.clearWrite(context, 'create', requestKey)
        if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context) {
          if (isForbiddenResponse(error)) { this.clearPrivateAttendance(); return }
          if (isExplicitWriteRejection(error)) toast(normalizeError(error).text)
          else { toast('创建结果未确认，已停止重复提交；请先核对场次列表'); this.load() }
        }
      }).finally(() => { if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.creating = false })
    },
    closeSession() {
      if (this.hasPendingMarks || this.submitting) {
        toast('仍有考勤标记正在保存，请稍候')
        return
      }
      this._detailEpoch = (this._detailEpoch || 0) + 1
      this.active = null
      this.items = []
      this.marking = {}
      this.detailLoading = false
    },
    openSession(session) {
      if (this.hasPendingMarks || this.submitting) return
      const sessionId = String(session.sessionId || '')
      if (String(this.active && this.active.sessionId || '') !== sessionId) this.studentPage = 0
      const epoch = (this._detailEpoch || 0) + 1
      this._detailEpoch = epoch
      const context = this.contextKey()
      this.active = { ...session }
      this.items = []
      this.marking = {}
      this.detailLoading = true
      teacherApi.getAttendanceDetail(session.sessionId).then((data) => {
        if (!this._pageActive || this._detailEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
        if (String(data && data.sessionId || sessionId) !== sessionId) { this.active = null; this.items = []; toast('名单对象校验失败，请重新打开'); return }
        this.active = data
        this.items = (data && data.items) || []
        this.reconcileMarks(sessionId, data)
      }).catch((error) => {
        if (!this._pageActive || this._detailEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
        if (isForbiddenResponse(error)) { this.clearPrivateAttendance(); return }
        this.active = null
        this.items = []
        this.marking = {}
        toast(error && error.biz ? normalizeError(error).text : '名单加载失败，请稍后重试')
      }).finally(() => {
        if (this._detailEpoch === epoch && this.contextKey() === context) this.detailLoading = false
      })
    },
    mark(item, status) {
      const studentId = item.studentId
      if (!this._pageActive || this.submitting || this.detailLoading || this.marking[studentId] || item.status === status || !this.items.includes(item)) return
      const sessionId = String(this.active && this.active.sessionId || '')
      const context = this.contextKey()
      const epoch = this._detailEpoch
      const marker = (this._markSequence || 0) + 1
      this._markSequence = marker
      const previous = item.status
      const action = `mark:${sessionId}`
      if (!this.beginWrite(context, action, studentId)) return
      item.status = status
      this.marking[studentId] = marker
      teacherApi.markAttendance(sessionId, studentId, status).then((ack) => {
        if (this.exactMarkReceipt(ack, sessionId, studentId, status)) {
          this.ackWrite(context, action, studentId, { ackId: status, parentId: sessionId })
        } else if (this._pageActive && this._detailEpoch === epoch && this.contextKey() === context && String(this.active && this.active.sessionId || '') === sessionId) {
          toast('该生点名结果待确认，已停止重复提交并刷新正式名单')
        }
        if (!this._pageActive || this._detailEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
        this.syncAttendanceCounts()
      }).catch((error) => {
        if (isExplicitWriteRejection(error)) this.clearWrite(context, action, studentId)
        if (!this._pageActive || this._detailEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
        item.status = previous
        this.syncAttendanceCounts()
        if (isForbiddenResponse(error)) { this.clearPrivateAttendance(); return }
        toast(isExplicitWriteRejection(error) ? (error && error.biz ? normalizeError(error).text : '标记失败，请稍后重试') : '该生点名结果待确认，已停止重复提交并刷新正式名单')
      }).finally(() => {
        if (this.marking[studentId] !== marker || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
        this.marking[studentId] = false
        if (this._pageActive && !this.hasPendingMarks && !this.submitting) this.openSession(this.active)
      })
    },
    syncAttendanceCounts() {
      if (!this.active) return
      this.active.presentCount = this.items.filter((item) => item.status === 'PRESENT').length
      this.active.absentCount = this.items.filter((item) => item.status === 'ABSENT').length
    },
    async submitSession() {
      if (this.submitting || this.detailLoading || this.hasPendingMarks || this.hasUnknownMarks || this.unmarkedCount || !this.active || !this.items.length || this.hasUnknownWrite('submit', this.active.sessionId)) return
      const sessionId = String(this.active.sessionId || '')
      const context = this.contextKey()
      const courseName = this.active.courseName || '本课程'
      const itemCount = this.items.length
      const epoch = this._detailEpoch
      const snapshot = JSON.stringify(this.items.map((item) => [item.studentId, item.status]))
      const confirmed = await this.confirmModal(
        '提交本场考勤',
        `即将提交${courseName}共${itemCount}人的考勤结果。提交后教师端不可直接修改，确认继续？`,
        '确认提交'
      )
      if (!confirmed || !this._pageActive || this.submitting || this.hasPendingMarks || this.unmarkedCount || this._detailEpoch !== epoch || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
      if (JSON.stringify(this.items.map((item) => [item.studentId, item.status])) !== snapshot) { toast('点名结果已变化，请重新确认'); return }
      if (!this.beginWrite(context, 'submit', sessionId)) return
      this.submitting = true
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      teacherApi.submitAttendanceSession(sessionId).then(async (ack) => {
        const ackId = String(ack && (ack.sessionId || ack.id) || '')
        if (!this.exactSubmitReceipt(ack, sessionId)) {
          if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context && String(this.active && this.active.sessionId || '') === sessionId) {
            toast('提交结果未确认，已停止重复提交；请只读核对本场状态')
            this.load()
          }
          return
        }
        this.ackWrite(context, 'submit', sessionId, { ackId, parentId: sessionId })
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
        const formal = await this.readBackSession(sessionId, context, writeEpoch, true)
        if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || String(this.active && this.active.sessionId || '') !== sessionId) return
        if (!formal) {
          if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context && String(this.active && this.active.sessionId || '') === sessionId) toast('已收到提交回执，正式状态尚未核对，请勿重复提交')
          return
        }
        if (ack.warningScanOk === false) {
          toast(ack.warningScanError || '考勤已提交；旷课预警扫描待核对')
        } else {
          uni.showToast({ title: '考勤已提交', icon: 'success' })
        }
        this.active = null
        this.items = []
        this.marking = {}
      }).catch((error) => {
        if (isExplicitWriteRejection(error)) this.clearWrite(context, 'submit', sessionId)
        if (this._pageActive && this._writeEpoch === writeEpoch && this.contextKey() === context && String(this.active && this.active.sessionId || '') === sessionId) {
          if (isForbiddenResponse(error)) { this.clearPrivateAttendance(); return }
          if (isExplicitWriteRejection(error)) toast(normalizeError(error).text)
          else { toast('提交结果未确认，已停止重复提交；请核对本场考勤状态'); this.load() }
        }
      }).finally(() => { if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.submitting = false })
    }
  }
}
</script>

<style scoped>
.at__pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0; font-size: 12px; }
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.at__input { width: 100%; height: 40px; line-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.at__date { color: var(--text-primary); }
.at__ph { color: var(--text-tertiary); }
.at__task-note { display: flex; flex-direction: column; gap: 3px; padding: var(--space-3); border-radius: var(--radius-md); background: var(--teacher-50); color: var(--text-secondary); font-size: var(--font-size-xs); }
.at__uncertain { margin: 12px 0; padding: 10px 12px; border-radius: 10px; background: var(--warning-50); color: var(--warning-700); font-size: 13px; line-height: 1.5; }
.at__task-note text:first-child { color: var(--teacher-700); font-size: var(--font-size-sm); font-weight: 600; }
.at__title-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.at__source-tag { display: inline-flex; align-items: center; min-height: 22px; padding: 0 var(--space-2); border-radius: 999px; background: var(--teacher-50); color: var(--teacher-700); font-size: var(--font-size-xs); font-weight: 600; }
.at__source-note { display: block; margin-top: 4px; color: var(--text-tertiary); font-size: var(--font-size-xs); line-height: 1.5; }
.at__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.at__back { display: inline-block; font-size: var(--font-size-sm); color: var(--teacher-700); margin-bottom: var(--space-3); }
.at__row { align-items: center; flex-wrap: wrap; gap: 8px; }
.at__row > .flex-1 { min-width: 60px; overflow-wrap: anywhere; }
.at__progress { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-3); }
.at__progress-title { display: block; color: var(--text-primary); font-size: var(--font-size-sm); font-weight: 600; }
.at__progress-value { flex-shrink: 0; color: var(--teacher-700); font-size: 22px; font-weight: 700; }
.at__seg { display: flex; flex-shrink: 0; border: 1px solid var(--border-base); border-radius: var(--radius-md); overflow: hidden; }
.at__seg.is-pending { opacity: .55; pointer-events: none; }
.at__seg-item { display: flex; align-items: center; justify-content: center; min-width: 44px; min-height: 44px; font-size: var(--font-size-xs); color: var(--text-secondary); padding: 6px 8px; }
.at__seg-item.is-active { background: var(--teacher-600); color: #fff; }
</style>
