<template>
  <view class="page-wrap">
    <view class="msg__hero hero-band is-brand">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="msg__navbar"><text class="msg__navbar-title">消息</text></view>
      <view class="msg__search"><text class="msg__search-icon">🔍</text><text class="msg__search-ph">搜索通知、消息</text></view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="msg__cats">
          <view v-for="t in data.tabs" :key="t.key" class="msg__cat" @click="tab = t.key">
            <text v-if="t.badge" class="msg__cat-badge">{{ t.badge }}</text>
            <view class="icon-grid__badge" :class="[tabGrad(t.key), { 'is-off': tab !== t.key }]">{{ tabIcon(t.key) }}</view>
            <text class="msg__cat-lb" :class="{ 'is-on': tab === t.key }">{{ t.label }}</text>
          </view>
        </view>

        <view class="page-pad" style="padding-top:0;">
          <view class="msg__listbar">
            <text class="t-sm t-secondary t-bold">最近消息</text>
            <text class="msg__readall" :class="{ 'is-done': !list.some(m => !m.read) }" @click="markAllRead">✓ 全部已读</text>
          </view>
          <MobileGlobalState v-if="!list.length" state="empty" title="暂无消息" description="这里会收到待办、通知、服务进度与课程教务消息。" />
          <view v-else class="stack-sm">
            <view v-for="m in pagedSlice(list)" :key="m.id" class="msg__item card" :class="{ 'is-unread': !m.read }" @click="open(m)">
              <view class="msg__item-top">
                <text class="msg__dot" :class="{ 'is-on': !m.read }" />
                <text class="msg__module">{{ m.module }}</text>
                <text v-if="m.level === 'high'" class="msg__urgent">重要</text>
                <text class="msg__time">{{ fromNow(m.time) }}</text>
              </view>
              <text class="msg__title">{{ m.title }}</text>
              <view v-if="m.deadline" class="msg__sub">截止 {{ deadlineText(m.deadline) }}</view>
              <view v-if="m.status" class="msg__sub"><MobileStatusTag :status="m.status" /></view>
              <view v-if="m.actionable || m.receipt" class="msg__actions">
                <text v-if="m.actionable" class="msg__btn is-primary" @click.stop="handle(m)">去处理</text>
                <text v-if="m.receipt" class="msg__btn" @click.stop="toast('回执确认功能即将开放')">确认回执</text>
              </view>
            </view>
            <view v-if="pagedFooter(list) === 'more'" class="msg__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(list) === 'end'" class="msg__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="message" :badges="{ message: unreadTotal }" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { fromNow, deadlineText } from '@/utils/format'
import { listPaging } from '@/utils/listPaging'
import { toast, go } from '@/utils/nav'
const TAB_ICON = { todo: '☑', notice: '📢', progress: '⏱', course: '📖' }
const TAB_GRAD = { todo: 'g1', notice: 'g1', progress: 'g3', course: 'g4' }

export default {
  mixins: [listPaging(20)],
  data() { return { data: null, state: 'loading', tab: 'todo', statusBarHeight: 20 } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  // onReachBottom 必须写在页面本身，mp-weixin 才会注册
  onReachBottom() { this.pagedReachBottom() },
  watch: {
    // 切换 tab 回到第一批
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
    toast, fromNow, deadlineText,
    tabIcon(key) { return TAB_ICON[key] || '✉' },
    tabGrad(key) { return TAB_GRAD[key] || 'g8' },
    pagingList() { return this.list },
    load() {
      this.state = 'loading'
      this.pagedReset()
      studentApi.getMessages().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    markAllRead() {
      this.list.forEach((m) => { if (!m.read) { m.read = true; this._syncRead(m) } })
    },
    /** 打开消息：本地即时置灰 + 真实通知（msg- 前缀）同步服务器已读，失败不打扰阅读 */
    open(m) {
      m.read = true
      this._syncRead(m)
    },
    _syncRead(m) {
      if (m._synced || !/^msg-\d+$/.test(String(m.id))) return
      m._synced = true
      studentApi.markMessageRead(String(m.id).replace('msg-', '')).catch(() => { m._synced = false })
    },
    handle(m) {
      m.read = true
      this._syncRead(m)
      if (m.status === 'RETURNED') return go('/pages/student/my-applications/index')
      go('/pages/student/campus-service/index')
    }
  }
}
</script>

<style scoped>
.msg__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.msg__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.msg__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.msg__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 10px var(--space-4); margin-top: var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-base); }
.msg__cats { display: flex; justify-content: space-between; padding: var(--space-4) var(--page-padding-mobile) var(--space-1); background: var(--bg-card); }
.msg__cat { display: flex; flex-direction: column; align-items: center; gap: var(--space-2); position: relative; }
.msg__cat-badge { position: absolute; top: -4px; right: 2px; min-width: 17px; height: 17px; padding: 0 4px; border-radius: var(--radius-full); background: var(--danger-500); color: #fff; font-size: 10px; font-weight: var(--font-weight-semibold); display: flex; align-items: center; justify-content: center; border: 1.5px solid var(--bg-card); z-index: 1; }
.msg__cat .icon-grid__badge { width: 50px; height: 50px; border-radius: var(--radius-lg); }
.msg__cat .icon-grid__badge.is-off { filter: grayscale(.3); opacity: .55; }
.msg__cat-lb { font-size: var(--font-size-xs); color: var(--text-secondary); }
.msg__cat-lb.is-on { color: var(--brand-primary); font-weight: var(--font-weight-semibold); }
.msg__listbar { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0 var(--space-3); }
.msg__readall { display: flex; align-items: center; gap: 4px; font-size: var(--font-size-sm); color: var(--brand-primary); }
.msg__readall.is-done { color: var(--text-disabled); }
.msg__item.is-unread { border-left: 3px solid var(--brand-primary); }
.msg__item-top { display: flex; align-items: center; gap: var(--space-2); }
.msg__dot { width: 7px; height: 7px; border-radius: var(--radius-full); background: transparent; }
.msg__dot.is-on { background: var(--danger-500); }
.msg__module { font-size: var(--font-size-xs); color: var(--brand-primary); }
.msg__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-sm); }
.msg__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.msg__title { display: block; font-size: var(--font-size-md); color: var(--text-primary); margin-top: 6px; line-height: 1.4; }
.msg__sub { margin-top: 6px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.msg__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.msg__btn { font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 5px 12px; }
.msg__btn.is-primary { color: #fff; background: var(--brand-primary); border-color: var(--brand-primary); }
.msg__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--brand-primary); }
.msg__paging.is-end { color: var(--text-tertiary); }
</style>
