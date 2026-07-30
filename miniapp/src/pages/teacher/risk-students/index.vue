<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <!-- 风险概览 -->
        <view class="rk__summary card">
          <view class="rk__sum-item"><text class="rk__sum-val is-high">{{ counts.HIGH }}</text><text class="rk__sum-label">高风险</text></view>
          <view class="rk__sum-item"><text class="rk__sum-val is-mid">{{ counts.MEDIUM }}</text><text class="rk__sum-label">中风险</text></view>
          <view class="rk__sum-item"><text class="rk__sum-val">{{ total }}</text><text class="rk__sum-label">需关注</text></view>
        </view>

        <view class="rk__filters">
          <text class="rk__filter" :class="{ 'is-active': level === 'all' }" @click="level = 'all'">全部</text>
          <text class="rk__filter" :class="{ 'is-active': level === 'HIGH' }" @click="level = 'HIGH'">高风险</text>
          <text class="rk__filter" :class="{ 'is-active': level === 'MEDIUM' }" @click="level = 'MEDIUM'">中风险</text>
        </view>

        <view class="stack-sm">
          <MobileStudentCard
            v-for="s in list"
            :key="s.id"
            :name="s.name"
            :class-name="s.className"
            :major="s.major"
            :stage="s.stage"
            :current-task="s.task"
            :risk-level="s.risk"
            :pending-count="s.pending"
            :last-activity="s.last"
            @view="openStudent(s)"
          >
            <template #actions>
              <text class="rk__btn" @click.stop="contact(s)">联系</text>
              <text class="rk__btn is-primary" @click.stop="openStudent(s)">处理</text>
            </template>
          </MobileStudentCard>
          <view v-if="hasMore" class="rk__paging" @click="loadMore">
            {{ loadingMore ? '加载中…' : '上拉加载更多' }}
          </view>
          <view v-else class="rk__paging is-end">没有更多了</view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { go } from '@/utils/nav'
const PAGE_SIZE = 20
export default {
  data() {
    return {
      list: [], state: 'loading', level: 'all', page: 1, hasMore: false,
      loadingMore: false, total: 0, counts: { HIGH: 0, MEDIUM: 0 }
    }
  },
  onLoad() { this._pageActive = true; this.load({ reset: true }) },
  onShow() { this._pageActive = true },
  onHide() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onUnload() { this._pageActive = false; this._loadEpoch = (this._loadEpoch || 0) + 1 },
  onReachBottom() { this.loadMore() },
  watch: {
    level() { this.load({ reset: true }) }
  },
  onPullDownRefresh() {
    this.load({ reset: true, done: () => uni.stopPullDownRefresh() })
  },
  methods: {
    loadMore() {
      if (!this.hasMore || this.loadingMore) return
      this.load({ reset: false })
    },
    load({ reset = true, done = null } = {}) {
      if (this._riskPromise) return this._riskPromise.finally(() => { if (done) done() })
      const requestedLevel = this.level
      const requestedPage = reset ? 1 : this.page + 1
      const epoch = (this._loadEpoch || 0) + 1
      this._loadEpoch = epoch
      if (reset) this.state = 'loading'
      else this.loadingMore = true
      const pending = teacherApi.getRiskStudentsPage(requestedLevel, requestedPage, PAGE_SIZE)
        .then((result) => {
          if (!this._pageActive || this._loadEpoch !== epoch || this.level !== requestedLevel) return result
          this.list = reset ? (result.list || []) : [...this.list, ...(result.list || [])]
          this.page = Number(result.page) || requestedPage
          this.hasMore = !!result.hasMore
          this.total = Number(result.total) || 0
          this.counts = result.counts || { HIGH: 0, MEDIUM: 0 }
          this.state = 'ready'
          return result
        })
        .catch((error) => {
          if (this._pageActive && this._loadEpoch === epoch && reset) this.state = 'error'
          throw error
        })
        .finally(() => {
          if (this._riskPromise === pending) this._riskPromise = null
          this.loadingMore = false
          if (done) done()
        })
      this._riskPromise = pending
      return pending
    },
    openStudent(student) { go('/pages/teacher/student-detail/index?id=' + student.id) },
    contact(student) { this.openStudent(student) }
  }
}
</script>

<style scoped>
.rk__summary { display: flex; margin-bottom: var(--space-4); }
.rk__sum-item { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; }
.rk__sum-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.rk__sum-val.is-high { color: var(--danger-600); }
.rk__sum-val.is-mid { color: var(--warning-600); }
.rk__sum-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.rk__filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-4); }
.rk__filter { padding: 5px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.rk__filter.is-active { background: var(--teacher-600); color: #fff; border-color: var(--teacher-600); }
.rk__btn { font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 5px 12px; }
.rk__btn.is-primary { color: #fff; background: var(--teacher-600); border-color: var(--teacher-600); }
.rk__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.rk__paging.is-end { color: var(--text-tertiary); }
</style>
