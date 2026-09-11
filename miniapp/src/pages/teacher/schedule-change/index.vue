<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="调停课管理" subtitle="调课 · 停课 · 补课" :before-back="backToApplications" show-back />

    <view class="sc__tabs">
      <view class="sc__tab" :class="{ 'is-on': tab === 'list' }" @click="switchTab('list')">
        我的申请<text v-if="changes.length" class="sc__tab-badge">{{ changes.length }}</text>
        <text v-if="tab === 'list'" class="sc__tab-u" />
      </view>
      <view class="sc__tab" :class="{ 'is-on': tab === 'new' }" @click="switchTab('new')">
        发起申请
        <text v-if="tab === 'new'" class="sc__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 我的申请 -->
      <view class="page-pad" v-if="tab === 'list'">
        <view v-if="receipt" class="card sc__receipt" role="status">
          <text class="sc__receipt-title">✓ {{ receipt.title }}</text>
          <text class="sc__receipt-sub">{{ receipt.courseName }} · 单据 {{ receipt.changeId }}</text>
          <view class="sc__row"><text class="sc__row-k">当前结果</text><text class="flex-1 t-sm">{{ receipt.result }}</text></view>
          <view class="sc__row" style="border-bottom:none;"><text class="sc__row-k">下一步</text><text class="flex-1 t-sm">{{ receipt.next }}</text></view>
        </view>
        <MobileGlobalState v-if="!changes.length" state="empty" title="暂无调停课申请"
          description="点击「发起申请」新建调课/停课/补课申请。" />
        <view class="stack" v-else>
          <view v-for="x in visibleChanges" :key="x.changeId" class="card sc">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.changeTypeLabel }} · {{ x.courseName || '—' }}</text>
                <text class="sc__sub">{{ x.className || '' }}</text>
              </view>
              <MobileStatusTag :label="statusLabel(x.status)" :type="statusTone(x.status)" />
            </view>
            <view class="sc__row"><text class="sc__row-k">原课位</text><text class="flex-1 t-sm">周{{ (x.origin || {}).weekday }}第{{ (x.origin || {}).slotNo }}节 {{ (x.origin || {}).classroom || '' }}</text></view>
            <view class="sc__row" v-if="x.changeType !== 'STOP'"><text class="sc__row-k">目标</text><text class="flex-1 t-sm">周{{ (x.target || {}).weekday }}第{{ (x.target || {}).slotNo }}节 {{ (x.target || {}).classroom || '' }}</text></view>
            <view class="sc__row"><text class="sc__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <view class="sc__actions" v-if="cancellable(x.status)">
              <button class="btn btn-ghost flex-1" :disabled="acting || hasUnknownWrite('cancel', x.changeId)" @click="doCancel(x)">{{ hasUnknownWrite('cancel', x.changeId) ? '等待核对撤销结果' : '撤销申请' }}</button>
            </view>
          </view>
        </view>
      </view>

      <view v-if="tab === 'list' && changes.length > 20" class="page-pad sc__pages">
        <button class="btn btn-ghost" :disabled="changePageIndex === 0" @click="changePage = changePageIndex - 1">上一组</button>
        <text>{{ changePageIndex + 1 }} / {{ Math.ceil(changes.length / 20) }}</text>
        <button class="btn btn-ghost" :disabled="(changePageIndex + 1) * 20 >= changes.length" @click="changePage = changePageIndex + 1">下一组</button>
      </view>
      <!-- 发起申请 -->
      <view class="page-pad" v-if="tab === 'new'">
        <MobileGlobalState v-if="scheduleState === 'loading'" state="loading" title="正在核对正式课位" />
        <MobileGlobalState v-else-if="scheduleState === 'error'" state="error" title="正式课位加载失败" @retry="loadSchedule" />
        <text v-if="scheduleError" class="sc__conflict-bad">{{ scheduleError }}</text>
        <view class="card sc__form">
          <view class="sc__row">
            <text class="sc__row-k">原课位</text>
            <picker :disabled="submitting" class="sc__picker" mode="selector" :range="itemLabels" :value="itemIndex" @change="onItem">
              <view class="sc__pick-val">{{ itemLabels[itemIndex] || '请选择' }}<text class="sc__arrow">▾</text></view>
            </picker>
          </view>
          <view class="sc__row">
            <text class="sc__row-k">类型</text>
            <picker :disabled="submitting" class="sc__picker" mode="selector" :range="typeLabels" :value="typeIndex" @change="onType">
              <view class="sc__pick-val">{{ typeLabels[typeIndex] }}<text class="sc__arrow">▾</text></view>
            </picker>
          </view>

          <template v-if="typeKey !== 'STOP'">
            <view class="sc__row"><text class="sc__row-k">目标星期</text><input :disabled="submitting" class="sc__input" type="number" v-model="targetWeekday" placeholder="1-7" @input="invalidateConflict" /></view>
            <view class="sc__row"><text class="sc__row-k">目标节次</text><input :disabled="submitting" class="sc__input" type="number" v-model="targetSlotNo" placeholder="如 1" @input="invalidateConflict" /></view>
            <view class="sc__row"><text class="sc__row-k">起止周</text>
              <input :disabled="submitting" class="sc__input sc__input--half" type="number" v-model="targetStartWeek" placeholder="起" @input="invalidateConflict" />
              <text class="sc__sep">~</text>
              <input :disabled="submitting" class="sc__input sc__input--half" type="number" v-model="targetEndWeek" placeholder="止" @input="invalidateConflict" />
            </view>
            <view class="sc__row">
              <text class="sc__row-k">单双周</text>
              <picker :disabled="submitting" class="sc__picker" mode="selector" :range="parityLabels" :value="parityIndex" @change="onParity">
                <view class="sc__pick-val">{{ parityLabels[parityIndex] }}<text class="sc__arrow">▾</text></view>
              </picker>
            </view>
            <view class="sc__row"><text class="sc__row-k">目标教室</text><input :disabled="submitting" class="sc__input" v-model="targetClassroom" placeholder="可选" @input="invalidateConflict" /></view>
          </template>
          <view class="sc__row" v-if="typeKey === 'MAKEUP'"><text class="sc__row-k">补课说明</text><input :disabled="submitting" class="sc__input" v-model="makeupPlan" placeholder="可选" /></view>
          <view class="sc__row" v-if="typeKey === 'STOP'"><text class="sc__row-k">后续安排</text><input :disabled="submitting" class="sc__input" v-model="makeupPlan" placeholder="停课须填写后续安排" /></view>
          <view class="sc__row" style="border-bottom:none;"><text class="sc__row-k">事由</text><input :disabled="submitting" class="sc__input" v-model="reason" placeholder="至少 5 字" /></view>
        </view>

        <view class="sc__conflict card" v-if="conflictChecked">
          <text v-if="conflictResult" class="sc__conflict-bad">⚠ 目标课位存在冲突（{{ conflictTypeLabel(conflictResult.type) }}）：{{ conflictResult.detail }}</text>
          <text v-else class="sc__conflict-ok">✓ 目标课位无冲突</text>
        </view>

        <MobileSafeAreaBar>
          <button class="btn btn-ghost flex-1" :disabled="checking || typeKey === 'STOP' || !currentItemId" @click="doConflictCheck">{{ checking ? '预检中…' : '冲突预检' }}</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || !canSubmit || hasUnknownWrite('submit', currentItemId)" @click="doSubmit">{{ submitting ? '提交中…' : hasUnknownWrite('submit', currentItemId) ? '等待核对结果' : typeKey !== 'STOP' && !conflictReady ? '请先完成预检' : '提交申请' }}</button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { normalizeError } from '@/services/request'
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'
import { useSessionStore } from '@/stores/session'
import { beginPersistentWrite, clearPersistentWrite, isExplicitWriteRejection, isForbiddenResponse, listPersistentWrites, persistWriteAck, teacherWriteContext } from '../academic-affairs/write-result'

const TYPES = [{ key: 'ADJUST', label: '调课' }, { key: 'STOP', label: '停课' }, { key: 'MAKEUP', label: '补课' }]
const PARITIES = [{ key: 'ALL', label: '每周' }, { key: 'ODD', label: '单周' }, { key: 'EVEN', label: '双周' }]
const STATUS_LABELS = {
  SUBMITTED: '待学院审', COLLEGE_REVIEW: '学院审批中', ACADEMIC_REVIEW: '教务处审批中',
  APPROVED: '已通过', APPLIED: '已生效', REJECTED: '已驳回', CANCELLED: '已撤销'
}
const STATUS_TONES = {
  SUBMITTED: 'warning', COLLEGE_REVIEW: 'warning', ACADEMIC_REVIEW: 'processing',
  APPROVED: 'success', APPLIED: 'success', REJECTED: 'danger', CANCELLED: 'default'
}
const CANCELLABLE = new Set(['SUBMITTED', 'COLLEGE_REVIEW'])

export default {
  data() {
    return {
      tab: 'list', state: 'loading', changes: [], acting: false, changePage: 0,
      items: [], itemIndex: 0, typeIndex: 0, parityIndex: 0,
      targetWeekday: '', targetSlotNo: '', targetStartWeek: '', targetEndWeek: '', targetClassroom: '',
      makeupPlan: '', reason: '', checking: false, submitting: false,
      conflictChecked: false, conflictResult: null, checkedFingerprint: '', receipt: null,
      requestedItemId: '', scheduleState: 'idle', scheduleError: '', unknownWrites: {}, writeStorageBlocked: false
    }
  },
  onLoad(options = {}) {
    this._pageActive = true
    this._viewContext = this.contextKey()
    this.syncUnknownWrites()
    this.requestedItemId = String(options.scheduleItemId || '')
    this.load()
    if (this.requestedItemId) { this.tab = 'new'; this.itemIndex = -1; this.loadSchedule() }
  },
  onShow() {
    this._pageActive = true
    this.syncUnknownWrites()
    const context = this.contextKey()
    if (this._viewContext !== context) {
      this._viewContext = context
      this._writeEpoch = (this._writeEpoch || 0) + 1
      this.acting = false
      this.submitting = false
      this.checking = false
      this.changePage = 0
      this.changes = []
      this.targetWeekday = ''; this.targetSlotNo = ''; this.targetStartWeek = ''; this.targetEndWeek = ''; this.targetClassroom = ''
      this.requestedItemId = ''
      this.tab = 'list'
      this.items = []
      this.itemIndex = 0
      this.reason = ''
      this.makeupPlan = ''
      this.receipt = null
      this.syncUnknownWrites()
      this.invalidateConflict()
      this._needsRefresh = false
      this.load()
      return
    }
    if (!this._needsRefresh) return
    this._needsRefresh = false
    this.load()
    if (this.tab === 'new') this.loadSchedule()
  },
  onHide() {
    this._pageActive = false
    this._needsRefresh = true
    this._listEpoch = (this._listEpoch || 0) + 1
    this._scheduleEpoch = (this._scheduleEpoch || 0) + 1
    this._conflictEpoch = (this._conflictEpoch || 0) + 1
  },
  onUnload() {
    this._pageActive = false
    this._listEpoch = (this._listEpoch || 0) + 1
    this._scheduleEpoch = (this._scheduleEpoch || 0) + 1
    this._conflictEpoch = (this._conflictEpoch || 0) + 1
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    changePageIndex() { return Math.min(this.changePage, Math.max(0, Math.ceil(this.changes.length / 20) - 1)) },
    visibleChanges() { return this.changes.slice(this.changePageIndex * 20, (this.changePageIndex + 1) * 20) },
    itemLabels() { return this.items.map((i) => `周${i.weekday}第${i.slotNo}节 · ${i.courseName}（${i.className}）`) },
    typeLabels() { return TYPES.map((t) => t.label) },
    typeKey() { return TYPES[this.typeIndex].key },
    parityLabels() { return PARITIES.map((p) => p.label) },
    currentItemId() { const i = this.items[this.itemIndex]; return i ? i.itemId : null },
    bodyFingerprint() { return JSON.stringify(this._body()) },
    conflictReady() { return this.typeKey === 'STOP' || (this.conflictChecked && !this.conflictResult && this.checkedFingerprint === this.bodyFingerprint) },
    canSubmit() { return !!this.currentItemId && this.conflictReady }
  },
  onBackPress() { if (this.tab !== 'new') return false; this.backToApplications(); return true },
  methods: {
    backToApplications() { if (this.submitting || this.acting) { toast('正在处理，请稍候'); return false }; if (this.tab !== 'new') return true; this.tab = 'list'; return false },
    contextKey() {
      return teacherWriteContext(useSessionStore())
    },
    statusLabel(s) { return STATUS_LABELS[s] || (s ? `状态待确认（${s}）` : '状态待确认') },
    conflictTypeLabel(value) {
      return ({ TEACHER: '教师时间冲突', CLASS: '班级时间冲突', CLASSROOM: '教室占用冲突' })[value] || (value ? `其他冲突（${value}）` : '冲突类型待确认')
    },
    writeKey(action, objectId) { return `${action}|${String(objectId || '')}` },
    hasUnknownWrite(action, objectId) { return this.writeStorageBlocked || !!this.unknownWrites[this.writeKey(action, objectId)] },
    syncUnknownWrites(context = this.contextKey()) {
      const result = listPersistentWrites(context)
      this.writeStorageBlocked = !result.ok
      this.unknownWrites = result.ok ? Object.fromEntries(result.records.map((row) => [this.writeKey(row.action, row.objectId), row])) : {}
      return result
    },
    beginWrite(context, action, objectId) { const result = beginPersistentWrite(context, action, objectId); this.syncUnknownWrites(); if (!result.ok) toast(result.storageError ? '无法安全保存待核对记录，本次未提交' : '该操作正在等待正式记录核对'); return result.ok },
    ackWrite(context, action, objectId, ack) { const ok = persistWriteAck(context, action, objectId, ack); this.syncUnknownWrites(); return ok },
    clearWrite(context, action, objectId) { const ok = clearPersistentWrite(context, action, objectId); this.syncUnknownWrites(); return ok },
    reconcileWrites(rows) {
      const pending = listPersistentWrites(this.contextKey())
      if (!pending.ok) { this.syncUnknownWrites(); return }
      pending.records.forEach((record) => {
        if (record.state !== 'ACK') return
        if (record.action === 'submit' && record.ackId && rows.some((row) => String(row.changeId || '') === record.ackId)) this.clearWrite(record.context, record.action, record.objectId)
        if (record.action === 'cancel' && rows.some((row) => String(row.changeId || '') === record.objectId && String(row.status || '') === 'CANCELLED')) this.clearWrite(record.context, record.action, record.objectId)
      })
    },
    statusTone(s) { return STATUS_TONES[s] || 'default' },
    cancellable(s) { return CANCELLABLE.has(s) },
    switchTab(t) {
      if (this.submitting || this.acting) { toast('正在处理，请稍候'); return }
      this.tab = t
      if (t === 'new' && !this.items.length) this.loadSchedule()
    },
    async load(done) {
      const epoch = (this._listEpoch || 0) + 1
      this._listEpoch = epoch
      const context = this.contextKey()
      this.state = 'loading'
      try {
        const d = await teacherApi.getAcademicScheduleChanges()
        if (!this._pageActive || this._listEpoch !== epoch || this.contextKey() !== context) return
        this.changes = (d && d.list) || []
        this.reconcileWrites(this.changes)
        this.state = 'ready'
      } catch (error) {
        if (this._pageActive && this._listEpoch === epoch && this.contextKey() === context) {
          if (isForbiddenResponse(error)) { this.changes = []; this.items = []; this.receipt = null; this.tab = 'list' }
          this.state = normalizeError(error).pageState || 'error'
        }
      } finally { if (done) done() }
    },
    async loadSchedule() {
      const epoch = (this._scheduleEpoch || 0) + 1
      this._scheduleEpoch = epoch
      const context = this.contextKey()
      this.scheduleState = 'loading'
      this.scheduleError = ''
      try {
        const d = await teacherApi.getAcademicMySchedule()
        if (!this._pageActive || this._scheduleEpoch !== epoch || this.contextKey() !== context) return
        this.items = (d && d.items) || []
        if (this.requestedItemId) {
          this.itemIndex = this.items.findIndex((item) => String(item.itemId || item.scheduleItemId || '') === this.requestedItemId)
          if (this.itemIndex < 0) this.scheduleError = '该正式课位已失效或不在本人授课范围，请重新选择。'
          this.requestedItemId = ''
          this.invalidateConflict()
        }
        this.scheduleState = 'ready'
      } catch (error) {
        if (this._pageActive && this._scheduleEpoch === epoch && this.contextKey() === context) { this.items = []; this.scheduleState = 'error' }
      }
    },
    invalidateConflict() { this.conflictChecked = false; this.conflictResult = null; this.checkedFingerprint = '' },
    onItem(e) { this.itemIndex = Number(e.detail.value); this.invalidateConflict() },
    onType(e) { this.typeIndex = Number(e.detail.value); this.invalidateConflict() },
    onParity(e) { this.parityIndex = Number(e.detail.value); this.invalidateConflict() },
    _body() {
      return {
        originItemId: this.currentItemId, changeType: this.typeKey, reason: this.reason.trim(),
        targetWeekday: this.targetWeekday ? Number(this.targetWeekday) : null,
        targetSlotNo: this.targetSlotNo ? Number(this.targetSlotNo) : null,
        targetStartWeek: this.targetStartWeek ? Number(this.targetStartWeek) : null,
        targetEndWeek: this.targetEndWeek ? Number(this.targetEndWeek) : null,
        targetWeekParity: PARITIES[this.parityIndex].key,
        targetClassroom: this.targetClassroom.trim() || null,
        makeupPlan: this.makeupPlan.trim() || null
      }
    },
    doConflictCheck() {
      if (this.checking || !this.currentItemId) return
      if (!this.targetWeekday || !this.targetSlotNo) { toast('请先填写目标星期与节次'); return }
      const body = this._body()
      const fingerprint = JSON.stringify(body)
      const context = this.contextKey()
      const epoch = (this._conflictEpoch || 0) + 1
      this._conflictEpoch = epoch
      this.checking = true
      teacherApi.academicScheduleConflictCheck(this._body())
        .then((d) => {
          if (!this._pageActive || this._conflictEpoch !== epoch || this.contextKey() !== context || this.bodyFingerprint !== fingerprint) return
          this.conflictChecked = true
          this.conflictResult = d ? d.conflict : null
          this.checkedFingerprint = fingerprint
        })
        .catch((e) => {
          if (this._pageActive && this._conflictEpoch === epoch && this.contextKey() === context) toast((e && e.message) || '预检失败，请重试')
        })
        .finally(() => { if (this._conflictEpoch === epoch && this.contextKey() === context) this.checking = false })
    },
    async doSubmit() {
      if (this.submitting || !this.canSubmit) return
      const reason = this.reason.trim()
      if (reason.length < 5) { toast('事由至少 5 个字'); return }
      if (this.typeKey === 'STOP' && !this.makeupPlan.trim()) { toast('停课须填写后续安排说明'); return }
      if (this.typeKey !== 'STOP' && (!this.targetWeekday || !this.targetSlotNo)) { toast('请填写目标星期与节次'); return }
      const item = this.items[this.itemIndex] || {}
      const body = this._body()
      const originItemId = String(body.originItemId || '')
      if (this.hasUnknownWrite('submit', originItemId)) { toast('上次提交结果未确认，请先刷新申请列表核对'); return }
      const context = this.contextKey()
      const confirmed = await new Promise((resolve) => uni.showModal({
        title: '提交调停课申请',
        content: `${item.courseName || '本课程'} · ${this.typeLabels[this.typeIndex]}。服务器会再次核对正式课位与冲突，确认提交？`,
        confirmText: '确认提交',
        success: (result) => resolve(!!result.confirm), fail: () => resolve(false)
      }))
      if (!confirmed || !this._pageActive || this.submitting || !this.canSubmit || this.contextKey() !== context || String(this.currentItemId || '') !== originItemId || JSON.stringify(body) !== this.bodyFingerprint) return
      if (!this.beginWrite(context, 'submit', originItemId)) return
      this.submitting = true
      const writeEpoch = (this._writeEpoch || 0) + 1
      this._writeEpoch = writeEpoch
      teacherApi.submitAcademicScheduleChange(this._body())
        .then((d) => {
          const changeId = String(d && d.changeId || '')
          this.ackWrite(context, 'submit', originItemId, { ackId: changeId, parentId: originItemId })
          if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context || String(this.currentItemId || '') !== originItemId) return
          if (!changeId) { toast('提交响应缺少单据编号，已停止重复提交；请只读核对申请列表'); this.load(); return }
          this.receipt = {
            title: '调停课申请已提交', changeId,
            courseName: d.courseName || item.courseName || '课程', result: '待学院审核',
            next: '学院教务审核；终审生效后课表与考勤同步更新'
          }
          toast('已提交')
          this.reason = ''; this.makeupPlan = ''; this.targetWeekday = ''; this.targetSlotNo = ''
          this.targetStartWeek = ''; this.targetEndWeek = ''; this.targetClassroom = ''
          this.invalidateConflict()
          this.tab = 'list'; this.load()
        })
        .catch((e) => {
          if (isExplicitWriteRejection(e)) this.clearWrite(context, 'submit', originItemId)
          if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
          const code = e && String(e.code)
          if (code === 'DATA_CONFLICT') toast((e && e.message) || '目标课位冲突，单据不予受理')
          else if (isExplicitWriteRejection(e)) toast((e && e.message) || '提交未受理，请修改后重试')
          else { toast('提交结果未确认，已停止重复提交；请刷新申请列表核对'); this.load() }
        })
        .finally(() => { if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.submitting = false })
    },
    doCancel(x) {
      if (this.acting || this.submitting || !this.changes.includes(x) || !this.cancellable(x.status) || this.hasUnknownWrite('cancel', x.changeId)) return
      const changeId = String(x.changeId || '')
      const context = this.contextKey()
      const epoch = this._listEpoch
      const snapshot = JSON.stringify(x)
      uni.showModal({
        title: '撤销调停课申请', editable: true, placeholderText: '可填写撤销原因（可选）', content: '',
        success: (r) => {
          if (!r.confirm || !this._pageActive || this.acting || this.submitting || !this.changes.includes(x) || this._listEpoch !== epoch || this.contextKey() !== context || JSON.stringify(x) !== snapshot || String(x.changeId || '') !== changeId) return
          if (!this.beginWrite(context, 'cancel', changeId)) return
          const writeEpoch = (this._writeEpoch || 0) + 1
          this._writeEpoch = writeEpoch
          this.acting = true
          teacherApi.cancelAcademicScheduleChange(changeId, r.content || '')
            .then(() => {
              this.ackWrite(context, 'cancel', changeId, { parentId: changeId })
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              this.receipt = { title: '调停课申请已撤销', changeId, courseName: x.courseName || '课程', result: '已撤销并保留记录', next: '如仍需调整，请从正式课表重新发起' }
              toast('已撤销'); this.load()
            })
            .catch((e) => {
              if (isExplicitWriteRejection(e)) this.clearWrite(context, 'cancel', changeId)
              if (!this._pageActive || this._writeEpoch !== writeEpoch || this.contextKey() !== context) return
              if (isExplicitWriteRejection(e)) toast((e && e.message) || '撤销未受理，请刷新后重试')
              else { toast('撤销结果未确认，已停止重复提交；请刷新申请列表核对'); this.load() }
            })
            .finally(() => { if (this._writeEpoch === writeEpoch && this.contextKey() === context) this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.sc__pages { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 16px 0; }
.btn.btn-primary { background: var(--teacher-600); border-color: var(--teacher-600); color: #fff; }
.btn.btn-ghost { color: var(--teacher-700); border-color: var(--teacher-200); }
.btn[disabled] { opacity: .5; }
.sc__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.sc__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.sc__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.sc__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.sc__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.sc { display: flex; flex-direction: column; gap: var(--space-2); }
.sc__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.sc__row { display: flex; align-items: center; gap: var(--space-3); min-height: 44px; border-bottom: 1px solid var(--border-light); }
.sc__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 64px; flex-shrink: 0; }
.sc__picker { flex: 1; }
.sc__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.sc__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.sc__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.sc__input--half { flex: none; width: 64px; }
.sc__sep { color: var(--text-tertiary); font-size: var(--font-size-sm); }
.sc__form { display: flex; flex-direction: column; }
.sc__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.sc__conflict { margin-top: var(--space-3); }
.sc__conflict-bad { font-size: var(--font-size-sm); color: var(--danger-600); }
.sc__conflict-ok { font-size: var(--font-size-sm); color: var(--success-600); }
.sc__receipt { margin-bottom: var(--space-3); border-color: #a7d7b4; background: #f3fbf5; }
.sc__receipt-title, .sc__receipt-sub { display: block; }.sc__receipt-title { color: var(--success-700, #15803d); font-size: var(--font-size-base); font-weight: var(--font-weight-semibold); }.sc__receipt-sub { margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
</style>
