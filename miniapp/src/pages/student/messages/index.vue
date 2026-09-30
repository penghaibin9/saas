<template>
  <view class="student-shell">
    <MobileStudentHero title="消息" subtitle="重要通知与办理反馈，及时掌握">
      <view class="shell-search" @click="openSearch"><MobileShellIcon name="search" tone="gray" :size="22" /><text>搜索通知、消息</text></view>
    </MobileStudentHero>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="msg__cats">
          <view v-for="t in data.tabs" :key="t.key" class="msg__cat" @click="tab = t.key">
            <text v-if="t.badge" class="msg__cat-badge">{{ t.badge }}</text>
            <MobileShellIcon :name="tabIcon(t.key)" :tone="tab === t.key ? 'blue' : 'gray'" :size="29" />
            <text class="msg__cat-lb" :class="{ 'is-on': tab === t.key }">{{ t.label }}</text>
          </view>
        </view>

        <view class="shell-pad"><view class="shell-panel">
          <view class="msg__listbar">
            <text class="shell-title">{{ sectionTitle }}</text>
            <button v-if="tab === 'notice'" class="msg__readall shell-plain-button" :disabled="!readableUnread || markingAll" @click="markAllRead">{{ markingAll ? '处理中…' : hasMore ? '本页已读' : '全部已读' }}</button>
          </view>
          <view v-if="!list.length" class="shell-empty">
            <MobileShellIcon :name="tabIcon(tab)" tone="gray" :size="30" round />
            <text class="shell-row__title">{{ emptyTitle }}</text>
            <text class="shell-muted">{{ emptyDescription }}</text>
            <button v-if="tab !== 'notice' && noticeUnread" class="shell-plain-button msg__empty-link" @click="tab = 'notice'">查看 {{ noticeUnread }} 条未读通知</button>
          </view>
          <view v-else>
            <view v-for="m in list" :key="m.id" class="msg__item" :class="{ 'is-unread': !m.read, 'is-emg': m.emergency }" @click="open(m)">
              <MobileShellIcon :name="tab === 'notice' ? 'bell' : 'file-text'" :tone="m.emergency ? 'red' : tab === 'progress' ? 'teal' : 'blue'" :size="25" round />
              <view class="msg__content">
              <view class="msg__title-row"><text class="msg__title">{{ m.title }}</text><text v-if="!m.read && _canPersistRead(m)" class="msg__unread">未读</text></view>
              <view class="msg__item-top">
                <text class="msg__module">{{ messageModuleLabel(m.module) }}</text>
                <text v-if="m.emergency" class="msg__urgent">紧急</text>
                <text v-else-if="m.level === 'high'" class="msg__urgent">重要</text>
                <text class="msg__time">{{ fromNow(m.time) }}</text>
              </view>
              <text v-if="m.content || m.summary" class="msg__preview">{{ plainPreview(m) }}</text>
              <view v-if="m.receipt" class="msg__sub">待确认回执</view>
              <view v-if="m.deadline" class="msg__sub">截止 {{ deadlineText(m.deadline) }}</view>
              <view v-if="m.status && tab !== 'notice'" class="msg__sub"><MobileStatusTag :status="m.status" /></view>
              <view v-if="canRun(m)" class="msg__actions">
                <text class="msg__btn is-primary" @click.stop="handle(m)">{{ actionLabel(m) }}</text>
              </view>
              </view>
            </view>
            <view v-if="hasMore" class="msg__paging" @click="loadMore">
              {{ loadingMore ? '加载中…' : '上拉加载更多' }}
            </view>
            <view v-else class="msg__paging is-end">没有更多了</view>
          </view>
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
import { ensureStudentPerformanceApi } from '@/services/mobilePerformanceInstaller.student'
import { fromNow, deadlineText } from '@/utils/format'
import { toast, go } from '@/utils/nav'
import { canNavigate, disabledReasonOf, runAction } from '@/services/actionRouter'
import { stashDetail, stashSearchPool } from '@/utils/msgStash'
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { messageModuleLabel } from '@/services/messagePresentation'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
const TAB_ICON = { todo: 'clipboard-check', notice: 'bell', progress: 'clock', course: 'book' }
const TAB_GRAD = { todo: 'g1', notice: 'g1', progress: 'g3', course: 'g4' }
const PAGE_SIZE = 20

ensureStudentPerformanceApi()

export default {
  data() {
    return {
      data: { tabs: [], groups: {} }, state: 'loading', tab: 'notice', statusBarHeight: 20, markingAll: false,
      emg: null, emgAcking: false, page: 1, hasMore: false, loadingMore: false
    }
  },
  onLoad() {
    this._pageActive = true
    this.statusBarHeight = getStatusBarHeight()
    this.load({ reset: true })
  },
  onShow() {
    this._pageActive = true
    if (this._wasHidden) { this._wasHidden = false; this.load({ reset: true }) }
    if (this.data) this._pickEmergency()
  },
  onHide() { this._pageActive = false; this._wasHidden = true; this._messagesPromise = null; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onReachBottom() { this.loadMore() },
  watch: {
    tab() { this.load({ reset: true }) }
  },
  computed: {
    sectionTitle() { return { todo: '待我处理', notice: '学校通知', progress: '办理进度', course: '课程消息' }[this.tab] || '消息' },
    emptyTitle() { return { todo: '当前没有待处理事项', notice: '暂无学校通知', progress: '暂无办理进度' }[this.tab] || '暂无消息' },
    emptyDescription() { return { todo: '需要你处理或补交材料时，会显示在这里。', notice: '学校发布与你相关的通知后，会显示在这里。', progress: '提交申请后，可在这里查看进度与结果。' }[this.tab] || '有新消息时会显示在这里。' },
    noticeUnread() { return Number(this.data.tabs?.find(t => t.key === 'notice')?.badge) || 0 },
    readableUnread() { return this.list.filter(m => this._canPersistRead(m) && !m.read).length },
    list() { return this.data?.groups?.[this.tab] || [] },
    unreadTotal() {
      return (this.data.tabs || []).reduce((sum, item) => sum + (Number(item.badge) || 0), 0)
    }
  },
  methods: {
    toast, fromNow, deadlineText,
    messageModuleLabel,
    plainPreview(message) { return String(message.summary || message.content || '').replace(/<[^>]*>/g, '').slice(0, 100) },
    tabIcon(key) { return TAB_ICON[key] || 'mail' },
    tabGrad(key) { return TAB_GRAD[key] || 'g8' },
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true } = {}) {
      const requestedTab = this.tab
      const requestedPage = reset ? 1 : this.page + 1
      const session = currentSessionGeneration()
      if (this._session !== session) { this.data = { tabs: [], groups: {} }; this.emg = null; this._session = session }
      const requestKey = `${session}:${requestedTab}:${requestedPage}`
      if (this._messagesPromise && this._requestKey === requestKey) return this._messagesPromise
      this._requestKey = requestKey
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = studentApi.getMessagesPage(requestedTab, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.tab !== requestedTab || session !== currentSessionGeneration()) return result
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
          if (session !== currentSessionGeneration()) return
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          if (this._pageActive && this._loadEpoch === epoch && !reset) toast('加载更多失败，请重试')
        })
        .finally(() => {
          if (this._messagesPromise === pending) this._messagesPromise = null
          if (this._loadEpoch === epoch) this.loadingMore = false
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
      const message = this.emg
      const generation = currentSessionGeneration()
      const raw = String(message.messageId || message.id || '').replace('msg-', '')
      this.emgAcking = true
      try {
        await studentApi.ackMessageReceipt(raw)
        if (!this._pageActive || generation !== currentSessionGeneration()) return
        message.acked = true
        message.receipt = false
        toast('已确认')
        await this.load({ reset: true })
      } catch (e) {
        if (this._pageActive && generation === currentSessionGeneration()) toast((e && e.message) || '确认失败')
      } finally {
        this.emgAcking = false
      }
    },
    // 「待办/服务进度」的已读态由后端派生自真实业务状态（如请假是否仍 PENDING_REVIEW），
    // 不是可持久化的已读标记；本地伪装已读只会刷新前误导"事项已处理"，刷新后又会恢复，
    // 制造状态闪烁。因此所有标已读入口（全部已读/点开/去处理）都必须先过 _canPersistRead()，
    // 不可持久化的类型一律不动 read 字段（2026-08-04 复审二次收口：此前只在 markAllRead
    // 做了过滤，open/handle 仍无条件本地置 true，与本注释自相矛盾）。
    _canPersistRead(message) {
      if (!message || message.kind !== 'UNIFIED_MESSAGE') return false
      return /^\d+$/.test(String(message.messageId || message.id || '').replace('msg-', ''))
    },
    _markRead(message) {
      if (!this._canPersistRead(message) || message.read) return
      message.read = true
      return this._syncRead(message)
    },
    async markAllRead() {
      if (this.markingAll) return
      this.markingAll = true
      try { await Promise.all(this.list.filter(m => this._canPersistRead(m) && !m.read).map(message => this._markRead(message))) }
      finally { this.markingAll = false }
    },
    open(message) {
      this._markRead(message)
      stashDetail(message)
      go('/pages/common/message-detail/index?messageId=' + encodeURIComponent(String(message.messageId || message.id || '')))
    },
    openSearch() {
      stashSearchPool(Object.values((this.data && this.data.groups) || {}).flat())
      go('/pages/common/search/index')
    },
    _syncRead(message) {
      if (message._synced) return
      message._synced = true
      const raw = String(message.messageId || message.id || '').replace('msg-', '')
      // 失败时连同本地乐观的 read=true 一并回滚：只清 _synced 会让"已读"勾选留在界面上，
      // 却从未真正持久化，刷新前后不一致（2026-08-04 复审新增发现）。
      const generation = currentSessionGeneration(), snapshot = this.data
      return studentApi.markMessageRead(raw).then(() => {
        if (!this._pageActive || generation !== currentSessionGeneration() || this.data !== snapshot) return
        this.data.tabs = this.data.tabs.map(t => t.key === 'notice' ? { ...t, badge: Math.max(0, (Number(t.badge) || 0) - 1) } : t)
      }).catch(() => { message._synced = false; message.read = false; if (this._pageActive && generation === currentSessionGeneration()) toast('标记已读失败，请重试') })
    },
    // V3 §4.2：能不能处理、去哪里处理，都由服务端已解析的 action.target 决定。
    // 此前这里按 status === 'RETURNED' 猜「我的申请」大厅，否则一律丢到「在校服务」大厅，
    // 学生点完还得自己找那条记录（V3 深审 P0-02/P0-03）。
    canRun(message) { return canNavigate(message && message.action, 'student') },
    actionLabel(message) {
      const action = message && message.action
      return (action && action.label) || '去处理'
    },
    handle(message) {
      this._markRead(message)
      if (!this.canRun(message)) {
        toast(disabledReasonOf(message && message.action))
        return
      }
      runAction(message.action, { side: 'student' })
    }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/student-shell.scss';
.msg__hero { padding: 0 var(--page-padding-mobile) var(--space-4); }
.msg__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.msg__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.msg__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 10px var(--space-4); margin-top: var(--space-1); color: var(--text-tertiary); font-size: var(--font-size-base); }
.msg__cats { display: flex; justify-content: space-around; padding: 16px 16px 0; background: #fff; }
.msg__cat { display: flex; flex-direction: column; align-items: center; gap:8px; position: relative; min-width:75px; padding-bottom:14px; }
.msg__cat-badge { position: absolute; top: -4px; right: 2px; min-width: 17px; height: 17px; padding: 0 4px; border-radius: var(--radius-full); background: var(--danger-500); color: #fff; font-size: 10px; font-weight: var(--font-weight-semibold); display: flex; align-items: center; justify-content: center; border: 1.5px solid var(--bg-card); z-index: 1; }
.msg__cat .icon-grid__badge { width: 50px; height: 50px; border-radius: var(--radius-lg); }
.msg__cat .icon-grid__badge.is-off { filter: grayscale(.3); opacity: .55; }
.msg__cat-lb { font-size:14px; color:#65718a; }
.msg__cat-lb.is-on { color:#1671f8; font-weight:600; }
.msg__cat-lb.is-on::after { content:''; display:block; position:absolute; bottom:0; left:25%; width:50%; height:3px; border-radius:3px; background:#1671f8; }
.msg__listbar { display: flex; align-items: center; justify-content: space-between; padding: var(--space-2) 0 var(--space-3); }
.msg__readall { display: flex; align-items: center; gap: 4px; font-size: var(--font-size-sm); color: var(--brand-primary); }
.msg__readall.is-done { color: var(--text-disabled); }
.msg__item { display:flex; align-items:flex-start; gap:12px; padding:18px 0; border-bottom:1px solid #edf0f5; }
.msg__item:last-child { border-bottom:0; }
.msg__content { flex:1; min-width:0; }
.msg__title-row { display:flex; align-items:baseline; gap:6px; }
.msg__unread { flex-shrink:0; font-size:11px; color:#1671f8; }
.msg__preview { display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; margin-top:8px; font-size:14px; color:#65718a; line-height:1.6; }
.msg__empty-link { margin:12px auto 0; color:#1671f8; min-height:44px; font-size:14px; }
.msg__readall { min-height:44px; }
.msg__readall[disabled] { color:#9aa4b5; background:transparent; }
.msg__item.is-emg { border-left-color: var(--danger-500); }
.msg__item-top { display: flex; align-items: center; gap: var(--space-2); }
.msg__dot { width: 7px; height: 7px; border-radius: var(--radius-full); background: transparent; }
.msg__dot.is-on { background: var(--danger-500); }
.msg__module { font-size:12px; color:#65718a; }
.msg__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-sm); }
.msg__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.msg__title { display:block; font-size:16px; font-weight:600; color:#142440; line-height:1.5; }
.msg__item-top { flex-wrap:wrap; margin-top:6px; }
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
