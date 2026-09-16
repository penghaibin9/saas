<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="移动待办" :subtitle="scopeText" />
    <MobileGlobalState v-if="state !== 'ready'" :state="state" @retry="refresh" />
      <view v-else>
        <view class="td__filters page-pad">
          <MobileSegmented :items="filtersWithBadge" :model-value="filter" @update:modelValue="selectFilter" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!list.length" state="empty" :title="filter === 'done' ? '暂无已处理事项' : '当前分类暂无待办'" description="可切换其他分类查看，或下拉刷新。" />
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
              :action-disabled="!canHandle(t)"
              :disabled-reason="blockedReason(t)"
              @handle="handle(t)"
              @view="handle(t)"
            />
            <view v-if="pagingError" class="td__paging"><text>更多待办加载失败</text><button class="td__action" @click="loadMore">重试</button></view>
            <view v-else-if="pagerState.hasMore" class="td__paging" @click="loadMore">
              {{ pagerState.loading ? '加载中…' : '继续加载' }}
            </view>
            <view v-else class="td__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    <MobileTeacherTabBar ref="badges" active="workbench" :pending="pendingCount" />
  </view>
</template>

<script>
import { normalizeError } from '@/services/request'
import { useSessionStore } from '@/stores/session'
import { teacherTodoT8Api, TEACHER_TODO_PAGE_SIZE } from '@/services/teacherTodoT8Api'
import { runAction, canNavigate, disabledReasonOf } from '@/services/actionRouter'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { createNetworkPager } from '@/utils/networkPager'
import { deadlineText, isOverdue } from '@/utils/format'

export default {
  data() {
    return {
      filters: [],
      filter: 'all',
      pendingCount: null,
      total: 0,
      scopeText: '',
      state: 'loading',
      epoch: 0,
      pagingError: false,
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
  onShow() {
    this._active = true
    const context = this.contextKey()
    if (this._context !== context) {
      this.filter = 'all'; this.filters = []; this.pendingCount = null; this.total = 0
    }
    this._context = context
    this.scopeText = useSessionStore().dataScopeText
    this.refresh()
    this.$refs?.badges?.refresh()
  },
  onHide() { this._active = false; this.epoch++; this._pager?.reset(); this.$refs?.badges?.invalidate() },
  onReachBottom() { this.loadMore() },
  onUnload() { this._active = false; this.epoch++; this._pager?.reset(); this._pager = null },
  onPullDownRefresh() { this.refresh().finally(() => uni.stopPullDownRefresh()); this.$refs?.badges?.refresh() },
  methods: {
    deadlineText,
    isOverdue,
    displayStatus(status) { return status === 'DONE' ? 'COMPLETED' : status },
    contextKey() {
      const session = useSessionStore(), identity = session.identity || {}, user = session.realUser || {}
      return [currentSessionGeneration(), identity.userId, user.tenantId || identity.tenantId,
        user.activeContextId || user.currentRole?.contextId || identity.activeContextId, session.currentRole].join('|')
    },
    isCurrent(epoch, context) { return this._active && epoch === this.epoch && context === this.contextKey() },
    syncPagerState(value) {
      // The shared pager mutates a plain object, so publish a fresh Vue snapshot.
      this.pagerState = { ...value, items: [...(value.items || [])] }
    },
    selectFilter(next) { if (!next || next === this.filter) return; this.filter = next; return this.refresh() },
    async refresh() {
      if (!this._active) return
      const epoch = ++this.epoch, context = this.contextKey(), group = this.filter
      this._pager?.reset()
      const pager = createNetworkPager(async (cursor, pageSize) => {
        const result = await teacherTodoT8Api.list({ group, cursor, pageSize })
        // Counts and errors need the same stale-response guard as the item list.
        if (this.isCurrent(epoch, context)) {
          this.filters = result?.filters || []
          this.pendingCount = Number(result?.pendingCount || 0)
          this.total = Number(result?.total || 0)
        }
        return { items: result?.items || [], nextCursor: result?.nextCursor || '' }
      }, { pageSize: TEACHER_TODO_PAGE_SIZE, maxItems: 100, idKey: item => item && (item.todoId || item.id) })
      this._pager = pager
      this.state = 'loading'
      this.pagingError = false
      const request = pager.refresh()
      this.syncPagerState(pager.state)
      try {
        const value = await request
        if (!this.isCurrent(epoch, context)) return
        this.syncPagerState(value)
        this.state = 'ready'
      } catch (error) {
        if (this.isCurrent(epoch, context)) this.state = normalizeError(error).pageState || 'error'
      }
    },
    async loadMore() {
      const pager = this._pager, epoch = this.epoch, context = this.contextKey()
      if (!this._active || !pager || pager.state.loading || !pager.state.hasMore || context !== this._context) return
      this.pagingError = false
      const request = pager.loadMore()
      this.syncPagerState(pager.state)
      try {
        await request
      } catch (error) {
        if (this.isCurrent(epoch, context)) this.pagingError = true
      } finally {
        if (this.isCurrent(epoch, context)) this.syncPagerState(pager.state)
      }
    },
    canHandle(todo) { return canNavigate(todo && todo.action, 'teacher') },
    blockedReason(todo) { return disabledReasonOf(todo && todo.action) },
    handle(todo) {
      if (!this.canHandle(todo)) return
      runAction(todo && todo.action, { side: 'teacher' })
    }
  }
}
</script>

<style scoped>
.td__filters { padding-bottom: var(--space-3); }
.td__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.td__paging.is-end { color: var(--text-tertiary); }
.td__action { display: inline-block; margin: 0; padding: 0 16px; min-height: 36px; line-height: 36px; border-radius: 8px; border: 1px solid #1677ff; background: #fff; color: #1677ff; font-size: 14px; }
</style>
