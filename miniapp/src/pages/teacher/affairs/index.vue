<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学工待办" subtitle="本校学工事务待处理" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="ta__total">
          <text class="ta__total-n">{{ data.total }}</text>
          <text class="ta__total-l">项学工待办</text>
        </view>
        <view class="ta__empty" v-if="!data.cards.length"><text>暂无待办</text></view>
        <view class="stack">
          <view v-for="c in data.cards" :key="c.todoType" class="ta__card">
            <text class="ta__label">{{ c.label }}</text>
            <text class="ta__count">{{ c.count }}</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
export default {
  data() { return { data: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      teacherApi.getAffairs().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.ta__total { background: var(--brand-primary); color: #fff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); display: flex; align-items: baseline; gap: var(--space-2); }
.ta__total-n { font-size: 28px; font-weight: 700; }
.ta__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.ta__card { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.ta__label { font-weight: 600; color: var(--text-primary); }
.ta__count { font-size: 20px; font-weight: 700; color: var(--brand-primary); }
</style>
