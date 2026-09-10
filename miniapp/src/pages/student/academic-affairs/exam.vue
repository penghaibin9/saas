<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="我的考试 / 缓考" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view v-if="applicationNotice" class="ed__notice"><text>{{ applicationNotice }}</text><button v-if="pendingApplication" class="btn" @click="load">核对本人记录</button></view>
        <view v-if="partialErrors.length" class="ed__partial"><text>{{ partialErrors.join('、') }}暂时无法更新，其它内容仍可查看。</text><text @click="load(true)">重试</text></view>
        <view class="section-head">
          <text class="section-head__title">我的考试安排</text>
          <text
            v-if="d.schedule && d.schedule.length"
            class="section-head__more"
            @click="printTicket"
          >复制准考证摘要</text>
        </view>
        <AcademicPageState v-if="!partialErrors.includes('考试安排') && !(d.schedule && d.schedule.length)" state="empty" title="暂无已发布考试安排"
          description="教务发布考场座位后，准考证与考场信息会出现在此。" />
        <view class="list-group" v-else>
          <view v-for="it in d.schedule" :key="it.examCourseId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ it.courseName }}</text>
              <text class="ed__sub">{{ it.examDate || '未排定' }} {{ it.startTime || '' }}{{ it.endTime ? ' - ' + it.endTime : '' }}</text>
              <text class="ed__sub">考场 {{ it.classroom || '—' }} · 座位 {{ it.seatNo ?? '—' }} · 准考证 {{ it.admissionNo || '—' }}</text>
            </view>
          </view>
        </view>

        <view class="section-head">
          <text class="section-head__title">可申请缓考的考试</text>
        </view>
        <AcademicPageState v-if="!partialErrors.includes('可申请考试') && !d.options.length" state="empty" title="暂无可申请的考试"
          description="已排考且未开考的课程会在此显示，发布后即可申请缓考。" />
        <view class="list-group" v-else>
          <view v-for="c in d.options" :key="c.examCourseId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ c.courseName }}</text>
              <text class="ed__sub">{{ c.examDate || '未排定日期' }} {{ c.startTime || '' }}</text>
            </view>
            <button v-if="c.hasActiveDefer" class="btn-tag is-disabled" disabled>申请中</button>
            <button v-else-if="c.canApply === true" class="btn-tag" @click="openForm(c)">申请缓考</button>
            <button v-else class="btn-tag is-disabled" disabled>暂不可申请</button>
          </view>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="ed__form-title">申请缓考：{{ selectedCourse && selectedCourse.courseName }}</text>
          <picker mode="selector" :range="reasonOptions" range-key="label" @change="onReasonPick">
            <view class="ed__input ed__picker">{{ reasonLabel(form.reasonType) }}</view>
          </picker>
          <textarea class="ed__textarea" :disabled="submitting || !!pendingApplication" v-model="form.reason" :maxlength="500" placeholder="缓考原因说明（选填，材料要求请向学校核对）" placeholder-class="ed__ph" />
          <view class="ed__form-actions">
            <button class="btn btn-ghost" @click="showForm = false">取消</button>
            <button class="btn btn-primary" :disabled="submitting || !!pendingApplication" @click="submit">
              {{ submitting ? '提交中…' : '提交申请' }}
            </button>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">我的缓考申请</text></view>
        <AcademicPageState v-if="!partialErrors.includes('缓考记录') && !d.deferrals.length" state="empty" title="暂无缓考申请" description="选择上方可申请的考试发起缓考。" />
        <view class="list-group" v-else>
          <view v-for="r in d.deferrals" :key="r.deferId" class="list-row" :class="{ 'is-target': String(r.deferId) === targetId }">
            <view class="flex-1">
              <text class="t-md">{{ r.courseName }}</text>
              <text class="ed__sub">{{ reasonLabel(r.reasonType) }} · {{ (r.applyAt || '').replace('T', ' ').slice(0, 16) }}</text>
              <text v-if="r.returnReason" class="ed__reason">{{ r.status === 'REJECTED' ? '驳回原因' : '退回原因' }}：{{ r.returnReason }}</text>
            </view>
            <view class="flex-col-end">
              <MobileStatusTag :status="r.status" />
              <button v-if="r.status === 'RETURNED'" class="btn-tag" @click="resubmit(r)">补材料重提</button>
            </view>
          </view>
        </view>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>

<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { academicStudentApi as studentApi } from '@/services/academicStudentApi'
import { academicApplicationPage } from './application-page'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { toast } from '@/utils/nav'
import { savePending } from './pending-ledger'
const isForbidden = error => Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
const REASON_OPTIONS = [{ label: '疾病', value: 'ILLNESS' }, { label: '公务或学校安排', value: 'OFFICIAL' }, { label: '家庭重大事项', value: 'FAMILY' }, { label: '其他', value: 'OTHER' }]
const REASON_LABELS = { ILLNESS: '疾病', SICK: '疾病', MEDICAL: '疾病', OFFICIAL: '公务或学校安排', EMERGENCY: '突发事件', FAMILY: '家庭重大事项', OTHER: '其他' }
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicApplicationPage],
  created() { this.applicationScope = 'exam' },
  data() { return { d: null, state: 'loading', showForm: false, selectedCourse: null, form: { reasonType: 'ILLNESS', reason: '' }, reasonOptions: REASON_OPTIONS, targetId: '', partialErrors: [], printing: false, academicDraftFields: ['selectedCourse', 'form', 'showForm'] } },
  onLoad(options = {}) { this.targetId = String(options.id || ''); this.load() },
  methods: {
    resetAcademicContext() { this.clearApplicationContext(); this.targetId = ''; this.partialErrors = []; this.printing = false; this.finishApplication() },
    clearForbiddenExam() {
      const hadPending = this.protectPendingReference()
      this.d = null; this.targetId = ''; this.partialErrors = []; this.printing = false; this.finishApplication(); this.submitting = false
      this.applicationNotice = hadPending ? '当前无权核对考试与缓考记录；本次办理仍待核实。' : ''
      savePending('draft:' + this.applicationScope, null)
    },
    finishApplication() { this.showForm = false; this.selectedCourse = null; this.form = { reasonType: 'ILLNESS', reason: '' } },
    load() {
      return this.readAcademic(async () => {
        const identity = currentSessionGeneration(); const epoch = this.readEpoch
        const results = await Promise.allSettled([studentApi.getMyExamSchedule(), studentApi.getMyDeferOptions(), studentApi.getMyDeferrals()])
        const denied = results.find(result => result.status === 'rejected' && isForbidden(result.reason))
        if (denied) { if (epoch === this.readEpoch && identity === currentSessionGeneration() && !this.readHidden) this.clearForbiddenExam(); throw denied.reason }
        return results
      }, results => {
        const previous = this.d || { schedule: [], options: [], deferrals: [] }
        const valid = i => results[i].status === 'fulfilled' && Array.isArray(results[i].value?.items)
        const names = ['考试安排', '可申请考试', '缓考记录']
        this.partialErrors = names.filter((_, i) => !valid(i))
        if (this.partialErrors.length === 3) throw results.find(result => result.status === 'rejected')?.reason || new Error('考试信息无法核对')
        this.d = { schedule: valid(0) ? results[0].value.items : previous.schedule, options: valid(1) ? results[1].value.items : previous.options, deferrals: valid(2) ? results[2].value.items : previous.deferrals }
        if (this.selectedCourse) this.selectedCourse = this.d.options.find(row => String(row.examCourseId) === String(this.selectedCourse.examCourseId)) || { ...this.selectedCourse, canApply: false }
        if (valid(2)) this.acceptApplication(this.d.deferrals, 'deferId', (row, body, kind) => kind === 'resubmit'
          ? String(this.pendingApplication?.returnedId || '') === String(body.deferId) && !['RETURNED', 'REJECTED', 'CANCELLED'].includes(row.status) && !!row.status
          : !!this.pendingApplication?.returnedId && String(row.examCourseId) === String(body.examCourseId) && row.reasonType === body.reasonType && (row.reason || '') === body.reason)
      })
    },
    reasonLabel(v) { return REASON_LABELS[String(v || '').toUpperCase()] || '未说明' },
    onReasonPick(e) { if (!this.submitting && !this.pendingApplication) this.form.reasonType = this.reasonOptions[Number(e.detail.value)]?.value || 'OTHER' },
    openForm(c) {
      if (!c || c.hasActiveDefer || c.canApply !== true) return
      if (this.submitting || this.pendingApplication || this.partialErrors.includes('可申请考试')) return
      if (String(this.selectedCourse?.examCourseId) !== String(c.examCourseId)) this.form = { reasonType: 'ILLNESS', reason: '' }
      this.selectedCourse = c; this.showForm = true
    },
    submit() {
      if (!this.selectedCourse || this.selectedCourse.canApply !== true || this.submitting) return
      if (this.partialErrors.includes('可申请考试') || this.partialErrors.includes('缓考记录')) return
      const body = { examCourseId: this.selectedCourse.examCourseId, reasonType: this.form.reasonType, reason: this.form.reason.trim() }
      return this.sendApplication({ title: '确认申请缓考：' + this.selectedCourse.courseName, body,
        send: frozen => studentApi.applyDefer(frozen.examCourseId, frozen.reasonType, frozen.reason), rows: this.d.deferrals, idKey: 'deferId' })
    },
    resubmit(r) {
      if (r.status !== 'RETURNED' || this.partialErrors.includes('缓考记录')) return
      return this.sendApplication({ title: '确认已处理退回要求并重提', kind: 'resubmit', body: { deferId: r.deferId }, existingId: r.deferId,
        recovery: { field: 'status', excludes: ['RETURNED', 'REJECTED', 'CANCELLED'] }, send: body => studentApi.resubmitDefer(body.deferId), rows: this.d.deferrals, idKey: 'deferId' })
    },
    async printTicket() {
      if (!(this.d && this.d.schedule && this.d.schedule.length)) return
      if (this.printing || this.partialErrors.includes('考试安排')) return
      const identity = currentSessionGeneration(); const epoch = this.readEpoch
      const current = () => identity === currentSessionGeneration() && epoch === this.readEpoch && !this.readHidden
      this.printing = true
      try {
        const res = await studentApi.printExamTicket('个人准考证')
        if (!current()) return
        if (!res?.loggedAt) throw new Error('用途登记结果待核实')
        const rows = res.document?.schedule || res.document?.items || this.d.schedule
        const text = rows.map(it => [it.courseName, it.examDate, it.classroom, '座位 ' + (it.seatNo ?? '—')].filter(Boolean).join(' · ')).join('\n')
        uni.setClipboardData({ data: text, success: () => { if (current()) toast('已复制准考证摘要') }, fail: () => { if (current()) toast('复制未完成，请重试') } })
      } catch (_) { if (current()) toast('准考证摘要暂未完成，请稍后核对') }
      finally { if (identity === currentSessionGeneration()) this.printing = false }
    }
  }
}
</script>

<style scoped>
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.ed__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ed__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
.is-target { border: 1px solid var(--brand-primary); box-shadow: 0 0 0 2px var(--brand-50); }
.ed__input { width: 100%; min-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; display: flex; align-items: center; }
.ed__picker { color: var(--text-primary); }
.ed__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.ed__ph { color: var(--text-tertiary); }
.ed__form-title { display: block; font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.ed__form-actions { display: flex; gap: var(--space-2); justify-content: flex-end; }
.flex-col-end { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.btn-tag { font-size: var(--font-size-xs); color: var(--primary-600); background: var(--primary-50); border: none; border-radius: var(--radius-full); padding: 4px 12px; }
.btn-tag.is-disabled { color: var(--text-tertiary); background: var(--fill-light, #f1f5f9); }
.ed__notice, .ed__partial { display: flex; justify-content: space-between; gap: 8px; padding: 10px 12px; border-radius: var(--radius-md); font-size: 12px; }
.ed__notice { flex-direction: column; background: var(--success-50); color: var(--success-700); }
.ed__notice.is-warning, .ed__partial { background: var(--warning-50); color: var(--warning-700); }
.ed__notice text:first-child { font-size: 14px; font-weight: 700; }
</style>
