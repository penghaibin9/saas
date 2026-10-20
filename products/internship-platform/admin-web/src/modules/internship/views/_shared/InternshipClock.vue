<template>
  <div class="bpl-clock">
    <button
      type="button"
      class="ix-clock-trigger"
      popovertarget="internship-date-popover"
      aria-label="打开日期与时间"
    >
      <time :datetime="now.toISOString()">{{ dateLabel }}</time>
    </button>
    <div
      id="internship-date-popover"
      popover
      class="ix-calendar"
      role="dialog"
      aria-label="日期与时间"
    >
      <header>
        <strong>日期与时间</strong
        ><button
          type="button"
          popovertarget="internship-date-popover"
          popovertargetaction="hide"
          aria-label="关闭日期与时间"
        >
          ×
        </button>
      </header>
      <p>
        {{
          now.toLocaleDateString('zh-CN', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'long'
          })
        }}
      </p>
      <time class="ix-calendar-time" :datetime="now.toISOString()">{{
        now.toLocaleTimeString('zh-CN', { hour12: false })
      }}</time>
      <small>本地时间</small>
      <nav aria-label="切换日历月份">
        <strong>{{ monthLabel }}</strong
        ><button type="button" aria-label="上个月" @click="moveMonth(-1)">‹</button
        ><button type="button" @click="month = new Date(now.getFullYear(), now.getMonth(), 1)">
          今天</button
        ><button type="button" aria-label="下个月" @click="moveMonth(1)">›</button>
      </nav>
      <div class="ix-calendar-grid">
        <span
          v-for="day in ['一', '二', '三', '四', '五', '六', '日']"
          :key="day"
          class="ix-calendar-week"
          >{{ day }}</span
        >
        <time
          v-for="day in days"
          :key="day.key"
          :datetime="day.key"
          :aria-current="day.today ? 'date' : undefined"
          :class="{ 'is-muted': day.outside, 'is-today': day.today }"
          >{{ day.number }}</time
        >
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onUnmounted, ref } from 'vue'
const now = ref(new Date())
const month = ref(new Date(now.value.getFullYear(), now.value.getMonth(), 1))
const timer = setInterval(() => {
  now.value = new Date()
}, 1000)
onUnmounted(() => clearInterval(timer))
const dateLabel = computed(() =>
  now.value.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
)
const monthLabel = computed(() =>
  month.value.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' })
)
const days = computed(() => {
  const offset = (month.value.getDay() + 6) % 7
  return Array.from({ length: 42 }, (_, index) => {
    const date = new Date(month.value.getFullYear(), month.value.getMonth(), 1 - offset + index)
    return {
      key: [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, '0'),
        String(date.getDate()).padStart(2, '0')
      ].join('-'),
      number: date.getDate(),
      outside: date.getMonth() !== month.value.getMonth(),
      today: date.toDateString() === now.value.toDateString()
    }
  })
})
function moveMonth(offset) {
  month.value = new Date(month.value.getFullYear(), month.value.getMonth() + offset, 1)
}
</script>

<style scoped>
.ix-clock-trigger {
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  padding: 8px 4px;
}
.ix-calendar {
  inset: 76px 22px auto auto;
  margin: 0;
  width: 310px;
  max-width: calc(100vw - 24px);
  padding: 20px;
  border: 1px solid var(--card-b, #e5e7eb);
  border-radius: 12px;
  box-shadow: 0 12px 40px #18345925;
  background: var(--card, #fff);
  color: var(--t1, #24334b);
  font: 13px/1.6 var(--font-family-base, sans-serif);
}
.ix-calendar header,
.ix-calendar nav {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ix-calendar header > strong,
.ix-calendar nav > strong {
  flex: 1;
}
.ix-calendar p {
  margin: 18px 0 0;
}
.ix-calendar-time {
  display: block;
  font-size: 34px;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}
.ix-calendar small {
  display: block;
  color: var(--t3, #64748b);
  margin-bottom: 24px;
}
.ix-calendar button {
  border: 0;
  background: transparent;
  color: var(--t3, #64748b);
  cursor: pointer;
  font: inherit;
  min-width: 28px;
  min-height: 28px;
}
.ix-calendar button:hover {
  color: var(--pri, #2563eb);
  background: var(--pri-bg, #eff6ff);
  border-radius: 5px;
}
.ix-calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
  margin-top: 16px;
  text-align: center;
}
.ix-calendar-grid > * {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 30px;
}
.ix-calendar-week,
.is-muted {
  color: var(--t3, #64748b);
}
.ix-calendar-grid .is-today {
  color: #fff;
  background: var(--pri, #2563eb);
  border-radius: 5px;
}
.is-muted {
  opacity: 0.5;
}
button:focus-visible {
  outline: 2px solid var(--pri, #2563eb);
  outline-offset: 2px;
}
</style>
