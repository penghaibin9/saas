<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="消息" />
    <view class="msg__head">
      <view><text class="t-lg">教师消息</text><text class="msg__summary">未读 {{ unreadTotal }} · 服务端分页</text></view>
      <text class="msg__search" @click="openSearch">搜索</text>
    </view>
    <scroll-view scroll-x class="msg__tabs">
      <view class="msg__tabs-inner">
        <view v-for="t in tabs" :key="t.key" class="msg__tab" :class="{ 'msg__tab--active': tab === t.key }" @click="selectTab(t.key)">
          <text>{{ t.label }}</text><text v-if="Number(t.badge) > 0" class="msg__badge">{{ t.badge > 99 ? '99+' : t.badge }}</text>
        </view>
      </view>
    </scroll-view>
    <view class="page-pad">
      <MobileGlobalState v-if="state === 'loading' && !list.length" state="loading" title="消息加载中" />
      <MobileGlobalState v-else-if="state === 'error' && !list.length" state="error" title="消息加载失败" description="请检查网络后重试。" @retry="refresh" />
      <MobileGlobalState v-else-if="!list.length" state="empty" title="暂无消息" description="当前分类没有新的消息。" />
      <view v-else class="stack">
        <view v-for="m in list" :key="m.id" class="card msg__row" @click="openMessage(m)">
          <view class="row-between msg__row-top">
            <view class="msg__meta"><view v-if="!m.read" class="msg__dot" /><text class="t-sm t-tertiary">{{ m.module || currentTabLabel }}</text></view>
            <text class="t-xs t-tertiary">{{ fromNow(m.time || m.eventAt) }}</text>
          </view>
          <text class="msg__title" :class="{ 'msg__title--unread': !m.read }">{{ m.title }}</text>
          <view class="row-between msg__bottom">
            <view class="msg__tags"><text v-if="m.level === 'high'" class="msg__risk">重要</text><text v-if="m.requireAck && !m.acked" class="msg__ack">待确认</text><text v-if="m.withdrawn" class="msg__withdrawn">已撤回</text></view>
            <button v-if="canHandle(m)" class="btn btn-ghost msg__action" @click.stop="handle(m)">{{ (m.action && m.action.label) || '去处理' }}</button>
          </view>
        </view>
        <view class="msg__footer"><text v-if="pagerState.loading" class="t-sm t-tertiary">加载中…</text><text v-else-if="pagerState.hasMore" class="t-sm t-tertiary">继续上拉加载</text><text v-else class="t-sm t-tertiary">没有更多了</text></view>
      </view>
    </view>
    <MobileTabBar side="teacher" active="messages" />
  </view>
</template>

<script>
import { createNetworkPager } from '@/utils/networkPager'
import { fromNow } from '@/utils/format'
import { go } from '@/utils/nav'
import { stashDetail } from '@/utils/msgStash'
import { canNavigate, runAction } from '@/services/actionRouter'
import { getTeacherMessageBadges, getTeacherMessagesPage, markTeacherMessageRead } from '@/services/teacherMessagesV3Api'

const TAB_DEFS = [
  { key: 'system', label: '系统通知' }, { key: 'dynamic', label: '学生动态' },
  { key: 'risk', label: '风险预警' }, { key: 'urge', label: '催办提醒' }
]
const emptyPagerState = () => ({ items: [], cursor: '', hasMore: false, loading: false, refreshing: false, requestEpoch: 0, error: null })

export default {
  data() { return { tab: 'system', state: 'loading', badges: { system: 0, dynamic: 0, risk: 0, urge: 0 }, pagerState: emptyPagerState() } },
  computed: {
    tabs() { return TAB_DEFS.map((t) => ({ ...t, badge: Number(this.badges[t.key] || 0) })) },
    list() { return this.pagerState.items || [] },
    unreadTotal() { return Object.values(this.badges).reduce((sum, value) => sum + Number(value || 0), 0) },
    currentTabLabel() { const found = TAB_DEFS.find((t) => t.key === this.tab); return found ? found.label : '消息' }
  },
  onLoad() { this.setupPager(); this.refresh() },
  onUnload() { if (this._pager) this._pager.reset(); this._pager = null },
  onReachBottom() { if (this._pager) this._pager.loadMore().catch(() => { this.state = 'error' }) },
  onPullDownRefresh() { this.refresh().finally(() => uni.stopPullDownRefresh()) },
  methods: {
    setupPager() {
      if (this._pager) this._pager.reset()
      this._pager = createNetworkPager(async (cursor, pageSize) => {
        const data = await getTeacherMessagesPage({ tab: this.tab, cursor, pageSize })
        return { items: (data && data.items) || [], nextCursor: (data && data.nextCursor) || '' }
      }, { pageSize: 20, maxItems: 100, idKey: 'id' })
      this.pagerState = this._pager.state
    },
    async loadBadges() {
      try { const data = await getTeacherMessageBadges(); this.badges = { ...this.badges, ...((data && data.badges) || {}) } } catch (_error) {}
    },
    async refresh() {
      this.state = 'loading'
      try { await Promise.all([this._pager.refresh(), this.loadBadges()]); this.state = 'ready' } catch (_error) { this.state = 'error' }
    },
    async selectTab(next) { if (!next || next === this.tab) return; this.tab = next; this.setupPager(); await this.refresh() },
    openSearch() { go('/pages/common/search/index') },
    isDetailOnly(action) { return !!(action && action.target && action.target.path === '/pages/common/message-detail/index') },
    canHandle(m) { return !!(m && m.action && !this.isDetailOnly(m.action) && canNavigate(m.action, 'teacher')) },
    handle(m) { if (this.canHandle(m)) runAction(m.action, { side: 'teacher' }) },
    openMessage(m) { if (!m) return; stashDetail(m); this.markRead(m); go('/pages/common/message-detail/index?messageId=' + encodeURIComponent(String(m.messageId || m.id || ''))) },
    markRead(m) {
      if (!m || m.read || m.kind !== 'UNIFIED_MESSAGE') return
      const raw = String(m.messageId || m.id || ''); if (!/^\d+$/.test(raw)) return
      m.read = true; this.badges = { ...this.badges, [this.tab]: Math.max(0, Number(this.badges[this.tab] || 0) - 1) }
      markTeacherMessageRead(raw).catch(() => { m.read = false; this.badges = { ...this.badges, [this.tab]: Number(this.badges[this.tab] || 0) + 1 } })
    },
    fromNow
  }
}
</script>

<style scoped>
.msg__head { display:flex;align-items:center;justify-content:space-between;padding:var(--space-4) var(--page-padding-mobile) var(--space-2); }
.msg__summary { display:block;margin-top:2px;font-size:var(--font-size-xs);color:var(--text-tertiary); }.msg__search{font-size:var(--font-size-sm);color:var(--brand-primary);padding:var(--space-2)}
.msg__tabs{white-space:nowrap;border-bottom:1px solid var(--border-light)}.msg__tabs-inner{display:inline-flex;gap:var(--space-1);padding:0 var(--page-padding-mobile)}
.msg__tab{position:relative;display:flex;align-items:center;gap:4px;padding:var(--space-3) var(--space-2);font-size:var(--font-size-sm);color:var(--text-secondary)}.msg__tab--active{color:var(--brand-primary);font-weight:var(--font-weight-semibold)}.msg__tab--active::after{content:'';position:absolute;left:var(--space-2);right:var(--space-2);bottom:0;height:2px;background:var(--brand-primary);border-radius:2px}
.msg__badge{min-width:18px;height:18px;padding:0 5px;border-radius:9px;line-height:18px;text-align:center;font-size:10px;color:#fff;background:var(--danger-500)}
.msg__row{padding:var(--space-4)}.msg__row-top{gap:var(--space-2)}.msg__meta{display:flex;align-items:center;gap:6px;min-width:0}.msg__dot{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:var(--brand-primary)}
.msg__title{display:block;margin-top:var(--space-2);font-size:var(--font-size-base);color:var(--text-secondary);line-height:1.5}.msg__title--unread{color:var(--text-primary);font-weight:var(--font-weight-semibold)}
.msg__bottom{margin-top:var(--space-3);min-height:28px}.msg__tags{display:flex;gap:var(--space-2);align-items:center}.msg__risk,.msg__ack,.msg__withdrawn{font-size:11px;padding:2px 7px;border-radius:var(--radius-sm)}.msg__risk{color:var(--danger-700);background:var(--danger-50)}.msg__ack{color:var(--warning-700);background:var(--warning-50)}.msg__withdrawn{color:var(--text-tertiary);background:var(--bg-muted)}
.msg__action{min-height:28px;height:28px;line-height:26px;padding:0 var(--space-3);font-size:var(--font-size-xs)}.msg__footer{display:flex;justify-content:center;padding:var(--space-3) 0 var(--space-6)}
</style>
