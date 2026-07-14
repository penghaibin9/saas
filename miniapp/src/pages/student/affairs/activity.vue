<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="活动与第二课堂" back />
    <view class="ac__tabs">
      <text class="ac__tab" :class="{ 'is-active': tab === 'available' }" @click="tab = 'available'">可报名</text>
      <text class="ac__tab" :class="{ 'is-active': tab === 'mine' }" @click="tab = 'mine'">我的报名（{{ (d && d.mine.length) || 0 }}）</text>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="d">
        <template v-if="tab === 'available'">
          <MobileGlobalState v-if="!d.available.length" state="empty" title="暂无可报名活动" description="学工处发布活动后会显示在这里。" />
          <view class="list-group" v-else>
            <view v-for="a in d.available" :key="a.activityId" class="list-row ac__row">
              <view class="flex-1">
                <text class="t-md">{{ a.activityName }}</text>
                <text class="ac__sub">{{ a.activityTypeLabel }} · {{ (a.startAt || '').slice(0, 16).replace('T', ' ') }} · {{ a.location || '—' }}</text>
                <text class="ac__sub" v-if="a.creditValue">二课学分 {{ a.creditValue }}</text>
              </view>
              <button
                class="btn ac__btn"
                :class="a.mySignupStatus ? 'btn-ghost' : 'btn-primary'"
                :disabled="acting === a.activityId"
                @click="a.mySignupStatus ? cancelEnroll(a) : enroll(a)"
              >{{ acting === a.activityId ? '…' : (a.mySignupStatus ? '取消报名' : '报名') }}</button>
            </view>
          </view>
        </template>

        <template v-else>
          <MobileGlobalState v-if="!d.mine.length" state="empty" title="暂无报名记录" description="在「可报名」中报名后会显示在这里。" />
          <view class="list-group" v-else>
            <view v-for="a in d.mine" :key="a.activityId" class="list-row ac__row">
              <view class="flex-1">
                <text class="t-md">{{ a.activityName }}</text>
                <text class="ac__sub">{{ a.activityTypeLabel }} · {{ (a.startAt || '').slice(0, 16).replace('T', ' ') }}</text>
              </view>
              <MobileStatusTag :label="signupLabel(a.mySignupStatus)" :type="signupTag(a.mySignupStatus)" />
              <button
                v-if="a.status === 'ONGOING' && a.mySignupStatus === 'ENROLLED'"
                class="btn btn-primary ac__btn" :disabled="acting === a.activityId" @click="checkin(a)"
              >{{ acting === a.activityId ? '…' : '签到' }}</button>
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const SIGNUP_LABEL = { ENROLLED: '已报名', WAITLIST: '候补中', CHECKED_IN: '已签到', CONFIRMED: '已确认', CANCELLED: '已取消' }
const SIGNUP_TAG = { ENROLLED: 'processing', WAITLIST: 'warning', CHECKED_IN: 'success', CONFIRMED: 'success', CANCELLED: 'default' }

export default {
  data() { return { d: null, state: 'loading', tab: 'available', acting: null } },
  onLoad() { this.load() },
  methods: {
    signupLabel(s) { return SIGNUP_LABEL[s] || s || '未报名' },
    signupTag(s) { return SIGNUP_TAG[s] || 'default' },
    load() {
      this.state = 'loading'
      studentApi.getMyActivities().then((d) => { this.d = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    enroll(a) {
      if (this.acting) return
      this.acting = a.activityId
      studentApi.enrollActivity(a.activityId, 'ENROLL').then(() => {
        uni.showToast({ title: '报名成功', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '报名失败，请稍后重试'))
        .finally(() => { this.acting = null })
    },
    cancelEnroll(a) {
      if (this.acting) return
      this.acting = a.activityId
      studentApi.enrollActivity(a.activityId, 'CANCEL').then(() => {
        uni.showToast({ title: '已取消报名', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '取消失败，请稍后重试'))
        .finally(() => { this.acting = null })
    },
    checkin(a) {
      if (this.acting) return
      this.acting = a.activityId
      studentApi.checkinActivity(a.activityId, 'MANUAL').then(() => {
        uni.showToast({ title: '签到成功', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '签到失败，请稍后重试'))
        .finally(() => { this.acting = null })
    }
  }
}
</script>

<style scoped>
.ac__tabs { display: flex; background: var(--bg-card); padding: 0 var(--page-padding-mobile); border-bottom: 1px solid var(--border-light); }
.ac__tab { flex: 1; text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.ac__tab.is-active { color: var(--brand-primary); font-weight: var(--font-weight-semibold); border-bottom: 2px solid var(--brand-primary); }
.ac__row { align-items: center; }
.ac__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ac__btn { flex-shrink: 0; min-height: 32px; padding: 0 var(--space-3); font-size: var(--font-size-sm); margin-left: var(--space-2); }
</style>
