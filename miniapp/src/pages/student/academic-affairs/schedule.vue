<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="我的课表" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="items">
        <button class="sc__print" :disabled="printing" @click="printDoc">{{ printing ? '留痕中…' : '打印课表（留痕）' }}</button>
        <view class="sc__empty" v-if="!items.length"><text>暂无已发布课表</text></view>
        <view v-for="d in grouped" :key="d.day" class="sc__day">
          <text class="sc__day-t">{{ WEEK[d.day] }}</text>
          <view v-for="it in d.list" :key="it.itemId" class="sc__item">
            <view class="sc__slot">第{{ it.slotNo }}节</view>
            <view class="sc__main">
              <text class="sc__course">{{ it.courseName }}</text>
              <text class="sc__meta">{{ it.classroom }} · {{ it.teacherName }} · {{ parity(it) }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { safeToast, toastError } from '@/services/request'
const WEEK = { 1: '周一', 2: '周二', 3: '周三', 4: '周四', 5: '周五', 6: '周六', 7: '周日' }
export default {
  data() { return { items: null, state: 'loading', WEEK, printing: false } },
  onLoad() { this.load() },
  computed: {
    grouped() {
      const m = {}
      ;(this.items || []).forEach((it) => { (m[it.weekday] = m[it.weekday] || []).push(it) })
      return Object.keys(m).sort().map((day) => ({
        day, list: m[day].sort((a, b) => a.slotNo - b.slotNo)
      }))
    }
  },
  methods: {
    parity(it) {
      const p = it.weekParity === 'ODD' ? '单周' : it.weekParity === 'EVEN' ? '双周' : '全周'
      return `${it.startWeek}-${it.endWeek}周·${p}`
    },
    load() {
      this.state = 'loading'
      studentApi.getMySchedule().then((d) => { this.items = d.items || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    printDoc() {
      if (this.printing) return
      this.printing = true
      studentApi.printMySchedule('个人课表').then((res) => {
        const lines = (this.items || []).map((it) =>
          `${WEEK[it.weekday] || it.weekday} 第${it.slotNo}节 ${it.courseName} ${it.classroom || ''}`).join('\n')
        const text = `个人课表\n水印：${(res && res.watermark) || ''}\n留痕：${(res && res.loggedAt) || ''}\n\n${lines || '暂无课表'}`
        uni.setClipboardData({
          data: text,
          success: () => safeToast('已留痕并复制课表摘要', 'success'),
          fail: () => safeToast('已打印留痕', 'success')
        })
      }).catch((e) => toastError(e)).finally(() => { this.printing = false })
    }
  }
}
</script>

<style scoped>
.sc__print { margin-bottom: var(--space-3); background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); font-size: var(--font-size-sm); }
.sc__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.sc__day { margin-bottom: var(--space-4); }
.sc__day-t { display: block; font-weight: 700; color: var(--brand-primary); margin-bottom: var(--space-2); }
.sc__item { display: flex; gap: var(--space-3); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.sc__slot { flex-shrink: 0; width: 56px; text-align: center; font-size: var(--font-size-sm); color: var(--text-secondary); align-self: center; }
.sc__course { display: block; font-weight: 600; }
.sc__meta { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); margin-top: 2px; }
</style>
