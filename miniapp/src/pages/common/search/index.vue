<template>
  <view class="page-wrap">
    <MobileNavBar variant="default" title="搜索" show-back />
    <view class="se__bar">
      <text class="se__icon">🔍</text>
      <input
        class="se__input"
        v-model="keyword"
        placeholder="搜索通知、消息标题"
        placeholder-class="se__ph"
        confirm-type="search"
        focus
      />
      <text v-if="keyword" class="se__clear" @click="keyword = ''">✕</text>
    </view>

    <view class="page-pad">
      <template v-if="!keyword.trim()">
        <text class="t-sm t-tertiary">输入关键词搜索本人消息与通知</text>
      </template>
      <template v-else>
        <text class="t-sm t-tertiary">找到 {{ result.length }} 条结果</text>
        <view class="list-group" v-if="result.length" style="margin-top: var(--space-3);">
          <view v-for="m in result" :key="m.id" class="list-row" @click="open(m)">
            <view class="flex-1">
              <text class="t-md">{{ m.title }}</text>
              <text class="se__sub">{{ m.module || '消息' }} · {{ formatTime(m.time) }}</text>
            </view>
          </view>
        </view>
        <MobileGlobalState v-else state="empty" title="没有找到相关消息" description="换个关键词试试。" />
      </template>
    </view>
  </view>
</template>

<script>
import { getSearchPool, stashDetail } from '@/utils/msgStash'
import { go } from '@/utils/nav'

export default {
  data() { return { keyword: '', pool: [] } },
  onLoad() { this.pool = getSearchPool() },
  computed: {
    result() {
      const kw = this.keyword.trim().toLowerCase()
      if (!kw) return []
      return this.pool.filter((m) => ((m.title || '') + (m.module || '')).toLowerCase().includes(kw))
    }
  },
  methods: {
    formatTime(t) { return t ? String(t).slice(0, 10) : '' },
    open(m) {
      stashDetail(m)
      go('/pages/common/message-detail/index')
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
