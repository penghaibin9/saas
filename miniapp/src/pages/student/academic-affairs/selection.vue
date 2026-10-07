<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="网上选课" show-back />
    <AcademicPageState :state="pageState" @retry="load">
      <view v-if="loaded" class="page-pad sl">
        <view class="sl__hero">
          <text class="sl__eyebrow">注册与安排 · 仅限本人</text>
        </view>

        <picker v-if="batchCatalog.length" :range="batchCatalog" range-key="batchName" :value="activeBatchIndex" @change="onBatchPick">
          <view class="sl__batch-picker">{{ activeBatchName }}</view>
        </picker>
        <view v-if="batchTotal > batchCatalog.length" class="sl__batch-more">
          <text>已显示 {{ batchCatalog.length }} / {{ batchTotal }} 个批次</text>
          <button class="btn btn-ghost" :disabled="batchLoading" @click="loadMoreBatches">{{ batchLoading ? '读取中…' : '加载更多批次' }}</button>
        </view>
        <text class="sl__hero-desc">余量仅供参考，不是名额预留。</text>

        <MobileAcademicDecisionCard v-if="decisionError" class="sl__decision"
          :trace="decisionError.decisionTrace" :message="decisionError.message" audience="student" />

        <view v-if="receipt" class="sl__receipt" :class="'is-' + receipt.tone" role="status">
          <view class="sl__receipt-head">
            <view class="sl__receipt-mark"><text>{{ receipt.tone === 'success' ? '✓' : receipt.tone === 'danger' ? '!' : '…' }}</text></view>
            <view class="flex-1">
              <text class="sl__receipt-course">{{ receipt.courseName }}</text>
              <text class="sl__receipt-title">{{ receipt.label }}</text>
            </view>
          </view>
          <text class="sl__receipt-desc">{{ receipt.description }}</text>
          <button v-if="receipt.status === 'RESULT_UNKNOWN'" class="btn btn-ghost sl__receipt-action" :disabled="recordsState === 'loading'" @click="refreshRecords">重新核对本人记录</button>
          <button v-else-if="['SELECTED', 'LOCKED'].includes(receipt.status)" class="btn btn-ghost sl__receipt-action" @click="goSchedule">查看正式课表</button>
        </view>

        <view class="sl__tabs">
          <button class="sl__tab" :class="{ 'is-active': tab === 'courses' }" @click="tab = 'courses'">可办理课程 <text>{{ courseCount }}</text></button>
          <button class="sl__tab" :class="{ 'is-active': tab === 'mine' }" @click="tab = 'mine'">我的选课与报名 <text>{{ recordTotal }}</text></button>
        </view>

        <template v-if="tab === 'courses'">
          <view class="sl__search"><input v-model="searchDraft" placeholder="搜索课程、代码或老师" @confirm="searchCourses" /><button class="btn btn-ghost" @click="searchCourses">搜索</button></view>
          <view v-if="courseState === 'error'" class="sl__local-state is-error">
            <view class="flex-1"><text class="sl__local-title">课程暂时无法加载</text><text class="sl__local-desc">{{ courseError || '请检查网络后重试。本人记录不会因此显示为空。' }}</text></view>
            <button class="btn btn-ghost" @click="loadBatch(activeBatchId)">重试</button>
          </view>
          <view v-else-if="courseState === 'loading' && !activeGroups.length" class="sl__local-state"><text>正在读取当前批次课程…</text></view>
          <view v-if="courseStale" class="sl__stale"><text>当前显示上次已确认的课程快照，正在等待最新结果。</text></view>
          <AcademicPageState v-if="courseState === 'ready' && !activeGroups.length" state="empty"
            title="本批次暂无可办理课程" description="批次开放、补选资格或课程供给变化后，请重新加载。" />

          <view v-for="group in displayedGroups" :key="group.batch.batchId" class="sl__group">
            <view v-for="course in group.courses" :key="course.selectionCourseId" class="sl__course">
              <view class="sl__course-title-row" @click="toggleDetail(course)">
                <view class="sl__course-icon"><image :src="bookIcon" mode="aspectFit" /></view>
                <view class="flex-1">
                  <text class="sl__course-title">{{ course.courseName || '课程名称待补充' }}</text>
                  <text class="sl__course-meta">{{ course.courseCode || '课程代码待确认' }}</text>
                </view>
                <text v-if="courseRecord(course)" class="sl__status" :class="'is-' + statusMeta(courseRecord(course).status).tone">{{ statusMeta(courseRecord(course).status).label }}</text>
                <text v-else class="sl__detail-link">{{ detailId === String(course.selectionCourseId) ? '收起' : '详情' }}</text>
              </view>
              <text class="sl__course-meta sl__teacher">{{ course.teacherName || '教师待定' }} · {{ course.credit ?? '—' }} 学分</text>
              <text class="sl__course-schedule">{{ scheduleText(course) }}</text>
              <view class="sl__fact sl__course-summary"><text class="sl__mode" :class="{ 'is-lottery': isLottery(course) }">{{ selectionModeText(course) }}</text><text>{{ isLottery(course) ? '报名不占座' : '余量 ' + remainText(course) }}</text></view>
              <view class="sl__course-footer"><text>{{ courseDeadline(course) }}</text><button class="btn btn-ghost sl__details-button" @click="toggleDetail(course)">{{ detailId === String(course.selectionCourseId) ? '收起详情' : detailLabel(course) }}</button></view>
              <view v-if="detailId === String(course.selectionCourseId)" class="sl__course-detail">
                <view class="sl__fact"><text>课程代码</text><text>{{ course.courseCode || '待确认' }}</text></view>
                <view class="sl__fact"><text>选课方式</text><text>{{ selectionModeText(course) }}</text></view>
                <view class="sl__fact"><text>实时余量</text><text>{{ remainText(course) }}（仅供参考）</text></view>
                <view class="sl__fact"><text>当前动作</text><text>{{ actionText(course) }}</text></view>
                <view v-if="course.reason || course.howToResolve" class="sl__decision-hint">
                  <text v-if="course.reason">{{ course.reason }}</text><text v-if="course.howToResolve">下一步：{{ course.howToResolve }}</text>
                </view>
                <button v-if="unresolvedFor(course)" class="btn btn-ghost sl__primary-action" :disabled="recordsState === 'loading'" @click="refreshRecords">结果待核实 · 核对本人记录</button>
                <button v-else-if="hasAction(course, 'ENROLL')" class="btn btn-primary sl__primary-action" :disabled="!!acting || courseStale || courseState !== 'ready'" @click="enroll(course)">{{ acting === course.selectionCourseId ? '正在核对…' : enrollLabel(course) }}</button>
                <button v-else-if="hasAction(course, 'DROP')" class="btn btn-ghost sl__primary-action" :disabled="!!acting || courseStale || courseState !== 'ready'" @click="drop(course)">{{ acting === course.selectionCourseId ? '正在核对…' : '申请退课' }}</button>
              </view>
            </view>
          </view>
          <view v-if="courseTotal" class="sl__pages">
            <button class="btn btn-ghost" :disabled="coursePage <= 1 || courseState === 'loading'" @click="changeCoursePage(coursePage - 1)">上一页</button>
            <text>第 {{ coursePage }} / {{ Math.max(1, Math.ceil(courseTotal / 20)) }} 页，共 {{ courseTotal }} 门</text>
            <button class="btn btn-ghost" :disabled="!courseHasMore || courseState === 'loading'" @click="changeCoursePage(coursePage + 1)">下一页</button>
          </view>
          <text v-if="searchTerm && !courseTotal && courseState === 'ready'" class="sl__stale">当前批次没有匹配的课程</text>
        </template>

        <template v-else>
          <view v-if="recordsState === 'error'" class="sl__local-state is-error">
            <view class="flex-1"><text class="sl__local-title">本人选课记录暂时无法核对</text><text class="sl__local-desc">{{ recordsError || '请勿据此重复报名。网络恢复后重新核对。' }}</text></view>
            <button class="btn btn-ghost" @click="refreshRecords">重试</button>
          </view>
          <view v-else-if="recordsState === 'loading' && !visibleRecords.length" class="sl__local-state"><text>正在读取本人正式记录…</text></view>
          <view v-if="recordsStale" class="sl__stale"><text>以下为上次已确认记录，最新状态尚未取回。</text></view>
          <AcademicPageState v-if="recordsState !== 'loading' && recordsState !== 'error' && !visibleRecords.length" state="empty"
            :title="receipt && receipt.status === 'RESULT_UNKNOWN' ? '本次回读暂未查到记录' : '本批次暂无选课记录'" :description="receipt && receipt.status === 'RESULT_UNKNOWN' ? '本次操作仍待核实，请勿重复提交。稍后再核对本人记录。' : '这里会保留待抽签、已获名额、未中签、已退课与课程取消等正式状态。'" />
          <view v-for="record in visibleRecords" :key="record.recordId || record.selectionCourseId" class="sl__record">
            <view class="sl__record-head">
              <view class="flex-1">
                <text class="sl__course-title">{{ record.courseName || '课程名称待补充' }}</text>
                <text class="sl__course-meta">{{ record.credit ?? '—' }} 学分 · {{ recordTime(record) }}</text>
              </view>
              <text class="sl__status" :class="'is-' + statusMeta(record.status).tone">{{ statusMeta(record.status).label }}</text>
            </view>
            <text class="sl__record-desc">{{ statusMeta(record.status).description }}</text>
            <button v-if="unresolvedFor(record)" class="btn btn-ghost sl__record-action" :disabled="recordsState === 'loading'" @click="refreshRecords">结果待核实 · 核对本人记录</button>
            <button v-else-if="recordHasAction(record, 'DROP')" class="btn btn-ghost sl__record-action" :disabled="!!acting || courseStale || recordsStale" @click="drop(record)">{{ normalizeStatus(record.status) === 'PENDING_LOTTERY' ? '撤回抽签报名' : '申请退课' }}</button>
          </view>
          <view v-if="recordTotal" class="sl__pages">
            <button class="btn btn-ghost" :disabled="recordPage <= 1 || recordsState === 'loading'" @click="changeRecordPage(recordPage - 1)">上一页</button>
            <text>第 {{ recordPage }} / {{ Math.max(1, Math.ceil(recordTotal / 20)) }} 页，共 {{ recordTotal }} 条</text>
            <button class="btn btn-ghost" :disabled="!recordHasMore || recordsState === 'loading'" @click="changeRecordPage(recordPage + 1)">下一页</button>
          </view>
        </template>

        <view class="sl__rule-note">
          <text class="sl__rule-title">规则校验 · 办理后回读</text>
          <text>预检只核对当时条件，不占名额；按钮和余量也不承诺成功。写操作完成后，本页会重新读取本人正式记录。网络超时显示“结果待核实”，不会自动重放报名或退课。</text>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import MobileAcademicDecisionCard from '@/components/MobileAcademicDecisionCard.vue'
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'
import { findSelectionRecord, isPendingLottery, isUncertainSelectionError, isVisibleSelectionRecord, normalizeSelectionStatus, receiptFromRecord, selectionStatusMeta, recordConfirmsOperation } from './selection-state'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { canUpdatePendingCommand, createPendingCommand, readPending, savePending } from './pending-ledger'
import bookIcon from './book-open.svg'

const CONFIRMED_SEAT_STATUSES = ['SELECTED', 'LOCKED']

export default {
  components: { AcademicPageNav, AcademicPageState, MobileAcademicDecisionCard },
  data() {
    return {
      bookIcon, batchCatalog: [], courseCache: {}, recordCache: {}, activeBatchId: '', tab: 'courses', detailId: '',
      courseState: 'loading', recordsState: 'loading', courseError: '', recordsError: '', courseStale: false,
      recordsStale: false, loaded: false, acting: null, decisionError: null, receipt: null,
      requestEpoch: 0, recordsEpoch: 0, contextEpoch: 0, writeToken: 0, hidden: false,
      identity: currentSessionGeneration(), unresolved: {},
      searchDraft: '', searchTerm: '', batchPage: 1, batchTotal: 0, batchHasMore: false, batchLoading: false,
      coursePage: 1, courseTotal: 0, courseHasMore: false,
      recordPage: 1, recordTotal: 0, recordHasMore: false
    }
  },
  computed: {
    activeBatchIndex() { return Math.max(0, this.batchCatalog.findIndex(b => String(b.batchId) === this.activeBatchId)) },
    activeBatchName() { return this.batchCatalog.find(b => String(b.batchId) === this.activeBatchId)?.batchName || '请选择选课批次' },
    cacheKey() { return this.activeBatchId || '__all__' },
    activeGroups() { return this.courseCache[this.cacheKey] || [] },
    activeRecords() { return this.recordCache[this.cacheKey] || this.filterRecordsForBatch(this.recordCache.__all__ || [], this.activeBatchId) },
    visibleRecords() { return this.activeRecords.filter(isVisibleSelectionRecord) },
    confirmedRecords() { return this.visibleRecords.filter((record) => CONFIRMED_SEAT_STATUSES.includes(normalizeSelectionStatus(record && record.status))) },
    pendingRecords() { return this.visibleRecords.filter(isPendingLottery) },
    courseCount() { return this.courseTotal },
    displayedGroups() { return this.activeGroups },
    pageState() {
      if (!this.loaded) return 'loading'
      if (this.courseState === 'error' && this.recordsState === 'error' && !this.activeGroups.length && !this.activeRecords.length) return this.decisionError?.restricted ? 'forbidden' : 'error'
      return 'ready'
    }
  },
  onLoad() { this.load() },
  onShow() {
    const changed = this.identity !== currentSessionGeneration()
    if (changed) this.resetIdentity()
    if (this.hidden || changed) { this.hidden = false; this.loaded ? this.loadBatch(this.activeBatchId) : this.load() }
  },
  onHide() { this.hidden = true; this.invalidateContext() },
  onUnload() { this.hidden = true; this.invalidateContext() },
  methods: {
    normalizeStatus: normalizeSelectionStatus,
    statusMeta: selectionStatusMeta,
    normalizeGroups(value) { const rows = Array.isArray(value) ? value : value && value.groups; if (!Array.isArray(rows)) throw new Error('课程信息无法核对'); return rows },
    normalizeRecords(value) { const rows = Array.isArray(value) ? value : value && value.items; if (!Array.isArray(rows)) throw new Error('本人记录无法核对'); return rows },
    setCourseCache(key, value) { this.courseCache = { ...this.courseCache, [key]: value } },
    setRecordCache(key, value) { this.recordCache = { ...this.recordCache, [key]: value } },
    invalidateContext() { this.requestEpoch += 1; this.recordsEpoch += 1; this.contextEpoch += 1; this.writeToken += 1; this.acting = null },
    resetIdentity() {
      this.invalidateContext()
      this.identity = currentSessionGeneration()
      this.batchCatalog = []; this.courseCache = {}; this.recordCache = {}; this.unresolved = {}
      this.activeBatchId = ''; this.receipt = null; this.decisionError = null; this.detailId = ''; this.loaded = false
      this.searchDraft = ''; this.searchTerm = ''; this.tab = 'courses'
      this.batchPage = 1; this.batchTotal = 0; this.batchHasMore = false; this.batchLoading = false
      this.coursePage = 1; this.courseTotal = 0; this.courseHasMore = false
      this.recordPage = 1; this.recordTotal = 0; this.recordHasMore = false
    },
    isForbiddenSelectionError(reason) {
      const code = String(reason && reason.code || '').toUpperCase()
      return Number(reason && (reason.httpStatus || reason.statusCode || reason.code)) === 403 || /^403/.test(code) || code === 'FORBIDDEN' || code === 'NO_PERMISSION'
    },
    clearForbiddenSelectionContext(reason) {
      // A permission denial must not leave a previous student's batches, records
      // or allowed actions actionable while the next read is unavailable.
      const message = reason && reason.biz ? normalizeError(reason).text : '当前无权核对选课信息'
      // A denied read cannot establish the outcome of earlier writes.
      // Retain only original object references in the identity-scoped ledger.
      const pending = Object.fromEntries(Object.entries(this.unresolved).map(([key, item]) => [key, {
        operation: item.operation, selectionCourseId: item.selectionCourseId,
        selectionRecordId: item.selectionRecordId, batchId: item.batchId,
        commandId: item.commandId, returnedId: item.returnedId, _pendingOwner: item._pendingOwner
      }]))
      this.resetIdentity()
      savePending('selection', pending)
      this.courseState = 'error'; this.recordsState = 'error'; this.courseError = message; this.recordsError = message
      this.courseStale = false; this.recordsStale = false; this.loaded = true
      this.decisionError = { message, decisionTrace: (reason && reason.decisionTrace) || null, restricted: true, readSource: 'drop-preflight' }
    },
    identityMatches() { return !this.hidden && this.identity === currentSessionGeneration() },
    contextMatches(captured) { return this.identityMatches() && captured.contextEpoch === this.contextEpoch && captured.batchId === this.activeBatchId && captured.writeToken === this.writeToken },
    searchCourses() {
      this.searchTerm = this.searchDraft.trim(); this.coursePage = 1
      return this.activeBatchId ? this.readCourses(this.activeBatchId) : null
    },
    changeCoursePage(page) {
      if (page < 1 || page === this.coursePage || this.courseState === 'loading') return
      this.coursePage = page; this.detailId = ''; return this.readCourses(this.activeBatchId)
    },
    changeRecordPage(page) {
      if (page < 1 || page === this.recordPage || this.recordsState === 'loading') return
      this.recordPage = page; return this.readRecords(this.activeBatchId)
    },
    onBatchPick(event) { const batch = this.batchCatalog[Number(event.detail.value)]; if (batch) this.switchBatch(batch.batchId) },
    courseDeadline(course) { const end = String(course?.window?.endAt || '').replace('T', ' ').slice(5, 16); return end ? end + ' 截止' : '截止时间待学校发布' },
    unresolvedKey(courseId, batchId = this.activeBatchId) { return `${batchId}:${courseId}` },
    unresolvedFor(course) { return this.unresolved[this.unresolvedKey(course && course.selectionCourseId)] },
    recordAllowed(target, action) {
      if (this.courseState !== 'ready' || this.courseStale || this.unresolvedFor(target)) return false
      if (action === 'DROP' && (this.recordsState !== 'ready' || this.recordsStale)) return false
      return action === 'DROP' ? this.recordHasAction(target, action) : this.hasAction(target, action)
    },
    hasAction(target, action) {
      const wanted = String(action || '').toUpperCase()
      return Array.isArray(target && target.allowedActions) && target.allowedActions.some((value) => String(value || '').toUpperCase() === wanted)
    },
    recordHasAction(record, action) {
      if (Array.isArray(record && record.allowedActions)) return this.hasAction(record, action)
      const course = this.activeGroups.flatMap((group) => group.courses || []).find((item) => String(item.selectionCourseId) === String(record && record.selectionCourseId))
      return this.hasAction(course, action)
    },
    courseRecord(course) { return findSelectionRecord(this.activeRecords, course && course.selectionCourseId) },
    batchKicker(batch) {
      const status = normalizeSelectionStatus(batch && batch.status)
      return status === 'CLOSED' ? '已关闭或补选' : status === 'OPEN' ? '办理中' : (batch && batch.statusLabel) || '按学校时间办理'
    },
    batchWindow(batch) {
      const start = String(batch && (batch.windowStart || batch.startAt) || '').replace('T', ' ').slice(0, 16)
      const end = String(batch && (batch.windowEnd || batch.endAt) || '').replace('T', ' ').slice(0, 16)
      return start || end ? `${start || '已开始'} 至 ${end || '结束时间待确认'}` : '办理时间以学校发布为准'
    },
    selectionModeText(course) {
      const value = normalizeSelectionStatus(course && (course.lottery && course.lottery.mode || course.selectionMode || course.mode || course.method))
      return value.includes('LOTTERY') || String(course && course.method || '').includes('抽签') ? '抽签报名' : value === 'FCFS' ? '先到先得' : '按提交时规则确认'
    },
    isLottery(course) { return this.selectionModeText(course) === '抽签报名' },
    enrollLabel(course) { return this.isLottery(course) ? '报名参加抽签' : (course && course.reselect ? '提交补选' : '提交选课') },
    // 列表入口只陈述服务端下发的正式可执行动作，不能把“查看详情”伪装为“可选择”。
    detailLabel(course) {
      if (this.hasAction(course, 'ENROLL')) return this.isLottery(course) ? '查看并报名' : '查看并选择'
      if (this.hasAction(course, 'DROP')) return '查看退课条件'
      return '查看办理条件'
    },
    actionText(course) {
      if (this.hasAction(course, 'ENROLL')) return this.enrollLabel(course)
      if (this.hasAction(course, 'DROP')) return '可以申请退课'
      return (course && (course.statusLabel || course.reason)) || '当前不可办理'
    },
    scheduleText(course) {
      const week = { 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' }
      const rows = Array.isArray(course && course.scheduleItems) ? course.scheduleItems : []
      if (!rows.length) return '时间待排 · 以正式课表为准'
      return rows.map((row) => {
        const parity = row.weekParity === 'ODD' ? '单周' : row.weekParity === 'EVEN' ? '双周' : ''
        return [week[Number(row.weekday)] || `周${row.weekday}`, `第${row.slotNo}节`, parity, row.classroom].filter(Boolean).join(' · ')
      }).join('；')
    },
    remain(course) {
      if (course && Object.prototype.hasOwnProperty.call(course, 'remain') && (course.remain == null || course.remain === '')) return null
      if (course && course.remain !== null && course.remain !== undefined && Number.isFinite(Number(course.remain))) return Number(course.remain)
      const capacity = course && course.capacity != null ? Number(course.capacity) : NaN
      const count = course && (course.selectedCount ?? course.enrolledCount)
      const selected = count != null ? Number(count) : NaN
      return Number.isFinite(capacity) && Number.isFinite(selected) ? Math.max(0, capacity - selected) : null
    },
    remainText(course) {
      const remain = this.remain(course)
      const capacity = Number(course && course.capacity)
      if (remain === null) return '未知'
      return Number.isFinite(capacity) ? `${remain}/${capacity}` : String(remain)
    },
    recordTime(record) { return String(record && (record.updatedAt || record.enrolledAt || record.createdAt) || '').replace('T', ' ').slice(0, 16) || '时间待确认' },
    toggleDetail(course) { const id = String(course && course.selectionCourseId || ''); this.detailId = this.detailId === id ? '' : id },
    goSchedule() { uni.navigateTo({ url: '/pages/student/academic-affairs/schedule' }) },
    filterRecordsForBatch(records, batchId) {
      if (!batchId) return records
      return records.filter((record) => record && String(record.batchId) === String(batchId))
    },
    consumeReadError(kind, reason) {
      const message = reason && reason.biz ? normalizeError(reason).text : '网络异常，请稍后重试'
      if (reason && reason.biz) this.decisionError = { message, decisionTrace: reason.decisionTrace || null, readSource: kind, restricted: Number(reason.httpStatus) === 403 || /^403/.test(String(reason.code || '')) }
      if (kind === 'courses') { this.courseError = message; this.courseState = 'error'; this.courseStale = !!this.activeGroups.length }
      else { this.recordsError = message; this.recordsState = 'error'; this.recordsStale = !!this.activeRecords.length }
    },
    mergeBatches(rows) {
      const catalog = new Map(this.batchCatalog.map((batch) => [String(batch.batchId), batch]))
      rows.forEach((row) => {
        if (row && row.batchId && !catalog.has(String(row.batchId))) catalog.set(String(row.batchId), { batchId: String(row.batchId), batchName: row.batchName || '历史选课批次' })
      })
      this.batchCatalog = [...catalog.values()]
    },
    async load() {
      if (this.identity !== currentSessionGeneration()) this.resetIdentity()
      this.unresolved = readPending('selection') || {}
      if (!this.activeBatchId) {
        this.batchPage = 1
        const catalog = await this.readBatchCatalog(true)
        if (!this.identityMatches()) return null
        if (catalog === null) return null
        if (!this.activeBatchId) {
          this.courseState = 'ready'; this.recordsState = 'ready'; this.loaded = true
          return catalog
        }
      }
      return this.loadBatch(this.activeBatchId)
    },
    readBatchCatalog(reset = false, requestedPage = reset ? 1 : this.batchPage) {
      const epoch = (this._batchEpoch || 0) + 1
      this._batchEpoch = epoch
      const context = this.contextEpoch
      const page = Number(requestedPage)
      if (!Number.isSafeInteger(page) || page < 1) return Promise.resolve(null)
      this.batchLoading = true
      return studentApi.getSelectionBatches({ page, pageSize: 20 }).then((value) => {
        if (!this.identityMatches() || context !== this.contextEpoch || this._batchEpoch !== epoch) return null
        const rows = value && value.items
        if (!Array.isArray(rows)) throw new Error('选课批次信息无法核对')
        const catalog = new Map((reset ? [] : this.batchCatalog).map((batch) => [String(batch.batchId), batch]))
        rows.forEach((batch) => { if (batch && batch.batchId) catalog.set(String(batch.batchId), batch) })
        this.batchCatalog = [...catalog.values()]
        this.batchTotal = Number(value.total != null ? value.total : this.batchCatalog.length)
        this.batchHasMore = !!value.hasMore
        this.batchPage = page
        if (!this.activeBatchId && this.batchCatalog.length) this.activeBatchId = String(this.batchCatalog[0].batchId)
        return this.batchCatalog
      }).catch((reason) => {
        if (!this.identityMatches() || context !== this.contextEpoch || this._batchEpoch !== epoch) return null
        this.consumeReadError('courses', reason); this.recordsState = 'error'; this.recordsError = this.courseError
        return null
      }).finally(() => {
        if (this._batchEpoch === epoch && context === this.contextEpoch) { this.batchLoading = false; this.loaded = true }
      })
    },
    loadMoreBatches() {
      if (!this.batchHasMore || this.batchLoading) return null
      return this.readBatchCatalog(false, this.batchPage + 1)
    },
    switchBatch(batchId) {
      const next = String(batchId || '')
      if (!next || next === this.activeBatchId) return
      this.invalidateContext()
      this.activeBatchId = next; this.detailId = ''; this.receipt = null; this.decisionError = null
      this.coursePage = 1; this.recordPage = 1; this.searchDraft = ''; this.searchTerm = ''
      this.courseTotal = 0; this.courseHasMore = false; this.recordTotal = 0; this.recordHasMore = false
      const pending = Object.values(this.unresolved).find((item) => item.batchId === next)
      if (pending) this.showUnknown(pending)
      return this.loadBatch(next)
    },
    loadBatch(batchId) {
      if (!batchId) return Promise.resolve([])
      return Promise.allSettled([this.readCourses(String(batchId || '')), this.readRecords(String(batchId || ''))])
    },
    readCourses(capturedBatch) {
      const epoch = ++this.requestEpoch
      const context = this.contextEpoch
      const key = capturedBatch
      const current = () => this.identityMatches() && context === this.contextEpoch && this.requestEpoch === epoch && this.activeBatchId === capturedBatch
      this.courseState = 'loading'; this.courseStale = !!this.activeGroups.length; this.courseError = ''
      return studentApi.getSelectionCoursesPage({ batchId: capturedBatch, keyword: this.searchTerm, page: this.coursePage, pageSize: 20 }).then((value) => {
        if (!current()) return null
        if (!value || !value.batch || !Array.isArray(value.items)) throw new Error('课程信息无法核对')
        const total = Number(value.total)
        const maxPage = Math.max(1, Math.ceil((Number.isFinite(total) ? total : 0) / 20))
        if (this.coursePage > maxPage) {
          this.coursePage = maxPage
          return this.readCourses(capturedBatch)
        }
        this.courseTotal = Number.isFinite(total) && total >= 0 ? total : value.items.length
        this.courseHasMore = !!value.hasMore
        this.setCourseCache(key, [{ batch: value.batch, courses: value.items }])
        this.courseState = 'ready'; this.courseStale = false; this.loaded = true
        if (this.recordsState === 'ready' && this.decisionError?.readSource) this.decisionError = null
        const pending = Object.values(this.unresolved).find(item => item.batchId === this.activeBatchId)
        if (pending) this.showUnknown(pending)
        return value.items
      }).catch((reason) => {
        if (!current()) return null
        this.consumeReadError('courses', reason); this.loaded = true
        return null
      }).finally(() => {
        if (!current()) return
        this.loaded = true
      })
    },
    readRecords(batchId) {
      const epoch = ++this.recordsEpoch
      const context = this.contextEpoch
      const key = batchId
      const current = () => this.identityMatches() && this.recordsEpoch === epoch && context === this.contextEpoch
      this.recordsState = 'loading'; this.recordsStale = !!this.activeRecords.length; this.recordsError = ''
      return studentApi.getMySelectionsPage({ batchId, page: this.recordPage, pageSize: 20 }).then((value) => {
        if (!current()) return null
        if (!value || !Array.isArray(value.items)) throw new Error('本人记录无法核对')
        const total = Number(value.total)
        const maxPage = Math.max(1, Math.ceil((Number.isFinite(total) ? total : 0) / 20))
        if (this.recordPage > maxPage) {
          this.recordPage = maxPage
          return this.readRecords(batchId)
        }
        const records = value.items
        this.recordTotal = Number.isFinite(total) && total >= 0 ? total : records.length
        this.recordHasMore = !!value.hasMore
        this.setRecordCache(key, records)
        this.recordsState = 'ready'; this.recordsStale = false; this.loaded = true
        if (this.courseState === 'ready' && this.decisionError?.readSource) this.decisionError = null
        this.reconcilePending(records, batchId)
        return records
      }).catch((reason) => {
        if (!current()) return null
        this.consumeReadError('records', reason); this.loaded = true
        return null
      }).finally(() => {
        if (!current()) return
        this.loaded = true
      })
    },
    readExactRecord(captured) {
      if (!captured || !captured.batchId || !captured.selectionCourseId) return Promise.resolve(null)
      const context = this.contextEpoch
      return studentApi.getMySelectionsPage({
        batchId: captured.batchId, selectionCourseId: captured.selectionCourseId, page: 1, pageSize: 1
      }).then((value) => {
        if (!this.identityMatches() || context !== this.contextEpoch || this.activeBatchId !== captured.batchId) return null
        const records = value && value.items
        if (!Array.isArray(records)) return null
        return records.find((item) => String(item && item.selectionCourseId) === String(captured.selectionCourseId)) || null
      }).catch(() => null)
    },
    async refreshRecords() {
      const batchId = this.activeBatchId; const context = this.contextEpoch
      const unresolvedCount = Object.keys(this.unresolved).length
      const records = await this.readRecords(batchId)
      if (this.identityMatches() && context === this.contextEpoch && batchId === this.activeBatchId && Object.keys(this.unresolved).length < unresolvedCount) await this.readCourses(batchId)
      return records
    },
    showUnknown(captured) {
      this.receipt = { ...selectionStatusMeta('RESULT_UNKNOWN'), status: 'RESULT_UNKNOWN', courseName: captured.courseName, selectionCourseId: captured.selectionCourseId, operation: captured.operation }
    },
    reconcilePending(records, batchId) {
      const next = { ...this.unresolved }
      let receipt = null
      Object.entries(next).forEach(([key, captured]) => {
        if (batchId && captured.batchId !== batchId) return
        const record = records.find((item) => String(item.batchId) === captured.batchId && String(item.selectionCourseId) === captured.selectionCourseId)
        // Both an active page and a cold start need the original command receipt.
        // Another device or an older operation may already have changed this course record.
        if (!captured.returnedId || String(record?.recordId || '') !== String(captured.returnedId)) return
        if (!recordConfirmsOperation(record, captured.operation)) return
        delete next[key]
        if (captured.batchId === this.activeBatchId) receipt = { ...receiptFromRecord(record, captured.courseName), selectionCourseId: captured.selectionCourseId }
      })
      if (!savePending('selection', next)) {
        if (receipt) this.decisionError = { message: '学校记录已读取，但本机无法安全清除待核对引用；请稍后再次核对，切勿重复提交。', decisionTrace: null }
        return
      }
      this.unresolved = next
      if (receipt) this.receipt = receipt
    },
    captureAction(course, operation) {
      const selectionCourseId = String(course && course.selectionCourseId || '')
      const record = operation === 'DROP' ? findSelectionRecord(this.activeRecords, selectionCourseId) || course : null
      return { operation, selectionCourseId, selectionRecordId: String(record && record.recordId || ''), courseName: (course && course.courseName) || '当前课程', batchId: this.activeBatchId, contextEpoch: this.contextEpoch, writeToken: ++this.writeToken, lottery: this.isLottery(course), courseEpoch: this.requestEpoch }
    },
    confirmedTarget(captured) {
      if (!this.contextMatches(captured) || captured.courseEpoch !== this.requestEpoch) return null
      const course = this.activeGroups.flatMap((group) => group.courses || []).find((item) => String(item.selectionCourseId) === captured.selectionCourseId)
      if (course && this.recordAllowed(course, captured.operation)) return course
      // The student's own record can be on a different course page.  Its server
      // allowedActions remain authoritative for a DROP; do not force a full course
      // list just to reopen the same formal record.
      const record = captured.operation === 'DROP' && findSelectionRecord(this.activeRecords, captured.selectionCourseId)
      return record && this.recordAllowed(record, captured.operation) ? record : null
    },
    matchesDropPreflight(captured, preflight) {
      return !!preflight && preflight.allowed === true && String(preflight.action || '').toUpperCase() === 'DROP' &&
        String(preflight.selectionCourseId || '') === captured.selectionCourseId &&
        String(preflight.batchId || '') === captured.batchId &&
        String(preflight.selectionRecordId || '') === captured.selectionRecordId
    },
    enroll(course) {
      if (this.acting || !this.hasAction(course, 'ENROLL') || !this.recordAllowed(course, 'ENROLL')) return
      const captured = this.captureAction(course, 'ENROLL')
      this.acting = captured.selectionCourseId
      const content = captured.lottery ? '本次只登记抽签报名，不承诺名额。提交后以“已报名待抽签”记录为准。' : '余量不是名额承诺。服务器会再次校验容量、冲突、窗口和培养方案。'
      uni.showModal({
        title: captured.lottery ? '确认参加抽签' : '确认提交选课',
        content: captured.courseName + '\n' + content, confirmText: captured.lottery ? '确认报名' : '确认提交',
        success: (result) => {
          if (!this.contextMatches(captured)) return
          if (!result.confirm || !this.confirmedTarget(captured)) { this.acting = null; return }
          return this.runEnroll(captured)
        },
        fail: () => { if (this.contextMatches(captured)) this.acting = null }
      })
    },
    async runEnroll(captured) {
      if (!this.confirmedTarget(captured)) return
      this.decisionError = null; this.receipt = null
      let sent = false
      try {
        const preflight = await studentApi.preflightSelection(captured.selectionCourseId)
        if (!this.contextMatches(captured)) return
        if (!preflight || preflight.allowed !== true) {
          this.decisionError = { message: (preflight && preflight.message) || '当前课程未通过选课预检', decisionTrace: (preflight && preflight.decisionTrace) || null }
          return
        }
        if (!this.confirmedTarget(captured)) return
        if (!this.startWrite(captured)) {
          this.decisionError = { message: '本机无法安全保存本次选课的核对引用，尚未发送选课申请。请恢复存储后重试。', decisionTrace: null }
          return
        }
        sent = true
        const result = await studentApi.enrollSelection(captured.selectionCourseId)
        if (this.contextMatches(captured)) this.captureWriteReceipt(captured, result)
        // Even an empty transport payload must be reconciled with formal records.
        if (this.contextMatches(captured)) await this.reconcileWrite(captured)
      } catch (error) {
        if (!this.contextMatches(captured)) return
        if (!sent) {
          this.decisionError = { message: error && error.biz ? normalizeError(error).text : '预检暂时无法完成，尚未发送选课申请', decisionTrace: (error && error.decisionTrace) || null }
          return
        }
        await this.handleWriteError(error, captured)
      } finally {
        if (this.contextMatches(captured)) this.acting = null
      }
    },
    drop(courseOrRecord) {
      if (this.acting || (!this.recordHasAction(courseOrRecord, 'DROP') && !this.hasAction(courseOrRecord, 'DROP')) || !this.recordAllowed(courseOrRecord, 'DROP')) return
      const captured = this.captureAction(courseOrRecord, 'DROP')
      if (!captured.selectionRecordId) {
        this.decisionError = { message: '本人正式选课记录尚未完整返回，暂不能发起退课。请刷新后重试。', decisionTrace: null }
        return
      }
      this.acting = captured.selectionCourseId
      const current = findSelectionRecord(this.activeRecords, captured.selectionCourseId) || courseOrRecord
      const pending = normalizeSelectionStatus(current && current.status) === 'PENDING_LOTTERY'
      uni.showModal({
        title: pending ? '撤回抽签报名' : '确认申请退课',
        content: captured.courseName + '\n是否允许办理，以服务器当前状态和允许动作为准。',
        confirmText: pending ? '确认撤回' : '确认退课',
        success: (result) => {
          if (!this.contextMatches(captured)) return
          if (!result.confirm || !this.confirmedTarget(captured)) { this.acting = null; return }
          return this.runDrop(captured)
        },
        fail: () => { if (this.contextMatches(captured)) this.acting = null }
      })
    },
    async runDrop(captured) {
      if (!this.confirmedTarget(captured)) return
      this.decisionError = null; this.receipt = null
      let sent = false
      try {
        const preflight = await studentApi.preflightDropSelection(captured.selectionCourseId)
        if (!this.contextMatches(captured)) return
        if (!this.matchesDropPreflight(captured, preflight)) {
          this.decisionError = { message: (preflight && (preflight.message || preflight.reason)) || '当前记录未通过退课预检', decisionTrace: (preflight && preflight.decisionTrace) || null }
          return
        }
        if (!this.confirmedTarget(captured)) return
        if (!this.startWrite(captured)) {
          this.decisionError = { message: '本机无法安全保存本次退课的核对引用，尚未发送退课申请。请恢复存储后重试。', decisionTrace: null }
          return
        }
        sent = true
        const result = await studentApi.dropSelection(captured.selectionCourseId)
        if (this.contextMatches(captured)) this.captureWriteReceipt(captured, result)
        if (this.contextMatches(captured)) await this.reconcileWrite(captured)
      } catch (error) {
        if (!this.contextMatches(captured)) return
        if (!sent) {
          if (this.isForbiddenSelectionError(error)) {
            this.clearForbiddenSelectionContext(error)
            return
          }
          this.decisionError = { message: error && error.biz ? normalizeError(error).text : '退课预检暂时无法完成，尚未发送退课申请', decisionTrace: (error && error.decisionTrace) || null }
          return
        }
        await this.handleWriteError(error, captured)
      } finally {
        if (this.contextMatches(captured)) this.acting = null
      }
    },
    startWrite(captured) {
      // Invalidate reads started before this command; keep the unresolved object
      // across batch navigation until a later read proves this operation.
      const command = createPendingCommand('selection', { ...captured, returnedId: '' })
      if (!command) return false
      this.requestEpoch += 1; this.recordsEpoch += 1
      const unresolved = { ...this.unresolved, [this.unresolvedKey(captured.selectionCourseId, captured.batchId)]: command }
      if (!savePending('selection', unresolved)) return false
      Object.assign(captured, command)
      this.courseStale = true
      this.unresolved = unresolved
      this.decisionError = null; this.showUnknown(captured)
      return true
    },
    captureWriteReceipt(captured, result) {
      const returnedId = String(result?.recordId || '')
      if (!returnedId) return false
      const key = this.unresolvedKey(captured.selectionCourseId, captured.batchId)
      const original = this.unresolved[key]
      if (!original || original.commandId !== captured.commandId || !canUpdatePendingCommand('selection', original)) return false
      const next = { ...this.unresolved, [key]: { ...original, returnedId } }
      if (!savePending('selection', next)) {
        this.decisionError = { message: '已收到学校回执，但本机无法安全保存回执编号；请保持页面并重新核对，切勿重复提交。', decisionTrace: null }
        return false
      }
      this.unresolved = next
      captured.returnedId = returnedId
      return true
    },
    async handleWriteError(error, captured) {
      if (!isUncertainSelectionError(error)) {
        const next = { ...this.unresolved }; delete next[this.unresolvedKey(captured.selectionCourseId, captured.batchId)]
        if (!savePending('selection', next)) {
          this.showUnknown(captured)
          this.decisionError = { message: '本机无法安全清除待核对引用；请恢复存储后核对，切勿重复提交。', decisionTrace: null }
          return
        }
        this.unresolved = next
        this.receipt = null
        this.decisionError = { message: error && error.biz ? normalizeError(error).text : '当前请求未通过', decisionTrace: (error && error.decisionTrace) || null }
        await this.refreshRecords()
        if (this.contextMatches(captured)) await this.readCourses(captured.batchId)
        return
      }
      this.showUnknown(captured); this.tab = 'mine'
      await this.reconcileWrite(captured)
    },
    async reconcileWrite(captured) {
      if (!this.contextMatches(captured)) return null
      const records = await this.readRecords(captured.batchId)
      if (!this.contextMatches(captured)) return null
      const exactRecord = await this.readExactRecord(captured)
      if (!this.contextMatches(captured)) return null
      if (exactRecord) this.reconcilePending([...(records || []), exactRecord], captured.batchId)
      this.tab = 'mine'
      if (this.unresolved[this.unresolvedKey(captured.selectionCourseId, captured.batchId)]) {
        this.showUnknown(captured)
      } else if (this.receipt) {
        uni.showToast({ title: this.receipt.label, icon: this.receipt.tone === 'success' ? 'success' : 'none' })
        await this.readCourses(captured.batchId)
      }
      return records
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.sl { padding-bottom: calc(var(--space-6) + env(safe-area-inset-bottom)); }
.sl__hero { padding: 4px 0 12px; }
.sl__search { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.sl__batch-more, .sl__pages { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-top:12px; color:var(--text-secondary); font-size:12px; }
.sl__batch-more button, .sl__pages button { margin:0; font-size:12px; }
.sl__search input { flex: 1; min-width: 0; height: 42px; padding: 0 12px; background: var(--bg-card); border: 1px solid var(--border-base); border-radius: 10px; font-size: 14px; }
.sl__search button { margin: 0; font-size: 13px; }
.sl__course-summary { margin-top: 12px; }
.sl__details-button { margin: 14px 0 0; font-size: 13px; }
.sl__eyebrow { display:block; color:var(--text-secondary); font-size:12px; }
.sl__batch-picker { display: inline-block; padding: 10px 14px; background: var(--bg-card); border: 1px solid var(--border-base); border-radius: 8px; font-size: 14px; }
.sl__course-icon { width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; background: var(--brand-50, #edf3fc); border-radius: 12px; }
.sl__course-icon image { width: 22px; height: 22px; }
.sl__teacher { padding-top: 10px; }
.sl__course-footer { display: flex; align-items: center; justify-content: space-between; gap: 10px; border-top: 1px solid var(--border-light); padding-top: 12px; margin-top: 10px; font-size: 12px; color: var(--text-secondary); }
.sl__course-footer button { margin: 0; font-size: 12px; }
.sl__hero-title { display:block; margin-top:5px; color:var(--text-primary); font-size:20px; font-weight:700; }
.sl__hero-desc { display:block; margin-top:6px; color:var(--text-secondary); font-size:var(--font-size-xs); line-height:1.7; }
.sl__trust { display:flex; flex-wrap:wrap; gap:6px; margin-top:var(--space-3); }
.sl__trust text { padding:3px 8px; border-radius:var(--radius-full); background:rgba(255,255,255,.88); color:var(--text-secondary); font-size:10px; }
.sl__batch-scroll { width:100%; margin-top:var(--space-3); white-space:nowrap; }
.sl__batch-row { display:inline-flex; gap:8px; padding:1px; }
.sl__batch { display:inline-flex; flex-direction:column; min-width:138px; padding:9px 12px; border:1px solid var(--border-light); border-radius:12px; background:var(--bg-card); color:var(--text-primary); text-align:left; font-size:var(--font-size-sm); }
.sl__batch.is-active { border-color:var(--brand-primary); background:rgba(59,130,246,.08); color:var(--brand-primary); }
.sl__batch-status { display:block; margin-top:2px; color:var(--text-tertiary); font-size:10px; }
.sl__metrics { display:grid; grid-template-columns:repeat(3,1fr); gap:var(--space-2); margin-top:var(--space-3); }
.sl__metric { padding:11px 8px; border:1px solid var(--border-light); border-radius:13px; background:var(--bg-card); text-align:center; box-shadow:var(--shadow-card); color:var(--text-tertiary); font-size:10px; }
.sl__metric-value { display:block; margin-bottom:2px; color:var(--text-primary); font-size:21px; font-weight:700; }
.sl__decision,.sl__receipt,.sl__tabs,.sl__group,.sl__local-state,.sl__record,.sl__rule-note { margin-top:var(--space-3); }
.sl__receipt { padding:var(--space-4); border:1px solid rgba(217,119,6,.28); border-radius:16px; background:#fffbeb; }
.sl__receipt.is-success { border-color:rgba(22,163,74,.24); background:#f0fdf4; }
.sl__receipt.is-danger { border-color:rgba(220,38,38,.22); background:#fef2f2; }
.sl__receipt.is-muted { border-color:var(--border-light); background:var(--bg-card); }
.sl__receipt-head { display:flex; align-items:center; gap:var(--space-3); }
.sl__receipt-mark { display:flex; align-items:center; justify-content:center; width:36px; height:36px; border-radius:50%; background:rgba(217,119,6,.12); color:#b45309; font-weight:800; }
.sl__receipt.is-success .sl__receipt-mark { background:rgba(22,163,74,.13); color:#15803d; }
.sl__receipt.is-danger .sl__receipt-mark { background:rgba(220,38,38,.11); color:#b91c1c; }
.sl__receipt-course { display:block; color:var(--text-secondary); font-size:10px; }
.sl__receipt-title { display:block; margin-top:2px; color:var(--text-primary); font-size:var(--font-size-base); font-weight:700; }
.sl__receipt-desc { display:block; margin-top:var(--space-3); color:var(--text-secondary); font-size:var(--font-size-xs); line-height:1.65; }
.sl__receipt-action { width:100%; margin-top:var(--space-3); }
.sl__tabs { display:flex; border-bottom:1px solid var(--border-light); margin-bottom:14px; }
.sl__tab { flex:1; min-height:44px; border-radius:0; color:var(--text-secondary); font-size:14px; background:transparent; }
.sl__tab::after { border:0; }
.sl__tab text { margin-left:4px; color:var(--text-tertiary); font-size:10px; }
.sl__tab.is-active { border-bottom:3px solid var(--brand-primary); color:var(--brand-primary); font-weight:600; }
.sl__local-state { display:flex; align-items:center; gap:var(--space-3); padding:var(--space-3); border:1px solid var(--border-light); border-radius:13px; background:var(--bg-card); color:var(--text-secondary); font-size:var(--font-size-xs); }
.sl__local-state.is-error { border-color:rgba(220,38,38,.18); background:#fff7f7; }
.sl__local-title { display:block; color:var(--text-primary); font-weight:600; }
.sl__local-desc { display:block; margin-top:2px; line-height:1.55; }
.sl__stale { margin-top:var(--space-2); padding:8px 10px; border-radius:10px; background:#fffbeb; color:#92400e; font-size:10px; }
.sl__group { display:flex; flex-direction:column; gap:14px; }
.sl__group-head { display:flex; align-items:center; gap:var(--space-3); padding:var(--space-3) var(--space-4); border-bottom:1px solid var(--border-light); }
.sl__group-kicker { display:block; color:var(--brand-primary); font-size:9px; font-weight:700; letter-spacing:1px; }
.sl__group-title { display:block; margin-top:2px; color:var(--text-primary); font-size:var(--font-size-base); font-weight:700; }
.sl__group-time { display:block; margin-top:3px; color:var(--text-tertiary); font-size:10px; }
.sl__group-count { color:var(--text-tertiary); font-size:11px; }
.sl__course { padding:14px; border:1px solid var(--border-base); border-radius:12px; background:var(--bg-card); }
.sl__course-title-row,.sl__record-head { display:flex; align-items:flex-start; gap:var(--space-2); }
.sl__course-title { display:block; color:var(--text-primary); font-size:16px; font-weight:600; line-height:1.45; }
.sl__course-meta,.sl__course-schedule { display:block; margin-top:4px; color:var(--text-secondary); font-size:13px; line-height:1.6; }
.sl__course-schedule { margin-top:10px; color:var(--text-primary); }
.sl__detail-link { flex-shrink:0; color:var(--brand-primary); font-size:var(--font-size-xs); }
.sl__status { flex-shrink:0; padding:3px 7px; border-radius:var(--radius-full); background:rgba(217,119,6,.10); color:#92400e; font-size:10px; }
.sl__status.is-success { background:rgba(22,163,74,.10); color:#15803d; }
.sl__status.is-danger { background:rgba(220,38,38,.09); color:#b91c1c; }
.sl__status.is-muted { background:rgba(100,116,139,.09); color:var(--text-secondary); }
.sl__course-detail { margin-top:var(--space-3); padding-top:var(--space-3); border-top:1px solid var(--border-light); }
.sl__fact { display:flex; justify-content:space-between; gap:var(--space-3); padding:5px 0; font-size:var(--font-size-xs); }
.sl__fact text:first-child { color:var(--text-tertiary); }
.sl__fact text:last-child { color:var(--text-primary); text-align:right; }
.sl__course-summary text.sl__mode { padding:2px 6px; border-radius:4px; color:var(--brand-primary); background:var(--brand-50, #edf3fc); }
.sl__course-summary .sl__mode.is-lottery { color:#92400e; background:#fff6e6; }
.sl__decision-hint { margin-top:var(--space-2); padding:9px 10px; border-radius:10px; background:#fffbeb; }
.sl__decision-hint text { display:block; color:#92400e; font-size:10px; line-height:1.55; }
.sl__primary-action { width:100%; margin-top:var(--space-3); }
.sl__record { padding:var(--space-4); border:1px solid var(--border-light); border-radius:15px; background:var(--bg-card); box-shadow:var(--shadow-card); }
.sl__record-desc { display:block; margin-top:var(--space-3); color:var(--text-secondary); font-size:var(--font-size-xs); line-height:1.6; }
.sl__record-action { width:100%; margin-top:var(--space-3); }
.sl__rule-note { padding:var(--space-3) var(--space-4); border:1px solid rgba(59,130,246,.12); border-radius:14px; background:rgba(229,237,252,.55); color:var(--text-secondary); font-size:var(--font-size-xs); line-height:1.7; }
.sl__rule-title { display:block; margin-bottom:3px; color:var(--text-primary); font-weight:600; }
</style>
