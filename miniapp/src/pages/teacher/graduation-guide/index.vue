<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="gg__filters">
          <text class="gg__filter" :class="{ 'is-active': f === 'all' }" @click="f = 'all'">全部 {{ data.list.length }}</text>
          <text class="gg__filter" :class="{ 'is-active': f === 'review' }" @click="f = 'review'">待批阅 {{ reviewCount }}</text>
          <text class="gg__filter" :class="{ 'is-active': f === 'overdue' }" @click="f = 'overdue'">已逾期 {{ overdueCount }}</text>
        </view>

        <view class="stack">
          <view v-for="g in filtered" :key="g.id" class="gg card" @click="openReview(g)">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ g.name }}</text>
                <text class="gg__class">{{ g.className }}</text>
              </view>
              <MobileStatusTag :status="g.status" />
            </view>
            <text class="gg__topic">{{ g.topic }}</text>
            <view class="gg__meta">
              <text class="gg__node">当前节点 · {{ g.node }}</text>
              <text class="gg__deadline" :class="{ 'is-overdue': g.status === 'OVERDUE' }">截止 {{ g.deadline }}</text>
            </view>
            <view v-if="g.status === 'PENDING_REVIEW'" class="gg__actions">
              <button class="btn btn-ghost" @click.stop="toast('查看材料（演示）')">查看材料</button>
              <button class="gg__review" @click.stop="openReview(g)">去批阅</button>
            </view>
            <view v-else-if="g.status === 'OVERDUE'" class="gg__actions">
              <button class="gg__urge" @click.stop="toast('已催交（演示）')">催交学生</button>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <!-- 批阅弹层 -->
    <view v-if="reviewing" class="gg__mask" @click="reviewing = null">
      <view class="gg__sheet" @click.stop>
        <view class="gg__sheet-head">
          <text class="t-lg t-bold">批阅 · {{ reviewing.node }}</text>
          <text class="gg__sheet-close" @click="reviewing = null">×</text>
        </view>
        <text class="gg__sheet-topic">{{ detail.topic }}</text>
        <view class="gg__sheet-block">
          <text class="ir__label">提交时间</text><text class="gg__sheet-text">{{ detail.submitTime }} · 附件 {{ detail.attachment }}</text>
        </view>
        <view class="gg__sheet-block">
          <text class="ir__label">摘要</text><text class="gg__sheet-text">{{ detail.abstract }}</text>
        </view>
        <view class="gg__sheet-block">
          <text class="ir__label">进展</text>
          <text v-for="(p, i) in detail.progress" :key="i" class="gg__sheet-li">· {{ p }}</text>
        </view>
        <view class="gg__sheet-actions">
          <button class="btn btn-ghost flex-1" @click="submitReview('return')">退回整改</button>
          <button class="gg__review flex-1" @click="submitReview('pass')">批阅通过</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'
export default {
  data() { return { data: null, state: 'loading', f: 'all', reviewing: null } },
  onLoad() { this.load() },
  computed: {
    filtered() {
      if (!this.data) return []
      if (this.f === 'review') return this.data.list.filter((g) => g.status === 'PENDING_REVIEW')
      if (this.f === 'overdue') return this.data.list.filter((g) => g.status === 'OVERDUE')
      return this.data.list
    },
    reviewCount() { return this.data ? this.data.list.filter((g) => g.status === 'PENDING_REVIEW').length : 0 },
    overdueCount() { return this.data ? this.data.list.filter((g) => g.status === 'OVERDUE').length : 0 },
    detail() {
      if (!this.reviewing || !this.data) return {}
      return this.data.detail[this.reviewing.id] || { topic: this.reviewing.topic, submitTime: '—', attachment: '—', abstract: '（暂无详细摘要）', progress: [] }
    }
  },
  methods: {
    toast,
    load() {
      this.state = 'loading'
      teacherApi.getGdStudents().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    openReview(g) {
      if (g.status === 'OVERDUE') return toast('学生尚未提交，可催交')
      if (g.status === 'NOT_STARTED') return toast('该节点未开始')
      this.reviewing = g
    },
    submitReview(type) {
      const label = type === 'pass' ? '通过' : '退回整改'
      const g = this.reviewing
      uni.showModal({ title: label, editable: true, placeholderText: '填写指导/退回意见', success: (r) => {
        if (!r.confirm) return
        g.status = type === 'pass' ? 'APPROVED' : 'RETURNED'
        this.reviewing = null
        toast('已' + label + '（演示）')
      } })
    }
  }
}
</script>

<style scoped>
.gg__filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-4); }
.gg__filter { padding: 5px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.gg__filter.is-active { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.gg__class { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.gg__topic { display: block; font-size: var(--font-size-base); color: var(--text-primary); margin: var(--space-2) 0; line-height: 1.4; }
.gg__meta { display: flex; justify-content: space-between; }
.gg__node { font-size: var(--font-size-sm); color: var(--teacher-700); }
.gg__deadline { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gg__deadline.is-overdue { color: var(--danger-600); }
.gg__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.gg__review { min-height: 40px; border-radius: var(--radius-md); border: none; background: var(--teacher-600); color: #fff; font-size: var(--font-size-md); padding: 0 var(--space-4); }
.gg__review::after { border: none; }
.gg__urge { min-height: 40px; border-radius: var(--radius-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); font-size: var(--font-size-md); padding: 0 var(--space-4); }
.gg__urge::after { border: none; }
.gg__mask { position: fixed; inset: 0; background: var(--bg-mask); z-index: var(--z-modal); display: flex; align-items: flex-end; }
.gg__sheet { width: 100%; background: var(--bg-card); border-radius: var(--radius-lg) var(--radius-lg) 0 0; padding: var(--space-5) var(--page-padding-mobile) calc(var(--space-5) + env(safe-area-inset-bottom)); max-height: 80vh; overflow-y: auto; }
.gg__sheet-head { display: flex; align-items: center; justify-content: space-between; }
.gg__sheet-close { font-size: 26px; color: var(--text-tertiary); }
.gg__sheet-topic { display: block; font-size: var(--font-size-base); color: var(--text-primary); margin: var(--space-2) 0 var(--space-3); }
.gg__sheet-block { margin-bottom: var(--space-3); }
.gg__sheet-text { display: block; font-size: var(--font-size-base); color: var(--text-secondary); margin-top: 3px; line-height: 1.5; }
.gg__sheet-li { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.gg__sheet-actions { display: flex; gap: var(--space-2); margin-top: var(--space-4); }
</style>
