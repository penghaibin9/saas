<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学工统计" subtitle="谈心谈话工作量 · 心理关注聚合" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="talk || mental">
        <!-- 谈话工作量 -->
        <view class="section-head"><text class="section-head__title">谈心谈话工作量</text></view>
        <view class="card st__row3">
          <view class="st__stat"><text class="st__val">{{ talk ? talk.total : 0 }}</text><text class="st__label">谈话总数</text></view>
          <view class="st__stat"><text class="st__val">{{ talk ? talk.completed : 0 }}</text><text class="st__label">已完成</text></view>
          <view class="st__stat"><text class="st__val">{{ ratePct }}<text class="st__unit">%</text></text><text class="st__label">完成率</text></view>
        </view>
        <view class="card" v-if="talk && talk.breakdown && talk.breakdown.length">
          <view class="list-row" v-for="b in talk.breakdown" :key="b.key">
            <text class="flex-1 t-sm">{{ talkTypeLabel(b.key) }}</text>
            <text class="st__bk">{{ b.completed }}/{{ b.total }}</text>
          </view>
        </view>

        <!-- 心理关注 -->
        <view class="section-head"><text class="section-head__title">心理关注聚合</text></view>
        <view class="card st__row3">
          <view class="st__stat"><text class="st__val">{{ mental ? mental.total : 0 }}</text><text class="st__label">转介总数</text></view>
          <view class="st__stat"><text class="st__val st__danger">{{ mental ? mental.openCrisis : 0 }}</text><text class="st__label">在册危机</text></view>
          <view class="st__stat"><text class="st__val">{{ closedCount }}</text><text class="st__label">已结案</text></view>
        </view>
        <view class="card" v-if="mentalLevelRows.length">
          <text class="st__cap">按等级</text>
          <view class="list-row" v-for="r in mentalLevelRows" :key="r.key">
            <text class="flex-1 t-sm">{{ mentalLevelLabel(r.key) }}</text>
            <text class="st__bk">{{ r.value }}</text>
          </view>
        </view>
        <text class="st__note">仅聚合计数，不含任何学生个人敏感信息与明细。</text>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'

const TALK_TYPE = { LIFE: '生活关怀', STUDY: '学业', PSYCHOLOGY: '心理', CAREER: '就业', DISCIPLINE: '违纪', OTHER: '其他' }
const MENTAL_LEVEL = { CRISIS: '危机', HIGH: '高关注', MEDIUM: '中关注', LOW: '一般', NORMAL: '一般' }

export default {
  data() { return { talk: null, mental: null, state: 'loading' } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    ratePct() { return this.talk ? Math.round((this.talk.completionRate || 0) * 100) : 0 },
    closedCount() {
      const s = this.mental && this.mental.byStatus
      return s ? (s.CLOSED || 0) : 0
    },
    mentalLevelRows() {
      const m = this.mental && this.mental.byLevel
      return m ? Object.keys(m).map((k) => ({ key: k, value: m[k] })) : []
    }
  },
  methods: {
    talkTypeLabel(k) { return TALK_TYPE[k] || (k || '未分类') },
    mentalLevelLabel(k) { return MENTAL_LEVEL[k] || k },
    load(done) {
      this.state = 'loading'
      Promise.all([
        teacherApi.getTalkStats().catch(() => null),
        teacherApi.getMentalStats().catch(() => null)
      ]).then(([talk, mental]) => {
        this.talk = talk; this.mental = mental
        this.state = (talk || mental) ? 'ready' : 'error'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    }
  }
}
</script>

<style scoped>
.st__row3 { display: flex; }
.st__stat { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.st__val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--teacher-700); }
.st__val.st__danger { color: var(--danger-600); }
.st__unit { font-size: var(--font-size-xs); margin-left: 2px; }
.st__label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.st__bk { font-size: var(--font-size-sm); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.st__cap { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-bottom: var(--space-1); }
.st__note { font-size: var(--font-size-xs); color: var(--text-tertiary); text-align: center; padding: var(--space-2); }
</style>
