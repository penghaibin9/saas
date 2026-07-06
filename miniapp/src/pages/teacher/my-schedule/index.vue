<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的课表" subtitle="本学期授课安排" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
        <view class="ts__empty" v-if="!items.length"><text>暂无已发布课表</text></view>
        <view v-for="d in grouped" :key="d.day" class="ts__day">
          <text class="ts__day-t">{{ WEEK[d.day] }}</text>
          <view v-for="it in d.list" :key="it.itemId" class="ts__item">
            <view class="ts__slot">第{{ it.slotNo }}节</view>
            <view class="ts__main">
              <text class="ts__course">{{ it.courseName }}</text>
              <text class="ts__meta">{{ it.className }} · {{ it.classroom }} · {{ parity(it) }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="teacher" active="home" />
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
const WEEK = { 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' }
export default {
  data() { return { items: null, state: 'loading', WEEK } },
  onLoad() { this.load() },
  computed: {
    grouped() {
      const m = {}
      ;(this.items || []).forEach((it) => { (m[it.weekday] = m[it.weekday] || []).push(it) })
      return Object.keys(m).sort().map((day) => ({ day, list: m[day].sort((a, b) => a.slotNo - b.slotNo) }))
    }
  },
  methods: {
    parity(it) {
      const p = it.weekParity === 'ODD' ? '单周' : it.weekParity === 'EVEN' ? '双周' : '全周'
      return `${it.startWeek}-${it.endWeek}周·${p}`
    },
    load() {
      this.state = 'loading'
      teacherApi.getMySchedule().then((d) => { this.items = d.items || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.ts__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.ts__day { margin-bottom: var(--space-4); }
.ts__day-t { display: block; font-weight: 700; color: var(--brand-primary); margin-bottom: var(--space-2); }
.ts__item { display: flex; gap: var(--space-3); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.ts__slot { flex-shrink: 0; width: 56px; text-align: center; font-size: var(--font-size-sm); color: var(--text-secondary); align-self: center; }
.ts__course { display: block; font-weight: 600; }
.ts__meta { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
</style>
