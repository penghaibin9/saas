<template>
  <view class="page-wrap">
    <view class="msg__hero hero-band is-brand">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="msg__navbar"><text class="msg__navbar-title">消息</text></view>
      <view class="msg__search" @click="openSearch"><text class="msg__search-icon">🔍</text><text class="msg__search-ph">搜索通知、消息</text></view>
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
            <view v-for="m in list" :key="m.id" class="msg__item card" :class="{ 'is-unread': !m.read, 'is-emg': m.emergency }" @click="open(m)">
              <view class="msg__item-top">
                <text class="msg__dot" :class="{ 'is-on': !m.read }" />
                <text class="msg__module">{{ m.module }}</text>
                <text v-if="m.emergency" class="msg__urgent">紧急</text>
                <text v-else-if="m.level === 'high'" class="msg__urgent">重要</text>
                <text class="msg__time">{{ fromNow(m.time) }}</text>
              </view>
              <text class="msg__title">{{ m.title }}</text>
              <view v-if="m.receipt" class="msg__sub">待确认回执</view>
              <view v-if="m.deadline" class="msg__sub">截止 {{ deadlineText(m.deadline) }}</view>
              <view v-if="m.status" class="msg__sub"><MobileStatusTag :status="m.status" /></view>
              <view v-if="m.actionable" class="msg__actions">
                <text v-if="m.actionable" class="msg__btn is-primary" @click.stop="handle(m)">去处理</text>
              </view>
            </view>
            <view v-if="hasMore" class="msg__paging" @click="loadMore">
              {{ loadingMore ? '加载中…' : '上拉加载更多' }}
            </view>
            <view v-else class="msg__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="message" :badges="{ message: unreadTotal }" />

    <view v-if="emg" class="emg-mask" @touchmove.stop.prevent>
      <view class="emg-sheet">
        <text class="emg-sheet__tag">紧急通知</text>
        <text class="emg-sheet__title">{{ emg.title }}</text>
        <text class="emg-sheet__body">{{ emg.content || '请立即查看并确认已阅。' }}</text>
        <view class="emg-sheet__acts">
          <button class="btn btn-ghost flex-1" @click="openEmg">查看详情</button>
          <button class="btn btn-primary flex-1" :disabled="emgAcking" @click="ackEmg">
            {{ emgAcking ? '提交中…' : '确认已阅' }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { fromNow, deadlineText } from '@/utils/format'
import { toast, go } from '@/utils/nav'
import { stashDetail, stashSearchPool } from '@/utils/msgStash'
const TAB_ICON = { todo: '☑', notice: '📢', progress: '⏱', course: '📖' }
const TAB_GRAD = { todo: 'g1', notice: 'g1', progress: 'g3', course: 'g4' }
const PAGE_SIZE = 20

export default {
  data() {
    return {
      data: { tabs: [], groups: {} }, state: 'loading', tab: 'todo', statusBarHeight: 20,
      emg: null, emgAcking: false, page: 1, hasMore: false, loadingMore: false
    }
  },
  onLoad() {
    this._pageActive = true
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load({ reset: true })
  },
  onShow() {
    this._pageActive = true
    if (this.data) this._pickEmergency()
  },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onReachBottom() { this.loadMore() },
  watch: {
    tab() { this.load({ reset: true }) }
  },
  computed: {
    list() { return this.data?.groups?.[this.tab] || [] },
    unreadTotal() {
      return (this.data.tabs || []).reduce((sum, item) => sum + (Number(item.badge) || 0), 0)
    }
  },
  methods: {
    toast, fromNow, deadlineText,
    tabIcon(key) { return TAB_ICON[key] || '✉' },
    tabGrad(key) { return TAB_GRAD[key] || 'g8' },
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true } = {}) {
      if (this._messagesPromise) return this._messagesPromise
      const requestedTab = this.tab
      const requestedPage = reset ? 1 : this.page + 1
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = studentApi.getMessagesPage(requestedTab, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.tab !== requestedTab) return result
          const incoming = Array.isArray(result.list) ? result.list : []
          const previous = reset ? [] : (this.data.groups[requestedTab] || [])
          this.data = {
            ...this.data,
            tabs: result.tabs || this.data.tabs || [],
            groups: { ...this.data.groups, [requestedTab]: [...previous, ...incoming] },
            emergencyPending: result.emergencyPending || this.data.emergencyPending || []
          }
          this.page = Number(result.page) || requestedPage
          this.hasMore = !!result.hasMore
          this.state = 'ready'
          this._pickEmergency()
          return result
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._messagesPromise === pending) this._messagesPromise = null
          this.loadingMore = false
        })
      this._messagesPromise = pending
      return pending
    },
    _pickEmergency() {
      const list = (this.data && this.data.emergencyPending) || []
      this.emg = list.find((item) => item && item.receipt && !item.acked) || null
    },
    openEmg() { if (this.emg) this.open(this.emg) },
    async ackEmg() {
      if (!this.emg || this.emgAcking) return
      const raw = String(this.emg.messageId || this.emg.id || '').replace('msg-', '')
      this.emgAcking = true
      try {
        await studentApi.ackMessageReceipt(raw)
        this.emg.acked = true
        this.emg.receipt = false
        this.emg.read = true
        toast('已确认')
        await this.load({ reset: true })
      } catch (e) {
        toast((e && e.message) || '确认失败')
      } finally {
        this.emgAcking = false
      }
    },
    markAllRead() {
      this.list.forEach((message) => {
        if (!message.read) { message.read = true; this._syncRead(message) }
      })
    },
    open(message) {
      message.read = true
      this._syncRead(message)
      stashDetail(message)
      go('/pages/common/message-detail/index')
    },
    openSearch() {
      stashSearchPool(Object.values((this.data && this.data.groups) || {}).flat())
      go('/pages/common/search/index')
    },
    _syncRead(message) {
      if (message._synced) return
      const raw = String(message.messageId || message.id || '').replace('msg-', '')
      const isUnified = message.kind === 'UNIFIED_MESSAGE' || /^\d+$/.test(raw)
      if (!isUnified) return
      message._synced = true
      studentApi.markMessageRead(raw).catch(() => { message._synced = false })
    },
    handle(message) {
      message.read = true
      this._syncRead(message)
      if (message.status === 'RETURNED') return go('/pages/student/my-applications/index')
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
.msg__item.is-emg { border-left-color: var(--danger-500); }
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
.emg-mask {
  position: fixed; inset: 0; z-index: 1000; background: rgba(15, 23, 42, 0.55);
  display: flex; align-items: flex-end; justify-content: center;
}
.emg-sheet {
  width: 100%; background: #fff; border-radius: 16px 16px 0 0;
  padding: 20px 16px calc(16px + env(safe-area-inset-bottom));
}
.emg-sheet__tag {
  display: inline-block; font-size: 11px; color: #fff; background: var(--danger-500);
  padding: 2px 8px; border-radius: 4px; margin-bottom: 8px;
}
.emg-sheet__title {
  display: block; font-size: 17px; font-weight: 600; color: var(--text-primary); line-height: 1.4;
}
.emg-sheet__body {
  display: block; margin-top: 10px; font-size: 14px; color: var(--text-secondary);
  line-height: 1.6; max-height: 40vh; overflow: auto; white-space: pre-wrap;
}
.emg-sheet__acts { display: flex; gap: 10px; margin-top: 16px; }
</style>
