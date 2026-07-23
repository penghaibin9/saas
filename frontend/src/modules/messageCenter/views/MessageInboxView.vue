<template>
  <ModulePageShell
    title="我的消息"
    :subtitle="subtitle"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <template #actions>
      <button type="button" class="mc-btn mc-btn--ghost" @click="goSettings">消息设置</button>
      <button
        type="button"
        class="mc-btn mc-btn--primary"
        :disabled="readingAll || !counts.UNREAD"
        @click="onReadAll"
      >
        {{ readingAll ? '处理中…' : '全部已读' }}
      </button>
    </template>

    <ErrorState v-if="fatalError" :description="fatalError" @retry="bootstrap" />

    <div v-else class="mc-inbox" :class="{ 'is-narrow': narrow }">
      <!-- 左：分类 -->
      <aside class="mc-inbox__nav" aria-label="消息分类">
        <button
          v-for="c in categories"
          :key="c.key"
          type="button"
          class="mc-nav"
          :class="{ 'is-active': category === c.key }"
          @click="setCategory(c.key)"
        >
          <span class="mc-nav__label">{{ c.label }}</span>
          <span class="mc-nav__count">{{ counts[c.key] || 0 }}</span>
        </button>
        <div class="mc-nav__sep" />
        <button
          type="button"
          class="mc-nav"
          :class="{ 'is-active': readState === 'UNREAD' }"
          @click="setReadState('UNREAD')"
        >
          <span class="mc-nav__label">未读</span>
          <span class="mc-nav__count">{{ counts.UNREAD || 0 }}</span>
        </button>
        <button
          type="button"
          class="mc-nav"
          :class="{ 'is-active': readState === 'READ' }"
          @click="setReadState('READ')"
        >
          <span class="mc-nav__label">已读</span>
          <span class="mc-nav__count">{{ counts.READ || 0 }}</span>
        </button>
      </aside>

      <!-- 中：列表 -->
      <section class="mc-inbox__list" aria-label="消息列表">
        <LoadingState v-if="listLoading" text="加载消息…" />
        <EmptyState
          v-else-if="!items.length"
          title="暂无消息"
          description="这里只显示别人发给你的通知。你自己发布的内容请到左侧「发布记录」查看。"
        />
        <ul v-else class="mc-list">
          <li
            v-for="m in items"
            :key="m.messageId"
            class="mc-list__item"
            :class="{
              'is-active': m.messageId === selectedId,
              'is-unread': m.readStatus === 'UNREAD',
              'is-emergency': m.emergency
            }"
            @click="selectMessage(m.messageId)"
          >
            <div class="mc-list__top">
              <span v-if="m.emergency" class="mc-tag mc-tag--danger">紧急</span>
              <span v-else-if="m.pinned" class="mc-tag">置顶</span>
              <span v-if="m.requireAck && !m.acked" class="mc-tag mc-tag--warn">待确认</span>
              <span v-if="m.withdrawn" class="mc-tag">已撤回</span>
              <span v-if="m.expired" class="mc-tag">已失效</span>
              <span v-if="m.readStatus === 'UNREAD'" class="mc-dot" aria-label="未读" />
            </div>
            <div class="mc-list__title">{{ m.title }}</div>
            <div class="mc-list__meta">
              <span>{{ m.senderOrgName || '系统' }}</span>
              <span>{{ formatTime(m.createdAt) }}</span>
            </div>
            <div v-if="m.summary" class="mc-list__sum">{{ m.summary }}</div>
          </li>
        </ul>
        <div v-if="total > items.length" class="mc-list__more">
          <button type="button" class="mc-btn mc-btn--ghost" :disabled="listLoading" @click="loadMore">
            加载更多
          </button>
        </div>
      </section>

      <!-- 右：详情（窄屏改抽屉） -->
      <section v-if="!narrow || selectedId" class="mc-inbox__detail" aria-label="消息详情">
        <button v-if="narrow && selectedId" type="button" class="mc-drawer-close" @click="clearSelection">
          关闭
        </button>
        <LoadingState v-if="detailLoading" text="加载详情…" />
        <EmptyState
          v-else-if="!detail"
          title="选择一条消息"
          description="在中间列表点击查看正文与操作"
        />
        <article v-else class="mc-detail">
          <header class="mc-detail__head">
            <div class="mc-detail__tags">
              <span v-if="detail.emergency" class="mc-tag mc-tag--danger">紧急</span>
              <span v-if="detail.requireAck && !detail.acked" class="mc-tag mc-tag--warn">待确认</span>
              <span v-if="detail.withdrawn" class="mc-tag">已撤回</span>
              <span v-if="detail.expired" class="mc-tag">已失效</span>
            </div>
            <h2 class="mc-detail__title">{{ detail.title }}</h2>
            <div class="mc-detail__meta">
              <span>{{ detail.senderOrgName || '系统' }}</span>
              <span>发布 {{ formatTime(detail.createdAt) }}</span>
              <span v-if="detail.expireAt">有效至 {{ formatTime(detail.expireAt) }}</span>
            </div>
          </header>
          <div v-if="detail.withdrawn && detail.withdrawReason" class="mc-detail__alert">
            撤回说明：{{ detail.withdrawReason }}
          </div>
          <div class="mc-detail__body">{{ detail.contentPlain || detail.content || detail.summary }}</div>
          <footer class="mc-detail__foot">
            <div class="mc-detail__status">
              <span v-if="detail.readAt">已读 {{ formatTime(detail.readAt) }}</span>
              <span v-else>未读</span>
              <span v-if="detail.ackAt">· 已确认 {{ formatTime(detail.ackAt) }}</span>
            </div>
            <div class="mc-detail__actions">
              <button
                v-if="detail.readStatus === 'UNREAD'"
                type="button"
                class="mc-btn mc-btn--ghost"
                :disabled="acting"
                @click="onRead"
              >
                标为已读
              </button>
              <button
                v-if="detail.requireAck && !detail.acked && !detail.withdrawn"
                type="button"
                class="mc-btn mc-btn--primary"
                :disabled="acting"
                @click="onAck"
              >
                我已知晓
              </button>
              <button
                v-if="detail.actionKey"
                type="button"
                class="mc-btn mc-btn--primary"
                @click="onAction"
              >
                去办理
              </button>
            </div>
          </footer>
        </article>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 我的消息三栏布局。筛选写入 URL：category / readState / messageId。
 * 打开详情不自动已读；停留后由用户显式「标为已读」或确认回执。
 */
import { ModulePageShell, LoadingState, EmptyState, ErrorState } from '@/components/business'
import {
  fetchMessages,
  fetchMessageCategories,
  fetchMessageDetail,
  markMessageRead,
  markMessagesReadAll,
  ackMessage
} from '@/modules/messageCenter/api/message-center.api'
import { fetchActionKeys } from '@/modules/messageCenter/api/message-campaign.api'

const CATEGORIES = [
  { key: 'ALL', label: '全部' },
  { key: 'EMERGENCY', label: '紧急' },
  { key: 'ANNOUNCEMENT', label: '公告' },
  { key: 'BUSINESS', label: '业务通知' },
  { key: 'TODO', label: '待办提醒' },
  { key: 'SYSTEM', label: '系统消息' }
]

export default {
  name: 'MessageInboxView',
  components: { ModulePageShell, LoadingState, EmptyState, ErrorState },
  props: {
    ctx: { type: Object, default: null }
  },
  data() {
    return {
      categories: CATEGORIES,
      counts: {},
      items: [],
      total: 0,
      page: 1,
      pageSize: 30,
      detail: null,
      listLoading: false,
      detailLoading: false,
      readingAll: false,
      acting: false,
      fatalError: '',
      narrow: false,
      actionKeyMap: {},
      _readTimer: null
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    scopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    category() {
      return (this.$route.query.category || 'ALL').toUpperCase()
    },
    readState() {
      const s = (this.$route.query.readState || '').toUpperCase()
      return s === 'UNREAD' || s === 'READ' ? s : ''
    },
    selectedId() {
      return this.$route.query.messageId ? String(this.$route.query.messageId) : ''
    },
    subtitle() {
      const u = this.counts.UNREAD || 0
      const a = this.counts.pendingAck || 0
      if (a) return `未读 ${u} · 待确认 ${a}`
      return `未读 ${u}`
    }
  },
  watch: {
    '$route.query': {
      deep: true,
      handler() {
        this.reloadList()
        this.loadDetail()
      }
    }
  },
  mounted() {
    this.onResize()
    window.addEventListener('resize', this.onResize)
    this.bootstrap()
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.onResize)
    if (this._readTimer) clearTimeout(this._readTimer)
  },
  methods: {
    onResize() {
      this.narrow = window.innerWidth < 1100
    },
    async bootstrap() {
      this.fatalError = ''
      try {
        await Promise.all([
          this.reloadCounts(),
          this.reloadList(),
          this.loadDetail(),
          this.loadActionKeys()
        ])
      } catch (e) {
        this.fatalError = (e && e.message) || '加载消息失败'
      }
    },
    async loadActionKeys() {
      try {
        const data = await fetchActionKeys()
        const map = {}
        for (const a of (data && data.items) || []) {
          map[a.actionKey] = a
        }
        this.actionKeyMap = map
      } catch {
        this.actionKeyMap = {}
      }
    },
    async reloadCounts() {
      const data = await fetchMessageCategories()
      this.counts = data || {}
    },
    listParams() {
      const p = { page: this.page, pageSize: this.pageSize }
      if (this.category && this.category !== 'ALL') p.category = this.category
      if (this.readState) p.readStatus = this.readState
      return p
    },
    async reloadList() {
      this.listLoading = true
      this.page = 1
      try {
        const data = await fetchMessages(this.listParams())
        this.items = (data && data.items) || []
        this.total = (data && data.total) || 0
      } finally {
        this.listLoading = false
      }
    },
    async loadMore() {
      this.page += 1
      this.listLoading = true
      try {
        const data = await fetchMessages(this.listParams())
        const more = (data && data.items) || []
        this.items = this.items.concat(more)
        this.total = (data && data.total) || this.total
      } finally {
        this.listLoading = false
      }
    },
    async loadDetail() {
      if (!this.selectedId) {
        this.detail = null
        return
      }
      this.detailLoading = true
      try {
        this.detail = await fetchMessageDetail(this.selectedId)
        // 可视停留后显式已读（不因打开详情立刻已读）
        if (this.detail && this.detail.readStatus === 'UNREAD') {
          if (this._readTimer) clearTimeout(this._readTimer)
          this._readTimer = setTimeout(() => {
            if (this.selectedId === String(this.detail.messageId)) this.onRead(true)
          }, 2500)
        }
      } catch {
        this.detail = null
      } finally {
        this.detailLoading = false
      }
    },
    patchQuery(patch) {
      const q = { ...this.$route.query, ...patch }
      Object.keys(q).forEach((k) => {
        if (q[k] === '' || q[k] == null) delete q[k]
      })
      this.$router.replace({ path: this.$route.path, query: q }).catch(() => {})
    },
    setCategory(key) {
      this.patchQuery({ category: key === 'ALL' ? undefined : key, messageId: undefined })
    },
    setReadState(state) {
      const next = this.readState === state ? undefined : state
      this.patchQuery({ readState: next, messageId: undefined })
    },
    selectMessage(id) {
      this.patchQuery({ messageId: id })
    },
    clearSelection() {
      this.patchQuery({ messageId: undefined })
    },
    async onRead(silent) {
      if (!this.detail) return
      this.acting = true
      try {
        await markMessageRead(this.detail.messageId)
        this.detail = { ...this.detail, readStatus: 'READ', readAt: new Date().toISOString() }
        const row = this.items.find((x) => x.messageId === this.detail.messageId)
        if (row) row.readStatus = 'READ'
        await this.reloadCounts()
      } catch (e) {
        if (!silent) this.fatalError = (e && e.message) || '标记已读失败'
      } finally {
        this.acting = false
      }
    },
    async onAck() {
      if (!this.detail) return
      this.acting = true
      try {
        const r = await ackMessage(this.detail.messageId)
        this.detail = {
          ...this.detail,
          acked: true,
          ackAt: r.ackAt,
          readStatus: 'READ'
        }
        await Promise.all([this.reloadCounts(), this.reloadList()])
      } catch (e) {
        this.fatalError = (e && e.message) || '确认失败'
      } finally {
        this.acting = false
      }
    },
    async onReadAll() {
      this.readingAll = true
      try {
        const params = {}
        if (this.category && this.category !== 'ALL') params.category = this.category
        await markMessagesReadAll(params)
        await Promise.all([this.reloadCounts(), this.reloadList(), this.loadDetail()])
      } catch (e) {
        this.fatalError = (e && e.message) || '全部已读失败'
      } finally {
        this.readingAll = false
      }
    },
    onAction() {
      if (!this.detail || !this.detail.actionKey) return
      const spec = this.actionKeyMap[this.detail.actionKey]
      const path = spec && spec.routes && spec.routes.pc
      if (!path) {
        this.fatalError = '当前端暂无对应办理页，请前往学生端或教师小程序办理'
        return
      }
      const params = this.detail.actionParams || {}
      const q = Object.keys(params).map((k) => `${encodeURIComponent(k)}=${encodeURIComponent(params[k])}`).join('&')
      this.$router.push(q ? `${path}?${q}` : path)
    },
    goSettings() {
      this.$router.push('/admin/messages/settings')
    },
    formatTime(v) {
      if (!v) return ''
      const s = String(v).replace('T', ' ')
      return s.length >= 16 ? s.slice(0, 16) : s
    }
  }
}
</script>

<style scoped>
.mc-inbox {
  display: grid;
  grid-template-columns: 200px minmax(320px, 400px) 1fr;
  gap: 0;
  min-height: 560px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  overflow: hidden;
}
.mc-inbox.is-narrow {
  grid-template-columns: 160px 1fr;
  position: relative;
}
.mc-inbox.is-narrow .mc-inbox__detail {
  position: absolute;
  inset: 0;
  z-index: 2;
  background: var(--bg-card);
}
.mc-inbox__nav {
  border-right: 1px solid var(--border-light);
  padding: var(--space-3) 0;
  background: var(--bg-subtle, var(--bg-page));
}
.mc-nav {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 10px var(--space-4);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  font-size: var(--font-size-sm);
  text-align: left;
}
.mc-nav:hover { background: var(--bg-hover); color: var(--text-primary); }
.mc-nav.is-active {
  background: var(--primary-50, #eef5ff);
  color: var(--primary-700, #1d4ed8);
  font-weight: var(--font-weight-semibold);
}
.mc-nav__count {
  min-width: 20px;
  text-align: right;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}
.mc-nav__sep {
  height: 1px;
  margin: var(--space-2) var(--space-4);
  background: var(--border-light);
}
.mc-inbox__list {
  border-right: 1px solid var(--border-light);
  overflow: auto;
  max-height: calc(100vh - 220px);
}
.mc-list { list-style: none; margin: 0; padding: 0; }
.mc-list__item {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
}
.mc-list__item:hover { background: var(--bg-hover); }
.mc-list__item.is-active { background: var(--primary-25, var(--primary-50)); }
.mc-list__item.is-unread .mc-list__title { font-weight: var(--font-weight-semibold); }
.mc-list__item.is-emergency { box-shadow: inset 3px 0 0 var(--danger-500, #dc2626); }
.mc-list__top { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; min-height: 18px; }
.mc-list__title {
  font-size: var(--font-size-md);
  color: var(--text-primary);
  line-height: 1.4;
}
.mc-list__meta {
  display: flex; justify-content: space-between; gap: var(--space-2);
  margin-top: 4px; font-size: var(--font-size-xs); color: var(--text-tertiary);
}
.mc-list__sum {
  margin-top: 4px;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
}
.mc-list__more { padding: var(--space-3); text-align: center; }
.mc-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--primary-500); margin-left: auto;
}
.mc-tag {
  display: inline-flex; align-items: center;
  padding: 0 6px; height: 18px; border-radius: 4px;
  font-size: 11px; background: var(--bg-muted, #f3f4f6); color: var(--text-secondary);
}
.mc-tag--danger { background: #fef2f2; color: #b91c1c; }
.mc-tag--warn { background: #fffbeb; color: #b45309; }
.mc-inbox__detail { overflow: auto; max-height: calc(100vh - 220px); padding: var(--space-5); }
.mc-drawer-close {
  margin-bottom: var(--space-3);
  border: none; background: none; color: var(--text-link); cursor: pointer;
}
.mc-detail__title {
  margin: var(--space-2) 0;
  font-size: var(--font-size-xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  line-height: 1.35;
}
.mc-detail__meta {
  display: flex; flex-wrap: wrap; gap: var(--space-3);
  font-size: var(--font-size-sm); color: var(--text-tertiary);
}
.mc-detail__alert {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border-radius: var(--radius-sm);
  background: #fff7ed; color: #9a3412;
  font-size: var(--font-size-sm);
}
.mc-detail__body {
  margin-top: var(--space-4);
  max-width: 860px;
  white-space: pre-wrap;
  font-size: var(--font-size-md);
  line-height: 1.7;
  color: var(--text-primary);
}
.mc-detail__foot {
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-light);
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--space-3);
}
.mc-detail__status { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.mc-detail__actions { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.mc-btn {
  height: 32px; padding: 0 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--border-base); background: var(--bg-card);
  color: var(--text-primary); cursor: pointer; font-size: var(--font-size-sm);
}
.mc-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.mc-btn--primary {
  border-color: var(--primary-500, #2563eb);
  background: var(--primary-500, #2563eb); color: #fff;
}
.mc-btn--ghost { background: transparent; }
</style>
