<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="移动待办" :subtitle="scopeText" />
    <MobileGlobalState :state="state" @retry="refresh">
      <view>
        <view class="td__filters page-pad">
          <MobileSegmented :items="filtersWithBadge" v-model="filter" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!list.length" state="empty" title="暂无待办" description="切换其他分类查看。处理完成的会进入「已处理」。" />
          <view v-else class="stack-sm">
            <MobileTodoCard
              v-for="t in list"
              :key="t.todoId || t.id"
              :title="t.title"
              :source-module="t.sourceModule || ''"
              :student-name="''"
              :deadline="deadlineText(t.dueAt || t.deadline)"
              :status="displayStatus(t.status)"
              :overdue="isOverdue(t.dueAt || t.deadline) && t.status !== 'DONE'"
              :action-text="t.status === 'DONE' ? '查看' : '去处理'"
              @handle="handle(t)"
              @view="handle(t)"
            />
            <view v-if="pagerState.hasMore" class="td__paging" @click="loadMore">
              {{ pagerState.loading ? '加载中…' : '继续加载' }}
            </view>
            <view v-else class="td__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="teacher" active="todo" :badges="{ todo: pendingCount }" />
  </view>
</template>

<script>
import { useSessionStore } from '@/stores/session'
import { teacherTodoT8Api, TEACHER_TODO_PAGE_SIZE } from '@/services/teacherTodoT8Api'
import { runAction } from '@/services/actionRouter'
import { createNetworkPager } from '@/utils/networkPager'
import { deadlineText, isOverdue } from '@/utils/format'

export default {
  data() {
    return {
      filters: [],
      filter: 'all',
      pendingCount: 0,
      total: 0,
      scopeText: '',
      state: 'loading',
      pagerState: {
        items: [], cursor: '', hasMore: false, loading: false,
        refreshing: false, requestEpoch: 0, error: null
      }
    }
  },
  computed: {
    list() { return this.pagerState.items || [] },
    filtersWithBadge() {
      return (this.filters || []).map((item) => ({ ...item, badge: Number(item.badge) || 0 }))
    }
  },
  watch: {
    filter() { this.refresh() }
  },
  onLoad() {
    this.scopeText = useSessionStore().dataScopeText
    this._pager = createNetworkPager(async (cursor, pageSize) => {
      const result = await teacherTodoT8Api.list({ group: this.filter, cursor, pageSize })
      this.filters = (result && result.filters) || []
      this.pendingCount = Number((result && result.pendingCount) || 0)
      this.total = Number((result && result.total) || 0)
      return {
        items: (result && result.items) || [],
        nextCursor: (result && result.nextCursor) || ''
      }
    }, {
      pageSize: TEACHER_TODO_PAGE_SIZE,
      maxItems: 100,
      idKey: (item) => item && (item.todoId || item.id)
    })
    this.pagerState = this._pager.state
    this.refresh()
  },
  onReachBottom() { this.loadMore() },
  onUnload() { if (this._pager) this._pager.reset() },
  methods: {
    deadlineText,
    isOverdue,
    displayStatus(status) { return status === 'DONE' ? 'COMPLETED' : status },
    async refresh() {
      if (!this._pager) return
      this.state = 'loading'
      try {
        await this._pager.refresh()
        this.state = 'ready'
      } catch (error) {
        this.state = 'error'
      }
    },
    async loadMore() {
      if (!this._pager || this.pagerState.loading || !this.pagerState.hasMore) return
      try {
        await this._pager.loadMore()
      } catch (error) {
        // Keep already loaded rows visible; shared pager retains the error for retry/telemetry.
      }
    },
    handle(todo) {
      runAction(todo && todo.action, { side: 'teacher' })
    }
  }
}
</script>

<style scoped>
.td__filters { padding-bottom: var(--space-3); }
.td__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.td__paging.is-end { color: var(--text-tertiary); }
</style>
