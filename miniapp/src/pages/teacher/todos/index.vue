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
              v-for="t in filtered"
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
import { go, toast } from '@/utils/nav'
export default {
  data() { return { data: null, state: 'loading', filter: 'all', scopeText: '' } },
  onLoad() {
    this.scopeText = useSessionStore().dataScopeText
    this.load()
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
    load() {
      this.state = 'loading'
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
      uni.showModal({ title: '快速处理', content: '确认将「' + t.title + '」标记为已处理？', success: (r) => {
        if (r.confirm) { t.status = 'COMPLETED'; t.group = 'done'; t.soon = false; toast('已处理（演示）') }
      } })
    }
  }
}
</script>

<style scoped>
.td__filters { padding-bottom: var(--space-3); }
.td__btn { min-height: 34px; line-height: 34px; padding: 0 var(--space-3); border-radius: var(--radius-md); font-size: var(--font-size-sm); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); }
.td__btn.is-primary { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
</style>
