<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="o">
        <!-- 报到总览 -->
        <view class="or__hero card">
          <text class="or__hero-batch">{{ o.batch }}</text>
          <view class="or__hero-status">
            <text class="or__hero-icon" :class="{ 'is-pending': !reportDone }">{{ reportDone ? '✓' : '…' }}</text>
            <view class="flex-1">
              <text class="t-lg t-bold">{{ o.overallText }}</text>
              <text class="or__hero-sub">{{ heroSub }}</text>
            </view>
          </view>
          <view class="or__code" :class="{ 'is-invalid': !o.reportCode.valid }" @click="go('/pages/student/orientation/code/index')">
            <view class="flex-1">
              <text class="or__code-label">报到码</text>
              <text class="or__code-value">{{ o.reportCode.code }}</text>
            </view>
            <text class="or__code-note">{{ o.reportCode.valid ? '查看电子报到码 ›' : o.reportCode.note }}</text>
          </view>
        </view>

        <!-- 快捷操作 -->
        <view v-if="!reportDone" class="or__actions">
          <view class="or__action" @click="go('/pages/student/orientation/collect/index')">
            <text class="or__action-ic">📝</text><text>预报到信息采集</text>
          </view>
          <view v-if="o.greenChannelStatus === 'NOT_APPLIED'" class="or__action" @click="go('/pages/student/orientation/green-channel/index')">
            <text class="or__action-ic">🤝</text><text>绿色通道申请</text>
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
import { go, toast } from '@/utils/nav'
export default {
  data() { return { o: null, state: 'loading' } },
  onLoad() { this.load() },
  computed: {
    // 只有真实报到状态为「已现场报到 / 学院已确认」（mock 兼容 REGISTERED）才算完成，
    // 未报到/预报到不再显示"全部报到环节已完成"的假完成态
    reportDone() {
      const s = this.o && this.o.overallStatus
      return s === 'CHECKED_IN' || s === 'COLLEGE_CONFIRMED' || s === 'REGISTERED'
    },
    heroSub() {
      if (!this.o) return ''
      if (this.reportDone) return '全部报到环节已完成，欢迎加入！'
      if (this.o.blocked && this.o.blocked.reason) return '报到卡点：' + this.o.blocked.reason
      return '报到进行中，请尽快完成剩余报到环节'
    }
  },
  methods: {
    go,
    load() {
      this.state = 'loading'
      studentApi.getOrientation().then((d) => { this.o = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    call(c) { uni.makePhoneCall({ phoneNumber: c.phone, fail: () => toast('拨号未成功，可手动拨打：' + (c.phone || '')) }) }
  }
}
</script>

<style scoped>
.or__hero-batch { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.or__hero-status { display: flex; align-items: center; gap: var(--space-3); margin: var(--space-3) 0; }
.or__hero-icon { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--success-500); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 22px; }
.or__hero-icon.is-pending { background: var(--warning-500); }
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
.or__actions { display: flex; gap: var(--space-3); }
.or__action { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 6px; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4) var(--space-2); box-shadow: var(--shadow-card); font-size: var(--font-size-sm); color: var(--text-secondary); }
.or__action-ic { font-size: 22px; }
</style>
