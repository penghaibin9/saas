<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="移动待办" :subtitle="scopeText" />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="td__filters page-pad">
          <MobileSegmented :items="filtersWithBadge" v-model="filter" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!list.length" state="empty" title="暂无待办" description="切换其他分类查看。处理完成的会进入「已处理」。" />
          <view v-else class="stack-sm">
            <MobileTodoCard
              v-for="t in list"
              :key="t.id"
              :title="t.title"
              :source-module="t.module"
              :student-name="t.student"
              :deadline="deadlineText(t.deadline)"
              :status="t.status"
              :overdue="isOverdue(t.deadline) && t.status !== 'COMPLETED'"
              :action-text="t.status === 'COMPLETED' ? '查看' : '去处理'"
              @handle="handle(t)"
              @view="handle(t)"
            >
              <template v-if="t.status !== 'COMPLETED'" #actions>
                <button class="td__btn" @click.stop="quickDone(t)">快速处理</button>
                <button class="td__btn is-primary" @click.stop="handle(t)">去处理</button>
              </template>
            </MobileTodoCard>
            <view v-if="hasMore" class="td__paging" @click="loadMore">
              {{ loadingMore ? '加载中…' : '上拉加载更多' }}
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
import { teacherApi } from '@/services/teacherApi'
import { deadlineText, isOverdue } from '@/utils/format'
import { go } from '@/utils/nav'
const PAGE_SIZE = 20
export default {
  data() {
    return {
      data: { filters: [], list: [] }, state: 'loading', filter: 'all', scopeText: '',
      page: 1, hasMore: false, loadingMore: false
    }
  },
  onLoad() {
    this._pageActive = true
    this.scopeText = useSessionStore().dataScopeText
    this.load({ reset: true })
  },
  onShow() { this._pageActive = true },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onReachBottom() { this.loadMore() },
  watch: {
    filter() { this.load({ reset: true }) }
  },
  computed: {
    list() { return this.data.list || [] },
    pendingCount() { return Number(this.data.pendingCount) || 0 },
    filtersWithBadge() {
      return (this.data.filters || []).map((item) => ({
        ...item,
        badge: Number(item.badge) || 0
      }))
    }
  },
  methods: {
    deadlineText, isOverdue,
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true } = {}) {
      if (this._todosPromise) return this._todosPromise
      const requestedFilter = this.filter
      const requestedPage = reset ? 1 : this.page + 1
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = teacherApi.getTodosPage(requestedFilter, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.filter !== requestedFilter) return result
          this.data = {
            ...result,
            list: reset ? (result.list || []) : [...this.list, ...(result.list || [])]
          }
          this.page = Number(result.page) || requestedPage
          this.hasMore = !!result.hasMore
          this.state = 'ready'
          return result
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._todosPromise === pending) this._todosPromise = null
          this.loadingMore = false
        })
      this._todosPromise = pending
      return pending
    },
    handle(todo) {
      const map = {
        review: todo.module.includes('毕业') ? '/pages/teacher/graduation-guide/index?tab=review' : '/pages/teacher/internship-review/index',
        approve: '/pages/teacher/approval/index',
        risk: '/pages/teacher/risk-students/index',
        contact: '/pages/teacher/risk-students/index',
        confirm: '/pages/teacher/internship-review/index'
      }
      go(map[todo.group] || '/pages/teacher/approval/index')
    },
    quickDone(todo) { this.handle(todo) }
  }
}
</script>

<style scoped>
.td__filters { padding-bottom: var(--space-3); }
.td__btn { min-height: 34px; line-height: 34px; padding: 0 var(--space-3); border-radius: var(--radius-md); font-size: var(--font-size-sm); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); }
.td__btn.is-primary { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.td__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.td__paging.is-end { color: var(--text-tertiary); }
</style>
