<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的成绩" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="tr__sum">
          <view class="tr__stat"><text class="tr__num">{{ data.earnedCredits || 0 }}</text><text class="tr__lbl">已修学分</text></view>
          <view class="tr__stat"><text class="tr__num">{{ data.items.length }}</text><text class="tr__lbl">课程数</text></view>
          <view class="tr__stat"><text class="tr__num" :class="{ 'is-bad': data.failCount }">{{ data.failCount || 0 }}</text><text class="tr__lbl">挂科</text></view>
        </view>
        <view class="tr__empty" v-if="!data.items.length"><text>暂无成绩</text></view>
        <view class="stack">
          <view v-for="(g, i) in data.items" :key="i" class="tr__row">
            <view class="tr__main">
              <text class="tr__course">{{ g.courseName }}</text>
              <text class="tr__term">{{ g.term }} · {{ g.credit }}学分</text>
            </view>
            <text class="tr__score" :class="g.passStatus === 'FAIL' ? 'is-bad' : 'is-ok'">{{ g.score }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
export default {
  data() { return { data: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyTranscript().then((d) => { this.data = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.tr__sum { display: flex; gap: var(--space-2); margin-bottom: var(--space-4); }
.tr__stat { flex: 1; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) 0; text-align: center; box-shadow: var(--shadow-card); }
.tr__num { display: block; font-size: 22px; font-weight: 700; color: var(--brand-primary); }
.tr__num.is-bad { color: #dc2626; }
.tr__lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.tr__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.tr__row { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.tr__course { display: block; font-weight: 600; }
.tr__term { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
.tr__score { font-size: 20px; font-weight: 700; }
.tr__score.is-ok { color: #16a34a; }
.tr__score.is-bad { color: #dc2626; }
</style>
