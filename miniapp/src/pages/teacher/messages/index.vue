<template>
  <view class="page-wrap">
    <view class="tm__hero hero-band is-teacher">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="tm__navbar"><text class="tm__navbar-title">消息</text></view>
      <view class="tm__search"><text class="tm__search-icon">🔍</text><text class="tm__search-ph">搜索通知、学生、消息</text></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="tm__cats">
          <view v-for="t in data.tabs" :key="t.key" class="tm__cat" @click="tab = t.key">
            <text v-if="t.badge" class="tm__cat-badge">{{ t.badge }}</text>
            <view class="icon-grid__badge" :class="[tabGrad(t.key), { 'is-off': tab !== t.key }]">{{ tabIcon(t.key) }}</view>
            <text class="tm__cat-lb" :class="{ 'is-on': tab === t.key }">{{ t.label }}</text>
          </view>
        </view>

        <view class="page-pad" style="padding-top:0;">
          <view class="tm__listbar">
            <text class="t-sm t-secondary t-bold">最近消息</text>
            <text class="tm__readall" :class="{ 'is-done': !list.some(m => !m.read) }" @click="markAllRead">✓ 全部已读</text>
          </view>
          <MobileGlobalState v-if="!list.length" state="empty" title="暂无消息" description="系统通知、学生动态、风险预警与催办提醒会汇总在这里。" />
          <view v-else class="stack-sm">
            <view v-for="m in pagedSlice(list)" :key="m.id" class="tm__item card" :class="{ 'is-unread': !m.read }" @click="open(m)">
              <view class="tm__top">
                <text class="tm__dot" :class="{ 'is-on': !m.read }" />
                <text class="tm__module">{{ m.module }}</text>
                <text v-if="m.level === 'high'" class="tm__urgent">重要</text>
                <text class="tm__time">{{ fromNow(m.time) }}</text>
              </view>
              <text class="tm__title">{{ m.title }}</text>
              <view v-if="tab === 'risk' || tab === 'dynamic'" class="tm__go" @click.stop="jump(tab)">去处理 ›</view>
            </view>
            <view v-if="pagedFooter(list) === 'more'" class="tm__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(list) === 'end'" class="tm__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="teacher" active="message" :badges="{ message: unreadTotal }" />
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { fromNow } from '@/utils/format'
import { listPaging } from '@/utils/listPaging'
import { go } from '@/utils/nav'
const TAB_ICON = { system: '📢', dynamic: '👥', risk: '⚠', urge: '⏰' }
const TAB_GRAD = { system: 'g1', dynamic: 'g5', risk: 'g6', urge: 'g4' }

export default {
  mixins: [listPaging(20)],
  data() { return { data: null, state: 'loading', tab: 'system', statusBarHeight: 20 } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  // onReachBottom 必须写在页面本身，mp-weixin 才会注册
  onReachBottom() { this.pagedReachBottom() },
  watch: {
    tab() { this.pagedReset() }
  },
  computed: {
    list() { return this.data ? (this.data.groups[this.tab] || []) : [] },
    unreadTotal() {
      if (!this.data) return 0
      return Object.values(this.data.groups).flat().filter((m) => !m.read).length
    }
  },
  methods: {
    fromNow,
    tabIcon(key) { return TAB_ICON[key] || '✉' },
    tabGrad(key) { return TAB_GRAD[key] || 'g8' },
    pagingList() { return this.list },
    load() {
      this.state = 'loading'
      this.pagedReset()
      teacherApi.getMessages().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    open(m) { m.read = true },
    markAllRead() { this.list.forEach((m) => { m.read = true }) },
    jump(tab) { go(tab === 'risk' ? '/pages/teacher/risk-students/index' : '/pages/teacher/todos/index') }
  }
}
</script>

<style scoped>
.tm__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.tm__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.tm__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.tm__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 10px var(--space-4); margin-top: var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-base); }
.tm__cats { display: flex; justify-content: space-between; padding: var(--space-4) var(--page-padding-mobile) var(--space-1); background: var(--bg-card); }
.tm__cat { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); position: relative; }
.tm__cat-badge { position: absolute; top: -4px; right: 2px; min-width: 17px; height: 17px; padding: 0 4px; border-radius: var(--radius-full); background: var(--danger-500); color: #fff; font-size: 10px; font-weight: var(--font-weight-semibold); display: flex; align-items: center; justify-content: center; border: 1.5px solid var(--bg-card); z-index: 1; }
.tm__cat .icon-grid__badge { width: 50px; height: 50px; border-radius: var(--radius-lg); }
.tm__cat .icon-grid__badge.is-off { filter: grayscale(.3); opacity: .55; }
.tm__cat-lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.tm__cat-lb.is-on { color: var(--teacher-700); font-weight: var(--font-weight-semibold); }
.tm__listbar { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0 var(--space-3); }
.tm__readall { display: flex; align-items: center; gap: 4px; font-size: var(--font-size-sm); color: var(--teacher-700); }
.tm__readall.is-done { color: var(--text-disabled); }
.tm__item.is-unread { border-left: 3px solid var(--teacher-600); }
.tm__top { display: flex; align-items: center; gap: var(--space-2); }
.tm__dot { width: 7px; height: 7px; border-radius: var(--radius-full); background: transparent; }
.tm__dot.is-on { background: var(--danger-500); }
.tm__module { font-size: var(--font-size-xs); color: var(--teacher-700); }
.tm__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-sm); }
.tm__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.tm__title { display: block; font-size: var(--font-size-md); color: var(--text-primary); margin-top: 6px; line-height: 1.4; }
.tm__go { margin-top: 8px; font-size: var(--font-size-sm); color: var(--teacher-700); }
.tm__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.tm__paging.is-end { color: var(--text-tertiary); }
</style>
