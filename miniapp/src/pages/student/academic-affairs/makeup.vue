<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="补考重修" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="section-head">
          <text class="section-head__title">我的重修申请</text>
          <text class="section-head__more" @click="showForm = !showForm">{{ showForm ? '收起' : '+ 新增报名' }}</text>
        </view>

        <view class="card stack-sm" v-if="showForm">
          <input class="mk__input" v-model="form.courseName" placeholder="课程名称（必填）" placeholder-class="mk__ph" />
          <input class="mk__input" v-model="form.termCode" placeholder="学期（选填，如 2026-2027-1）" placeholder-class="mk__ph" />
          <textarea class="mk__textarea" v-model="form.reason" :maxlength="200" placeholder="申请说明（选填）" placeholder-class="mk__ph" />
          <button class="btn btn-primary" :disabled="!form.courseName.trim() || submitting" @click="submit">
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
        <MobileGlobalState v-else state="empty" title="暂无重修申请" description="点击右上角新增报名。" />

        <template v-if="d.exemptions.length">
          <view class="section-head"><text class="section-head__title">我的免修申请</text></view>
          <view class="list-group">
            <view v-for="e in d.exemptions" :key="e.exemptionId" class="list-row">
              <view class="flex-1">
                <text class="t-md">{{ e.courseName }}</text>
                <text class="mk__sub">{{ e.termCode || '—' }}</text>
                <text v-if="e.returnReason" class="mk__reason">{{ e.returnReason }}</text>
              </view>
              <MobileStatusTag :status="e.status" />
            </view>
          </view>
        </template>
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
    return { d: null, state: 'loading', showForm: false, submitting: false,
      form: { courseName: '', termCode: '', reason: '' } }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyMakeup().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    submit() {
      const name = this.form.courseName.trim()
      if (!name || this.submitting) return
      this.submitting = true
      submitLock.run(() => studentApi.applyRetake(name, this.form.termCode.trim(), this.form.reason.trim()))
        .then(() => {
          uni.showToast({ title: '重修报名已提交', icon: 'success' })
          this.showForm = false
          this.form = { courseName: '', termCode: '', reason: '' }
          this.load()
        }).catch((e) => {
          if (e && e.code === 'LOCKED') return
          toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试')
        }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.mk__input { width: 100%; height: 40px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 0 var(--space-3); box-sizing: border-box; }
.mk__textarea { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; }
.mk__ph { color: var(--text-tertiary); }
.mk__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.mk__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
</style>
