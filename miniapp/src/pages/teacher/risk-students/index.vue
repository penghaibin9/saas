<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="list">
        <!-- 风险概览 -->
        <view class="rk__summary card">
          <view class="rk__sum-item"><text class="rk__sum-val is-high">{{ counts.HIGH }}</text><text class="rk__sum-label">高风险</text></view>
          <view class="rk__sum-item"><text class="rk__sum-val is-mid">{{ counts.MEDIUM }}</text><text class="rk__sum-label">中风险</text></view>
          <view class="rk__sum-item"><text class="rk__sum-val">{{ list.length }}</text><text class="rk__sum-label">需关注</text></view>
        </view>

        <view class="rk__filters">
          <text class="rk__filter" :class="{ 'is-active': level === 'all' }" @click="level = 'all'">全部</text>
          <text class="rk__filter" :class="{ 'is-active': level === 'HIGH' }" @click="level = 'HIGH'">高风险</text>
          <text class="rk__filter" :class="{ 'is-active': level === 'MEDIUM' }" @click="level = 'MEDIUM'">中风险</text>
        </view>

        <view class="stack-sm">
          <MobileStudentCard
            v-for="s in pagedSlice(filtered)"
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
          <view v-if="pagedFooter(filtered) === 'more'" class="rk__paging" @click="pagedLoadMore">上拉加载更多</view>
          <view v-else-if="pagedFooter(filtered) === 'end'" class="rk__paging is-end">没有更多了</view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { listPaging } from '@/utils/listPaging'
import { go, toast } from '@/utils/nav'
export default {
  mixins: [listPaging(20)],
  data() { return { list: null, state: 'loading', level: 'all' } },
  onLoad() { this.load() },
  // onReachBottom 必须写在页面本身，mp-weixin 才会注册
  onReachBottom() { this.pagedReachBottom() },
  watch: {
    level() { this.pagedReset() }
  },
  computed: {
    filtered() {
      if (!this.list) return []
      return this.level === 'all' ? this.list : this.list.filter((s) => s.risk === this.level)
    },
    counts() {
      const c = { HIGH: 0, MEDIUM: 0 }
      ;(this.list || []).forEach((s) => { if (c[s.risk] !== undefined) c[s.risk]++ })
      return c
    }
  },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    pagingList() { return this.filtered },
    load(done) {
      this.state = 'loading'
      this.pagedReset()
      teacherApi.getRiskStudents().then((d) => { this.list = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    openStudent(s) { go('/pages/teacher/student-detail/index?id=' + s.id) },
    // 学生联系方式属敏感信息：不在列表明文提供，进入学生详情查看脱敏联系方式
    contact(s) { this.openStudent(s) }
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
