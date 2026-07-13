<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="移动待办" :subtitle="scopeText" />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="td__filters page-pad">
          <MobileSegmented :items="filtersWithBadge" v-model="filter" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!filtered.length" state="empty" title="暂无待办" description="切换其他分类查看。处理完成的会进入「已处理」。" />
          <view v-else class="stack-sm">
            <MobileTodoCard
              v-for="t in pagedSlice(filtered)"
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
            <view v-if="pagedFooter(filtered) === 'more'" class="td__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(filtered) === 'end'" class="td__paging is-end">没有更多了</view>
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
import { listPaging } from '@/utils/listPaging'
import { go, toast } from '@/utils/nav'
export default {
  mixins: [listPaging(20)],
  data() { return { data: null, state: 'loading', filter: 'all', scopeText: '' } },
  onLoad() {
    this.scopeText = useSessionStore().dataScopeText
    this.load()
  },
  // onReachBottom 必须写在页面本身，mp-weixin 才会注册（mixin 里的会被编译器忽略）
  onReachBottom() { this.pagedReachBottom() },
  watch: {
    // 切换分类回到第一批，避免上一分类的展开条数影响新分类
    filter() { this.pagedReset() }
  },
  computed: {
    filtered() {
      if (!this.data) return []
      return this.filter === 'all' ? this.data.list : this.data.list.filter((t) => {
        if (this.filter === 'soon') return t.soon && t.status !== 'COMPLETED'
        return t.group === this.filter
      })
    },
    pendingCount() {
      return this.data ? this.data.list.filter((t) => t.status !== 'COMPLETED').length : 0
    },
    filtersWithBadge() {
      if (!this.data) return []
      return this.data.filters.map((f) => {
        let n = 0
        if (f.key === 'all') n = this.data.list.filter((t) => t.status !== 'COMPLETED').length
        else if (f.key === 'soon') n = this.data.list.filter((t) => t.soon && t.status !== 'COMPLETED').length
        else if (f.key !== 'done') n = this.data.list.filter((t) => t.group === f.key && t.status !== 'COMPLETED').length
        return { ...f, badge: n }
      })
    }
  },
  methods: {
    deadlineText, isOverdue,
    // 供 listPaging 判断是否还有更多（仅在确有更多时才增长 pagerShown）
    pagingList() { return this.filtered },
    load() {
      this.state = 'loading'
      this.pagedReset()
      teacherApi.getTodos().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    handle(t) {
      const map = {
        review: t.module.includes('毕业') ? '/pages/teacher/graduation-guide/index' : '/pages/teacher/internship-review/index',
        approve: '/pages/teacher/approval/index',
        risk: '/pages/teacher/risk-students/index',
        contact: '/pages/teacher/risk-students/index',
        confirm: '/pages/teacher/internship-review/index'
      }
      go(map[t.group] || '/pages/teacher/approval/index')
    },
    quickDone(t) {
      // 待办来自各业务模块聚合，必须进入对应模块真实处理，不做本地假完成
      this.handle(t)
    }
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
