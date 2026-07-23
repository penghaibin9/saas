<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的考试 / 缓考" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head">
          <text class="section-head__title">我的考试安排</text>
          <text class="section-head__more" @click="printTicket">打印准考证</text>
        </view>
        <MobileGlobalState v-if="!(d.schedule && d.schedule.length)" state="empty" title="暂无已发布考试安排"
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
        <MobileGlobalState v-if="!d.options.length" state="empty" title="暂无可申请的考试"
          description="已排考且未开考的课程会在此显示，发布后即可申请缓考。" />
        <view class="list-group" v-else>
          <view v-for="c in d.options" :key="c.examCourseId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ c.courseName }}</text>
              <text class="ed__sub">{{ c.examDate || '未排定日期' }} {{ c.startTime || '' }}</text>
            </view>
            <button v-if="c.hasActiveDefer" class="btn-tag is-disabled" disabled>申请中</button>
            <button v-else class="btn-tag" @click="openForm(c)">申请缓考</button>
          </view>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <text class="ed__form-title">申请缓考：{{ selectedCourse && selectedCourse.courseName }}</text>
          <picker mode="selector" :range="reasonOptions" range-key="label" @change="onReasonPick">
            <view class="ed__input ed__picker">{{ reasonLabel(form.reasonType) }}</view>
          </picker>
          <textarea class="ed__textarea" v-model="form.reason" :maxlength="500" placeholder="缓考原因说明（选填，如病假需附材料请线下提交辅导员）" placeholder-class="ed__ph" />
          <view class="ed__form-actions">
            <button class="btn btn-ghost" @click="showForm = false">取消</button>
            <button class="btn btn-primary" :disabled="submitting" @click="submit">
              {{ submitting ? '提交中…' : '提交申请' }}
            </button>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">我的缓考申请</text></view>
        <MobileGlobalState v-if="!d.deferrals.length" state="empty" title="暂无缓考申请" description="选择上方可申请的考试发起缓考。" />
        <view class="list-group" v-else>
          <view v-for="r in d.deferrals" :key="r.deferId" class="list-row">
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
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const REASON_OPTIONS = [
  { label: '病假', value: 'SICK' },
  { label: '突发事件', value: 'EMERGENCY' },
  { label: '其他', value: 'OTHER' }
]
const REASON_MAP = REASON_OPTIONS.reduce((m, o) => ({ ...m, [o.value]: o.label }), {})

export default {
  data() {
    return {
      d: null, state: 'loading', showForm: false, submitting: false,
      selectedCourse: null, form: { reasonType: 'SICK', reason: '' },
      reasonOptions: REASON_OPTIONS
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      Promise.all([
        studentApi.getMyExamSchedule(),
        studentApi.getMyDeferOptions(),
        studentApi.getMyDeferrals()
      ]).then(([sched, opts, defers]) => {
        this.d = {
          schedule: (sched && sched.items) || [],
          options: (opts && opts.items) || [],
          deferrals: (defers && defers.items) || []
        }
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    reasonLabel(v) { return REASON_MAP[v] || v || '未说明' },
    printTicket() {
      studentApi.printExamTicket('个人准考证').then((res) => {
        const doc = (res && res.document) || {}
        const rows = doc.schedule || doc.items || this.d.schedule || []
        const lines = rows.map((it) =>
          `${it.courseName || '—'} ${it.examDate || ''} ${it.classroom || '—'} 座${it.seatNo ?? '—'} 准考证${it.admissionNo || '—'}`
        ).join('\n')
        const text = [
          '准考证摘要',
          `姓名：${doc.realName || '—'}`,
          `学号：${doc.studentNo || '—'}`,
          `留痕：${(res && res.loggedAt) || ''}`,
          '',
          lines || '暂无考试安排'
        ].join('\n')
        uni.setClipboardData({
          data: text,
          success: () => uni.showToast({ title: '已留痕并复制准考证摘要', icon: 'success' }),
          fail: () => uni.showToast({ title: '已留痕，可截屏保存', icon: 'success' })
        })
      }).catch((e) => toast((e && e.message) || '打印留痕失败'))
    },
    onReasonPick(e) { this.form.reasonType = this.reasonOptions[e.detail.value].value },
    openForm(c) {
      this.selectedCourse = c
      this.form = { reasonType: 'SICK', reason: '' }
      this.showForm = true
    },
    submit() {
      if (!this.selectedCourse || this.submitting) return
      this.submitting = true
      submitLock.run(() => studentApi.applyDefer(this.selectedCourse.examCourseId, this.form.reasonType, this.form.reason.trim()))
        .then(() => {
          uni.showToast({ title: '缓考申请已提交', icon: 'success' })
          this.showForm = false
          this.load()
        }).catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试')
        }).finally(() => { this.submitting = false })
    },
    resubmit(r) {
      studentApi.resubmitDefer(r.deferId).then(() => {
        uni.showToast({ title: '已重提', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '重提失败，请稍后重试'))
    }
  }
}
</script>

<style scoped>
.ed__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ed__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
.ed__input { width: 100%; min-height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; display: flex; align-items: center; }
.ed__picker { color: var(--text-primary); }
.ed__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.ed__ph { color: var(--text-tertiary); }
.ed__form-title { display: block; font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.ed__form-actions { display: flex; gap: var(--space-2); justify-content: flex-end; }
.flex-col-end { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; }
.btn-tag { font-size: var(--font-size-xs); color: var(--primary-600); background: var(--primary-50); border: none; border-radius: var(--radius-full); padding: 4px 12px; }
.btn-tag.is-disabled { color: var(--text-tertiary); background: var(--fill-light, #f1f5f9); }
</style>
