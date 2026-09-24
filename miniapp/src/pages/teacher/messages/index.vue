<template>
  <view class="teacher-shell">
    <MobileTeacherHero title="消息" :role-label="roleLabel" />
    <view class="message-tools"><text v-if="badgeLoaded" class="ts-muted">未读 {{ unreadTotal }}</text><button class="ts-link ts-plain" @click="openSearch"><MobileShellIcon name="search" :size="18" />搜索消息</button></view>
    <scroll-view scroll-x class="ts-tabs"><view class="ts-tabs-inner"><button v-for="t in tabs" :key="t.key" class="ts-tab ts-plain" :class="{ 'is-active': tab === t.key }" @click="selectTab(t.key)"><text>{{ t.label }}</text><text v-if="badgeLoaded && t.badge" class="message-tab-badge" :aria-label="t.badge + '条未读'">{{ t.badge > 99 ? '99+' : t.badge }}</text></button></view></scroll-view>
    <view class="ts-pad message-content">
      <MobileGlobalState v-if="state !== 'ready' && (!list.length || state !== 'loading')" :state="state" :title="state === 'loading' ? '正在加载消息' : '消息加载失败'" @retry="refresh" />
      <view v-else-if="!list.length" class="ts-panel ts-empty">当前分类暂无消息。</view>
      <view v-else class="ts-panel">
        <view v-for="m in list" :key="m.id" class="ts-row message-row" @click="openMessage(m)">
          <MobileShellIcon :name="messageVisual().icon" :tone="messageVisual().tone" :size="25" round />
          <view class="ts-body"><view class="message-heading"><text class="ts-row-title" :class="{ 'message-read': m.read }">{{ m.title }}</text><view v-if="!m.read" class="message-unread" aria-label="未读" /></view>
            <text v-if="m.summary || m.content || m.body || m.description" class="ts-muted message-preview">{{ m.summary || m.content || m.body || m.description }}</text>
            <view class="message-tags"><text v-if="m.level === 'high'" class="message-risk">重要</text><text v-if="m.requireAck && !m.acked" class="message-ack">待确认</text><text v-if="m.withdrawn" class="ts-muted">已撤回</text></view>
            <view class="message-meta"><text>{{ m.module || currentTabLabel }}</text><text>{{ fromNow(m.time || m.eventAt) }}</text></view>
            <button v-if="canHandle(m)" class="ts-link ts-plain message-action" @click.stop="handle(m)">{{ m.action.label || '去处理' }}<MobileShellIcon name="chevron-right" :size="16" /></button>
          </view>
        </view>
      </view>
      <view v-if="pagingError" class="ts-error"><text>更多消息加载失败</text><button class="ts-link ts-plain" @click="loadMore">重试</button></view>
      <button v-else-if="pagerState.hasMore" class="message-more ts-link ts-plain" @click="loadMore">{{ pagerState.loading ? '加载中…' : '加载更多' }}</button>
    </view>
    <MobileTeacherTabBar ref="badges" active="message" :unread="badgeLoaded ? unreadTotal : null" />
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
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
  data() { return { tab: 'system', state: 'loading', badges: { system: 0, dynamic: 0, risk: 0, urge: 0 }, pagerState: emptyPagerState(), roleLabel: '', epoch: 0, pagingError: false, badgeLoaded: false } },
  computed: {
    tabs() { return TAB_DEFS.map((t) => ({ ...t, badge: Number(this.badges[t.key] || 0) })) },
    list() { return this.pagerState.items || [] },
    unreadTotal() { return Object.values(this.badges).reduce((sum, value) => sum + Number(value || 0), 0) },
    currentTabLabel() { const found = TAB_DEFS.find((t) => t.key === this.tab); return found ? found.label : '消息' }
  },
  onLoad() { this.setupPager() },
  onShow() {
    const session = useSessionStore()
    this.roleLabel = session.roleConfig.label
    const key = [currentSessionGeneration(), session.currentRole, session.identity.userId].join('|')
    if (this._context !== key) { this.tab = 'system'; this.badges = { system: 0, dynamic: 0, risk: 0, urge: 0 }; this.setupPager() }
    this._context = key
    this.refresh()
    this.$refs?.badges?.refresh()
  },
  onHide() { this.epoch++; this.$refs?.badges?.invalidate() },
  onUnload() { this.epoch++; if (this._pager) this._pager.reset(); this._pager = null },
  onReachBottom() { this.loadMore() },
  onPullDownRefresh() { this.refresh().finally(() => uni.stopPullDownRefresh()) },
  methods: {
    setupPager() {
      if (this._pager) this._pager.reset()
      this._pager = createNetworkPager(async (cursor, pageSize) => {
        const data = await getTeacherMessagesPage({ tab: this.tab, cursor, pageSize })
        return { items: (data && data.items) || [], nextCursor: (data && data.nextCursor) || '' }
      }, { pageSize: 20, maxItems: 100, idKey: 'id' })
      this.syncPagerState(this._pager.state)
    },
    syncPagerState(state) {
      const value = state || emptyPagerState()
      // createNetworkPager owns a plain object outside Vue's proxy.  Assign a fresh
      // snapshot after each request so H5/mini-program renderers observe item changes.
      this.pagerState = { ...value, items: [...(value.items || [])] }
    },
    async loadBadges(epoch = this.epoch) {
      const generation = currentSessionGeneration()
      try {
        const data = await getTeacherMessageBadges()
        if (epoch !== this.epoch || generation !== currentSessionGeneration()) return
        this.badges = { system: 0, dynamic: 0, risk: 0, urge: 0, ...(data.badges || {}) }; this.badgeLoaded = true
      } catch (_) { if (epoch === this.epoch) this.badgeLoaded = false }
    },
    async refresh() {
      const epoch = ++this.epoch, generation = currentSessionGeneration(), pager = this._pager
      if (!pager) return
      this.state = 'loading'; this.pagingError = false
      try {
        const [pagerState] = await Promise.all([pager.refresh(), this.loadBadges(epoch)])
        if (epoch !== this.epoch || generation !== currentSessionGeneration()) return
        this.syncPagerState(pagerState)
        this.state = 'ready'
      } catch (error) { if (epoch === this.epoch && generation === currentSessionGeneration()) this.state = normalizeError(error).pageState || 'error' }
    },
    async loadMore() {
      if (!this._pager || this.pagerState.loading || !this.pagerState.hasMore) return
      const epoch = this.epoch, generation = currentSessionGeneration(), pager = this._pager
      this.pagingError = false
      try {
        const value = await pager.loadMore()
        if (epoch === this.epoch && generation === currentSessionGeneration()) this.syncPagerState(value)
      } catch (_) { if (epoch === this.epoch && generation === currentSessionGeneration()) this.pagingError = true }
    },
    messageVisual() { return { system: { icon: 'bell', tone: 'violet' }, dynamic: { icon: 'file-text', tone: 'teal' }, risk: { icon: 'alert-circle', tone: 'red' }, urge: { icon: 'bell', tone: 'amber' } }[this.tab] },
    async selectTab(next) { if (!next || next === this.tab) return; this.tab = next; this.setupPager(); await this.refresh() },
    openSearch() { go('/pages/common/search/index') },
    isDetailOnly(action) { return !!(action && action.target && action.target.path === '/pages/common/message-detail/index') },
    canHandle(m) { return !!(m && m.action && !this.isDetailOnly(m.action) && canNavigate(m.action, 'teacher')) },
    handle(m) { if (this.canHandle(m)) runAction(m.action, { side: 'teacher' }) },
    openMessage(m) { if (!m) return; stashDetail(m); this.markRead(m); go('/pages/common/message-detail/index?messageId=' + encodeURIComponent(String(m.messageId || m.id || ''))) },
    markRead(m) {
      if (!m || m.read || m.kind !== 'UNIFIED_MESSAGE') return
      const raw = String(m.messageId || m.id || ''); if (!/^\d+$/.test(raw)) return
      const tab = this.tab, generation = currentSessionGeneration()
      m.read = true; this.badges = { ...this.badges, [tab]: Math.max(0, Number(this.badges[tab] || 0) - 1) }
      markTeacherMessageRead(raw).catch(() => {
        if (generation !== currentSessionGeneration()) return
        m.read = false; this.loadBadges()
      })
    },
    fromNow
  }
}
</script>
<style lang="scss">
@import '@/styles/teacher-shell.scss';
.teacher-shell {
.message-tools { display: flex; align-items: center; justify-content: space-between; padding: 0 20px; margin-top: -8px; position: relative; }
.message-tools .ts-link { margin-left: auto; font-size: 12px; }
.message-content { padding-top: 8px; }
.message-row { align-items: flex-start !important; padding-top: 22px !important; padding-bottom: 22px !important; }
.message-heading { display: flex; align-items: flex-start; gap: 8px; }
.message-heading .ts-row-title { flex: 1; }
.message-unread { width: 7px; height: 7px; border-radius: 50%; background: #ee5353; margin-top: 8px; flex-shrink: 0; }
.message-tab-badge { display: inline-block; vertical-align: middle; margin-left: 4px; min-width: 16px; padding: 0 4px; border-radius: 9px; background: #ee5353; color: #fff; font-size: 10px; line-height: 17px; text-align: center; }
.message-read { font-weight: 500 !important; }
.message-preview { margin-top: 6px; display: -webkit-box !important; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.message-meta { display: flex; flex-wrap: wrap; gap: 4px 12px; justify-content: space-between; margin-top: 16px; font-size: 12px; line-height: 1.6; color: #75839a; }
.message-tags { display: flex; gap: 6px; margin-top: 6px; }
.message-ack, .message-risk { padding: 3px 7px; border-radius: 5px; font-size: 12px; line-height: 1.5; }
.message-ack { color: #af7100; background: #fff3d6; }.message-risk { color: #d84b4b; background: #ffeded; }
.message-action { float: right; font-size: 13px !important; }.message-more { margin: 0 auto !important; }
}
</style>
