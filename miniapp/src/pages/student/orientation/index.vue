<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="o">
        <!-- 报到总览 -->
        <view class="or__hero card">
          <text class="or__hero-batch">{{ o.batch }}</text>
          <view class="or__hero-status">
            <text class="or__hero-icon">✓</text>
            <view class="flex-1">
              <text class="t-lg t-bold">{{ o.overallText }}</text>
              <text class="or__hero-sub">全部报到环节已完成，欢迎加入！</text>
            </view>
          </view>
          <view class="or__code" :class="{ 'is-invalid': !o.reportCode.valid }">
            <view class="flex-1">
              <text class="or__code-label">报到码</text>
              <text class="or__code-value">{{ o.reportCode.code }}</text>
            </view>
            <text class="or__code-note">{{ o.reportCode.note }}</text>
          </view>
        </view>

        <!-- 报到流程时间线 -->
        <view class="section-head"><text class="section-head__title">报到流程</text></view>
        <view class="card">
          <MobileTimeline :nodes="o.steps" />
        </view>

        <!-- 联系人 -->
        <view class="section-head"><text class="section-head__title">联系人</text></view>
        <view class="card stack-sm">
          <view v-for="c in o.contacts" :key="c.role" class="or__contact">
            <view class="or__contact-avatar">{{ c.name.slice(0,1) }}</view>
            <view class="flex-1">
              <text class="t-md">{{ c.name }}</text>
              <text class="or__contact-role">{{ c.role }}</text>
            </view>
            <view class="or__contact-call" @click="call(c)">☎ 联系</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { o: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getOrientation().then((d) => { this.o = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    call(c) { uni.makePhoneCall({ phoneNumber: c.phone, fail: () => toast('拨打 ' + c.name + '（演示）') }) }
  }
}
</script>

<style scoped>
.or__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.or__hero-status { display: flex; align-items: center; gap: var(--space-3); margin: var(--space-3) 0; }
.or__hero-icon { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--success-500); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.or__hero-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.or__code { display: flex; align-items: center; gap: var(--space-3); background: var(--primary-50); border-radius: var(--radius-md); padding: var(--space-3); }
.or__code.is-invalid { background: var(--gray-100); }
.or__code-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.or__code-value { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); letter-spacing: 1px; }
.or__code-note { font-size: var(--font-size-xs); color: var(--text-tertiary); max-width: 44%; text-align: right; }
.or__contact { display: flex; align-items: center; gap: var(--space-3); }
.or__contact-avatar { width: 38px; height: 38px; border-radius: var(--radius-full); background: var(--primary-50); color: var(--brand-primary); display: flex; align-items: center; justify-content: center; }
.or__contact-role { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.or__contact-call { font-size: var(--font-size-sm); color: var(--brand-primary); border: 1px solid var(--brand-primary); border-radius: var(--radius-full); padding: 5px 12px; }
</style>
