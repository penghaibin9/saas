<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="今天 / 未来7天" back />
    <MobileGlobalState :state="state" @retry="refresh">
      <view class="page-pad stack">
        <MobileGlobalState v-if="!items.length" state="empty" title="未来 7 天没有安排"
          description="课程、考试与办理截止都会显示在这里。" />
        <template v-else>
          <view v-for="group in grouped" :key="group.day" class="card stack-sm">
            <view class="row-between ag__dayhd">
              <text class="ag__day">{{ group.label }}</text>
              <text class="ag__daycount">{{ group.items.length }} 项</text>
            </view>
            <view v-for="item in group.items" :key="item.eventId" class="ag__row"
              :class="{ 'is-now': item.status === 'ONGOING', 'is-past': item.status === 'PAST' }"
              @click="open(item)">
              <view class="ag__time">
                <text class="ag__time-start">{{ clockOf(item.startAt) || '全天' }}</text>
                <text v-if="item.endAt" class="ag__time-end">{{ clockOf(item.endAt) }}</text>
              </view>
              <view class="ag__bar" :class="'is-' + String(item.kind || '').toLowerCase()" />
              <view class="flex-1">
                <text class="ag__title">{{ item.title }}</text>
                <text class="ag__meta">{{ metaOf(item) }}</text>
              </view>
              <MobileStatusTag v-if="item.kind === 'EXAM'" label="考试" type="warning" />
              <text v-else-if="item.status === 'ONGOING'" class="ag__now">进行中</text>
            </view>
          </view>
          <button v-if="hasMore" class="btn btn-secondary" :disabled="loadingMore" @click="loadMore">
            {{ loadingMore ? '加载中…' : '加载更多' }}
          </button>
        </template>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { canNavigate, disabledReasonOf, runAction } from '@/services/actionRouter'
import { toast } from '@/utils/nav'

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']
const KIND_TEXT = { COURSE: '课程', EXAM: '考试', DEADLINE: '办理截止' }

// V3 §6：本页是纯读投影，不是新的 deadline 真值。每条 item 的可办理动作都来自服务端
// 已解析的 action.target；没有 action 的（例如课程）就只展示，不给假按钮。
export default {
  data() {
    return { items: [], state: 'loading', cursor: '', hasMore: false, loadingMore: false }
  },
  computed: {
    grouped() {
      const buckets = new Map()
      for (const item of this.items) {
        const day = String(item.startAt || '').slice(0, 10)
        if (!buckets.has(day)) buckets.set(day, [])
        buckets.get(day).push(item)
      }
      return [...buckets.entries()].map(([day, items]) => ({ day, label: this.dayLabel(day), items }))
    }
  },
  onLoad() { this.refresh() },
  onPullDownRefresh() { this.refresh().finally(() => uni.stopPullDownRefresh()) },
  methods: {
    clockOf(iso) { return iso ? String(iso).slice(11, 16) : '' },
    dayLabel(day) {
      if (!day) return ''
      const today = new Date()
      const pad = (n) => String(n).padStart(2, '0')
      const todayKey = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`
      const date = new Date(`${day}T00:00:00`)
      const weekday = Number.isNaN(date.getTime()) ? '' : WEEKDAYS[date.getDay()]
      return day === todayKey ? `今天 · ${weekday}` : `${day.slice(5)} ${weekday}`
    },
    metaOf(item) {
      return [KIND_TEXT[item.kind] || '', item.location, item.teacherName].filter(Boolean).join(' · ')
    },
    open(item) {
      if (!item.action) return
      if (!canNavigate(item.action, 'student')) {
        toast(disabledReasonOf(item.action))
        return
      }
      runAction(item.action, { side: 'student' })
    },
    refresh() {
      this.state = this.items.length ? this.state : 'loading'
      const epoch = (this._epoch || 0) + 1
      this._epoch = epoch
      return studentApi.getAgenda(7, '', 20)
        .then((data) => {
          if (this._epoch !== epoch) return
          this.items = (data && data.items) || []
          this.cursor = (data && data.nextCursor) || ''
          this.hasMore = !!this.cursor
          this.state = 'ready'
        })
        .catch(() => { if (this._epoch === epoch) this.state = 'error' })
    },
    loadMore() {
      if (this.loadingMore || !this.hasMore) return
      this.loadingMore = true
      const epoch = this._epoch
      studentApi.getAgenda(7, this.cursor, 20)
        .then((data) => {
          if (this._epoch !== epoch) return
          const seen = new Set(this.items.map((item) => item.eventId))
          for (const item of (data && data.items) || []) {
            if (!seen.has(item.eventId)) this.items.push(item)
          }
          this.cursor = (data && data.nextCursor) || ''
          this.hasMore = !!this.cursor
        })
        .catch((e) => toast((e && e.message) || '加载失败'))
        .finally(() => { this.loadingMore = false })
    }
  }
}
</script>

<style scoped>
.ag__dayhd { padding-bottom: var(--space-2); border-bottom: 1px solid var(--border-subtle, #eee); }
.ag__day { font-size: var(--font-size-base); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.ag__daycount { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ag__row { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) 0; }
.ag__row.is-past { opacity: 0.55; }
.ag__time { width: 48px; display: flex; flex-direction: column; }
.ag__time-start { font-size: var(--font-size-sm); color: var(--text-primary); }
.ag__time-end { font-size: 11px; color: var(--text-tertiary); }
.ag__bar { width: 3px; align-self: stretch; border-radius: 2px; background: var(--border-subtle, #ddd); }
.ag__bar.is-course { background: var(--brand-primary); }
.ag__bar.is-exam { background: var(--danger-500); }
.ag__bar.is-deadline { background: var(--warning-700); }
.ag__title { display: block; font-size: var(--font-size-base); color: var(--text-primary); }
.ag__meta { display: block; font-size: 11px; color: var(--text-tertiary); margin-top: 2px; }
.ag__now { font-size: 11px; color: var(--brand-primary); }
</style>
