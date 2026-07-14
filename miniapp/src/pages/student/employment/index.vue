<template>
  <view class="page-wrap">
    <view class="em__hero hero-band is-brand">
      <view class="hero-band__orb" />
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="em__navbar"><text class="em__navbar-back" @click="back">‹</text><text class="em__navbar-title">毕业与就业</text></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="e" style="padding-top: var(--space-3);">
        <MobileGlobalState v-if="!e.hasData" state="empty" title="暂无就业记录" description="就业老师登记去向后会显示在这里，如有疑问请联系就业老师。" />

        <template v-else>
          <view class="card">
            <view class="row-between">
              <text class="t-lg t-bold">{{ destinationText(e.destinationType) }}</text>
              <MobileStatusTag :label="verifyText(e.verifyStatus)" :type="verifyTag(e.verifyStatus)" />
            </view>
            <view class="em__dest" v-if="e.companyName">
              <text class="em__dest-t">{{ e.companyName }}</text>
              <text class="em__dest-job" v-if="e.jobTitle">{{ e.jobTitle }}</text>
            </view>
            <text class="em__hint">去向信息如有误差，请联系就业老师更正，本页不支持学生自行修改。</text>
          </view>

          <view class="section-head"><text class="section-head__title">材料状态（{{ materialStatusText(e.materialStatus) }}）</text></view>
          <view class="list-group" v-if="e.materials.length">
            <view v-for="(m, i) in e.materials" :key="i" class="list-row">
              <text class="flex-1 t-md">{{ m.type || '—' }}</text>
              <text class="em__file" v-if="m.fileName">{{ m.fileName }}</text>
              <MobileStatusTag :status="m.status" />
            </view>
          </view>
          <MobileGlobalState v-else state="empty" title="暂无材料记录" description="三方协议/劳动合同等材料由就业老师登记后会显示在这里。" />

          <view class="section-head"><text class="section-head__title">跟进记录</text></view>
          <view class="list-group" v-if="e.followUps.length">
            <view v-for="(f, i) in e.followUps" :key="i" class="list-row">
              <view class="flex-1">
                <text class="t-md">{{ f.content || '—' }}</text>
                <text class="em__sub">{{ f.way || '—' }} · {{ (f.time || '').slice(0, 10) }}</text>
              </view>
            </view>
          </view>
          <MobileGlobalState v-else state="empty" title="暂无跟进记录" description="就业老师跟进后会显示在这里。" />
        </template>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'

const DEST_TEXT = { SIGNED: '签约就业', FLEXIBLE: '灵活就业', FURTHER_STUDY: '升学', ENLISTED: '入伍',
  STARTUP: '自主创业', UNEMPLOYED: '待就业' }
const VERIFY_TEXT = { NOT_STARTED: '未核验', PENDING: '核验中', VERIFIED: '已核验', REJECTED: '核验未通过' }
const VERIFY_TAG = { NOT_STARTED: 'default', PENDING: 'warning', VERIFIED: 'success', REJECTED: 'danger' }
const MATERIAL_TEXT = { NOT_STARTED: '未提交', PENDING: '待审核', APPROVED: '已通过', RETURNED: '已退回' }

export default {
  data() { return { e: null, state: 'loading', statusBarHeight: 20 } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (err) {}
    this.load()
  },
  methods: {
    back() { uni.navigateBack({ delta: 1, fail: () => go('/pages/student/home/index') }) },
    destinationText(t) { return DEST_TEXT[t] || t || '待就业' },
    verifyText(s) { return VERIFY_TEXT[s] || s || '未核验' },
    verifyTag(s) { return VERIFY_TAG[s] || 'default' },
    materialStatusText(s) { return MATERIAL_TEXT[s] || s || '未提交' },
    load() {
      this.state = 'loading'
      studentApi.getEmployment().then((d) => { this.e = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.em__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.em__navbar { position: relative; height: 40px; display: flex; align-items: center; justify-content: center; }
.em__navbar-back { position: absolute; left: 0; color: #fff; font-size: 22px; padding: 4px 8px; }
.em__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.em__dest { margin-top: var(--space-2); }
.em__dest-t { display: block; font-size: var(--font-size-base); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.em__dest-job { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.em__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: var(--space-3); }
.em__file { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-right: var(--space-2); }
.em__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
</style>
