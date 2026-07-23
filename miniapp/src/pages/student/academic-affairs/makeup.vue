<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="补考重修 / 免修" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head">
          <text class="section-head__title">我的重修申请</text>
          <text class="section-head__more" @click="toggleForm('retake')">{{ showRetake ? '收起' : '+ 新增报名' }}</text>
        </view>

        <view class="card stack-sm" v-if="showRetake">
          <text class="mk__hint">请从挂科课程列表选择（禁止纯手输为主入口）</text>
          <picker mode="selector" :range="retakeLabels" :value="retakeIndex" @change="onRetakePick">
            <view class="mk__input">{{ retakeLabels[retakeIndex] || '请选择挂科课程' }}</view>
          </picker>
          <textarea class="mk__textarea" v-model="retakeForm.reason" :maxlength="200" placeholder="申请说明（选填）" placeholder-class="mk__ph" />
          <button class="btn btn-primary" :disabled="!retakeForm.gradeId || submitting" @click="submitRetake">
            {{ submitting ? '提交中…' : '提交重修报名' }}
          </button>
        </view>

        <view class="list-group" v-if="d.retakes.length">
          <view v-for="r in d.retakes" :key="r.applyId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ r.courseName }}</text>
              <text class="mk__sub">{{ r.termCode || '—' }} · 第{{ r.retakeCount }}次重修</text>
              <text v-if="r.reviewReason" class="mk__reason">{{ r.reviewReason }}</text>
            </view>
            <MobileStatusTag :status="r.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无重修申请" description="点击右上角从挂科列表报名。" />

        <view class="section-head">
          <text class="section-head__title">我的免修申请</text>
          <text class="section-head__more" @click="toggleForm('exemption')">{{ showExemption ? '收起' : '+ 申请免修' }}</text>
        </view>

        <view class="card stack-sm" v-if="showExemption">
          <text class="mk__hint">请从未及格课程列表选择</text>
          <picker mode="selector" :range="exLabels" :value="exIndex" @change="onExPick">
            <view class="mk__input">{{ exLabels[exIndex] || '请选择课程' }}</view>
          </picker>
          <textarea class="mk__textarea" v-model="exForm.reason" :maxlength="200" placeholder="免修理由（选填）" placeholder-class="mk__ph" />
          <button class="btn btn-primary" :disabled="!exForm.courseName || submitting" @click="submitExemption">
            {{ submitting ? '提交中…' : '提交免修申请' }}
          </button>
        </view>

        <view class="list-group" v-if="d.exemptions.length">
          <view v-for="e in d.exemptions" :key="e.exemptionId" class="list-row">
            <view class="flex-1">
              <text class="t-md">{{ e.courseName }}</text>
              <text class="mk__sub">{{ e.termCode || '—' }}</text>
              <text v-if="e.returnReason" class="mk__reason">{{ e.returnReason }}</text>
            </view>
            <MobileStatusTag :status="e.status" />
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="暂无免修申请" description="点击右上角从课程列表发起免修。" />
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

export default {
  data() {
    return {
      d: null, opts: { retakeOptions: [], exemptionOptions: [] }, state: 'loading', submitting: false,
      showRetake: false, showExemption: false,
      retakeIndex: 0, exIndex: 0,
      retakeForm: { gradeId: '', courseName: '', termCode: '', reason: '' },
      exForm: { courseName: '', termCode: '', reason: '' }
    }
  },
  computed: {
    retakeLabels() {
      const rows = this.opts.retakeOptions || []
      return rows.length ? rows.map((x) => `${x.courseName}（${x.termCode || '无学期'} · ${x.score ?? '—'}分）`) : ['暂无挂科课程']
    },
    exLabels() {
      const rows = this.opts.exemptionOptions || []
      return rows.length ? rows.map((x) => `${x.courseName}（${x.termCode || '无学期'}）`) : ['暂无可选课程']
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      Promise.all([studentApi.getMyMakeup(), studentApi.getMakeupOptions()])
        .then(([d, opts]) => {
          this.d = d
          this.opts = opts || { retakeOptions: [], exemptionOptions: [] }
          this.syncPickDefaults()
          this.state = 'ready'
        })
        .catch(() => { this.state = 'error' })
    },
    syncPickDefaults() {
      const r = (this.opts.retakeOptions || [])[0]
      if (r) {
        this.retakeForm.gradeId = r.gradeId
        this.retakeForm.courseName = r.courseName
        this.retakeForm.termCode = r.termCode || ''
        this.retakeIndex = 0
      } else {
        this.retakeForm.gradeId = ''
        this.retakeForm.courseName = ''
      }
      const e = (this.opts.exemptionOptions || [])[0]
      if (e) {
        this.exForm.courseName = e.courseName
        this.exForm.termCode = e.termCode || ''
        this.exIndex = 0
      } else {
        this.exForm.courseName = ''
      }
    },
    onRetakePick(e) {
      const i = Number(e.detail.value || 0)
      this.retakeIndex = i
      const row = (this.opts.retakeOptions || [])[i]
      if (!row) return
      this.retakeForm.gradeId = row.gradeId
      this.retakeForm.courseName = row.courseName
      this.retakeForm.termCode = row.termCode || ''
    },
    onExPick(e) {
      const i = Number(e.detail.value || 0)
      this.exIndex = i
      const row = (this.opts.exemptionOptions || [])[i]
      if (!row) return
      this.exForm.courseName = row.courseName
      this.exForm.termCode = row.termCode || ''
    },
    toggleForm(kind) {
      if (kind === 'retake') {
        this.showRetake = !this.showRetake
        if (this.showRetake) this.showExemption = false
      } else {
        this.showExemption = !this.showExemption
        if (this.showExemption) this.showRetake = false
      }
    },
    submitRetake() {
      if (!this.retakeForm.gradeId || this.submitting) return
      this.submitting = true
      submitLock.run(() => studentApi.applyRetake({
        gradeId: this.retakeForm.gradeId,
        courseName: this.retakeForm.courseName,
        termCode: this.retakeForm.termCode,
        reason: this.retakeForm.reason.trim()
      }))
        .then(() => {
          uni.showToast({ title: '重修报名已提交', icon: 'success' })
          this.showRetake = false
          this.retakeForm.reason = ''
          this.load()
        })
        .catch((e) => toast(normalizeError(e).message || '提交失败'))
        .finally(() => { this.submitting = false })
    },
    submitExemption() {
      if (!this.exForm.courseName || this.submitting) return
      this.submitting = true
      submitLock.run(() => studentApi.applyExemption({
        courseName: this.exForm.courseName,
        termCode: this.exForm.termCode,
        reason: this.exForm.reason.trim()
      }))
        .then(() => {
          uni.showToast({ title: '免修申请已提交', icon: 'success' })
          this.showExemption = false
          this.exForm.reason = ''
          this.load()
        })
        .catch((e) => toast(normalizeError(e).message || '提交失败'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.mk__input { background: var(--bg-elevated, #f5f6f8); border-radius: 8px; padding: 10px 12px; font-size: 14px; }
.mk__textarea { background: var(--bg-elevated, #f5f6f8); border-radius: 8px; padding: 10px 12px; min-height: 72px; width: 100%; box-sizing: border-box; font-size: 14px; }
.mk__ph { color: var(--t4); }
.mk__sub { display: block; color: var(--t3); font-size: 12px; margin-top: 4px; }
.mk__reason { display: block; color: var(--danger, #dc2626); font-size: 12px; margin-top: 4px; }
.mk__hint { display: block; color: var(--t3); font-size: 12px; }
</style>
