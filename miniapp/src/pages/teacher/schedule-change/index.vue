<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="调停课管理" subtitle="调课 · 停课 · 补课" show-back />

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
        <MobileGlobalState v-if="!changes.length" state="empty" title="暂无调停课申请"
          description="点击「发起申请」新建调课/停课/补课申请。" />
        <view class="stack" v-else>
          <view v-for="x in changes" :key="x.changeId" class="card sc">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ x.changeTypeLabel }} · {{ x.courseName || '—' }}</text>
                <text class="sc__sub">{{ x.className || '' }}</text>
              </view>
              <MobileStatusTag :label="statusLabel(x.status)" :type="statusTone(x.status)" />
            </view>
            <view class="sc__row"><text class="sc__row-k">原课位</text><text class="flex-1 t-sm">周{{ x.origin.weekday }}第{{ x.origin.slotNo }}节 {{ x.origin.classroom || '' }}</text></view>
            <view class="sc__row" v-if="x.changeType !== 'STOP'"><text class="sc__row-k">目标</text><text class="flex-1 t-sm">周{{ x.target.weekday }}第{{ x.target.slotNo }}节 {{ x.target.classroom || '' }}</text></view>
            <view class="sc__row"><text class="sc__row-k">事由</text><text class="flex-1 t-sm">{{ x.reason }}</text></view>
            <view class="sc__actions" v-if="cancellable(x.status)">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doCancel(x)">撤销申请</button>
            </view>
          </view>
        </view>
      </view>

      <!-- 发起申请 -->
      <view class="page-pad" v-if="tab === 'new'">
        <view class="card sc__form">
          <view class="sc__row">
            <text class="sc__row-k">原课位</text>
            <picker class="sc__picker" mode="selector" :range="itemLabels" :value="itemIndex" @change="onItem">
              <view class="sc__pick-val">{{ itemLabels[itemIndex] || '请选择' }}<text class="sc__arrow">▾</text></view>
            </picker>
          </view>
          <view class="sc__row">
            <text class="sc__row-k">类型</text>
            <picker class="sc__picker" mode="selector" :range="typeLabels" :value="typeIndex" @change="(e) => typeIndex = Number(e.detail.value)">
              <view class="sc__pick-val">{{ typeLabels[typeIndex] }}<text class="sc__arrow">▾</text></view>
            </picker>
          </view>

          <template v-if="typeKey !== 'STOP'">
            <view class="sc__row"><text class="sc__row-k">目标星期</text><input class="sc__input" type="number" v-model="targetWeekday" placeholder="1-7" /></view>
            <view class="sc__row"><text class="sc__row-k">目标节次</text><input class="sc__input" type="number" v-model="targetSlotNo" placeholder="如 1" /></view>
            <view class="sc__row"><text class="sc__row-k">起止周</text>
              <input class="sc__input sc__input--half" type="number" v-model="targetStartWeek" placeholder="起" />
              <text class="sc__sep">~</text>
              <input class="sc__input sc__input--half" type="number" v-model="targetEndWeek" placeholder="止" />
            </view>
            <view class="sc__row">
              <text class="sc__row-k">单双周</text>
              <picker class="sc__picker" mode="selector" :range="parityLabels" :value="parityIndex" @change="(e) => parityIndex = Number(e.detail.value)">
                <view class="sc__pick-val">{{ parityLabels[parityIndex] }}<text class="sc__arrow">▾</text></view>
              </picker>
            </view>
            <view class="sc__row"><text class="sc__row-k">目标教室</text><input class="sc__input" v-model="targetClassroom" placeholder="可选" /></view>
          </template>
          <view class="sc__row" v-if="typeKey === 'MAKEUP'"><text class="sc__row-k">补课说明</text><input class="sc__input" v-model="makeupPlan" placeholder="可选" /></view>
          <view class="sc__row" v-if="typeKey === 'STOP'"><text class="sc__row-k">后续安排</text><input class="sc__input" v-model="makeupPlan" placeholder="停课须填写后续安排" /></view>
          <view class="sc__row" style="border-bottom:none;"><text class="sc__row-k">事由</text><input class="sc__input" v-model="reason" placeholder="至少 5 字" /></view>
        </view>

        <view class="sc__conflict card" v-if="conflictChecked">
          <text v-if="conflictResult" class="sc__conflict-bad">⚠ 目标课位存在冲突（{{ conflictResult.type }}）：{{ conflictResult.detail }}</text>
          <text v-else class="sc__conflict-ok">✓ 目标课位无冲突</text>
        </view>

        <MobileSafeAreaBar>
          <button class="btn btn-ghost flex-1" :disabled="checking || typeKey === 'STOP' || !currentItemId" @click="doConflictCheck">{{ checking ? '预检中…' : '冲突预检' }}</button>
          <button class="btn btn-primary flex-1" :disabled="submitting || !currentItemId" @click="doSubmit">{{ submitting ? '提交中…' : '提交申请' }}</button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

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
      tab: 'list', state: 'loading', changes: [], acting: false,
      items: [], itemIndex: 0, typeIndex: 0, parityIndex: 0,
      targetWeekday: '', targetSlotNo: '', targetStartWeek: '', targetEndWeek: '', targetClassroom: '',
      makeupPlan: '', reason: '', checking: false, submitting: false,
      conflictChecked: false, conflictResult: null
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    itemLabels() { return this.items.map((i) => `周${i.weekday}第${i.slotNo}节 · ${i.courseName}（${i.className}）`) },
    typeLabels() { return TYPES.map((t) => t.label) },
    typeKey() { return TYPES[this.typeIndex].key },
    parityLabels() { return PARITIES.map((p) => p.label) },
    currentItemId() { const i = this.items[this.itemIndex]; return i ? i.itemId : null }
  },
  methods: {
    statusLabel(s) { return STATUS_LABELS[s] || s },
    statusTone(s) { return STATUS_TONES[s] || 'default' },
    cancellable(s) { return CANCELLABLE.has(s) },
    switchTab(t) {
      this.tab = t
      if (t === 'new' && !this.items.length) this.loadSchedule()
    },
    load(done) {
      this.state = 'loading'
      teacherApi.getAcademicScheduleChanges().then((d) => {
        this.changes = (d && d.list) || []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    loadSchedule() {
      teacherApi.getAcademicMySchedule().then((d) => {
        this.items = (d && d.items) || []
      }).catch(() => { this.items = [] })
    },
    onItem(e) { this.itemIndex = Number(e.detail.value); this.conflictChecked = false },
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
      this.checking = true
      teacherApi.academicScheduleConflictCheck(this._body())
        .then((d) => { this.conflictChecked = true; this.conflictResult = d ? d.conflict : null })
        .catch((e) => toast((e && e.message) || '预检失败，请重试'))
        .finally(() => { this.checking = false })
    },
    doSubmit() {
      if (this.submitting || !this.currentItemId) return
      const reason = this.reason.trim()
      if (reason.length < 5) { toast('事由至少 5 个字'); return }
      if (this.typeKey === 'STOP' && !this.makeupPlan.trim()) { toast('停课须填写后续安排说明'); return }
      if (this.typeKey !== 'STOP' && (!this.targetWeekday || !this.targetSlotNo)) { toast('请填写目标星期与节次'); return }
      this.submitting = true
      teacherApi.submitAcademicScheduleChange(this._body())
        .then(() => {
          toast('已提交')
          this.reason = ''; this.makeupPlan = ''; this.targetWeekday = ''; this.targetSlotNo = ''
          this.targetStartWeek = ''; this.targetEndWeek = ''; this.targetClassroom = ''
          this.conflictChecked = false
          this.tab = 'list'; this.load()
        })
        .catch((e) => {
          const code = e && String(e.code)
          if (code === 'DATA_CONFLICT') toast((e && e.message) || '目标课位冲突，单据不予受理')
          else toast((e && e.message) || '提交失败，请重试')
        })
        .finally(() => { this.submitting = false })
    },
    doCancel(x) {
      if (this.acting) return
      uni.showModal({
        title: '撤销调停课申请', editable: true, placeholderText: '可填写撤销原因（可选）', content: '',
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.cancelAcademicScheduleChange(x.changeId, r.content || '')
            .then(() => { toast('已撤销'); this.load() })
            .catch((e) => toast((e && e.message) || '撤销失败，请重试'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
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
</style>
