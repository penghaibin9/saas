<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="搜索" show-back />
    <view class="se__bar">
      <text class="se__icon">🔍</text>
      <input
        class="se__input"
        v-model="keyword"
        :placeholder="provider.placeholder"
        placeholder-class="se__ph"
        confirm-type="search"
        focus
        @input="onInput"
      />
      <text v-if="keyword" class="se__clear" @click="clear">✕</text>
    </view>

    <view class="page-pad">
      <template v-if="keyword.trim().length < minLength">
        <text class="t-sm t-tertiary">输入至少 {{ minLength }} 个字符开始搜索</text>
      </template>
      <template v-else-if="searching">
        <MobileGlobalState state="loading" title="搜索中" />
      </template>
      <template v-else-if="failed">
        <MobileGlobalState state="error" title="搜索失败" description="请检查网络后重试。" @retry="runSearch" />
      </template>
      <template v-else>
        <text class="t-sm t-tertiary">找到 {{ items.length }} 条结果{{ note ? ' · ' + note : '' }}</text>
        <view class="list-group" v-if="items.length" style="margin-top: var(--space-3);">
          <view v-for="row in items" :key="row.id" class="list-row" @click="open(row)">
            <view class="flex-1">
              <text class="t-md">{{ row.title }}</text>
              <text class="se__sub">{{ row.summary }} · {{ formatTime(row.time) }}</text>
            </view>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="没有找到相关内容" description="换个关键词试试。" />
      </template>
    </view>
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { MIN_KEYWORD_LENGTH, resolveSearchProvider } from '@/services/searchProviders'
import { canNavigate, runAction } from '@/services/actionRouter'
import { stashDetail } from '@/utils/msgStash'
import { go } from '@/utils/nav'

const DEBOUNCE_MS = 300

// V3 §9.4 Shared Search Shell：本页只负责输入、防抖、epoch 失效与结果框架，
// 不绑定任何一端的 API——搜什么由 side-aware provider 决定（V3 深审 P0-10）。
export default {
  data() {
    return {
      keyword: '', items: [], note: '', searching: false, failed: false,
      side: 'student', minLength: MIN_KEYWORD_LENGTH
    }
  },
  computed: {
    provider() { return resolveSearchProvider(this.side) }
  },
  onLoad() {
    this.side = useSessionStore().side === 'teacher' ? 'teacher' : 'student'
  },
  onUnload() {
    if (this._timer) clearTimeout(this._timer)
    this._timer = null
  },
  methods: {
    formatTime(t) { return t ? String(t).slice(0, 10) : '' },
    clear() {
      this.keyword = ''
      this.items = []
      this.note = ''
      this.failed = false
      // 输入清空后作废在途请求，避免旧结果稍后覆盖空态。
      this._epoch = (this._epoch || 0) + 1
    },
    onInput() {
      if (this._timer) clearTimeout(this._timer)
      this.failed = false
      if (this.keyword.trim().length < this.minLength) {
        this.items = []
        this.note = ''
        this._epoch = (this._epoch || 0) + 1
        return
      }
      this._timer = setTimeout(() => this.runSearch(), DEBOUNCE_MS)
    },
    runSearch() {
      const value = this.keyword.trim()
      if (value.length < this.minLength) return
      const epoch = (this._epoch || 0) + 1
      this._epoch = epoch
      this.searching = true
      this.failed = false
      this.provider.search(value)
        .then((result) => {
          // 快速输入会产生乱序响应：只接受最后一次请求的结果。
          if (this._epoch !== epoch) return
          this.items = (result && result.items) || []
          this.note = (result && result.note) || ''
        })
        .catch(() => { if (this._epoch === epoch) this.failed = true })
        .finally(() => { if (this._epoch === epoch) this.searching = false })
    },
    open(row) {
      if (row.action && canNavigate(row.action, this.side)) {
        runAction(row.action, { side: this.side })
        return
      }
      // 无 typed action 的历史/本地条目：只允许回消息详情，不猜业务落点。
      if (row.stashed) {
        stashDetail(row.stashed)
        go('/pages/common/message-detail/index')
      }
    }
  }
}
</script>

<style scoped>
.se__bar { display: flex; align-items: center; gap: var(--space-2); background: var(--bg-card); padding: var(--space-3) var(--page-padding-mobile); border-bottom: 1px solid var(--border-light); }
.se__icon { font-size: var(--font-size-base); color: var(--text-tertiary); }
.se__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); }
.se__ph { color: var(--text-tertiary); }
.se__clear { font-size: var(--font-size-sm); color: var(--text-tertiary); padding: 4px; }
.se__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
</style>
