<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="消息中心" />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="tm__tabs page-pad">
          <MobileSegmented :items="data.tabs" v-model="tab" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!list.length" state="empty" title="暂无消息" description="系统通知、学生动态、风险预警与催办提醒会汇总在这里。" />
          <view v-else class="stack-sm">
            <view v-for="m in list" :key="m.id" class="tm__item card" :class="{ 'is-unread': !m.read }" @click="open(m)">
              <view class="tm__top">
                <text class="tm__dot" :class="{ 'is-on': !m.read }" />
                <text class="tm__module">{{ m.module }}</text>
                <text v-if="m.level === 'high'" class="tm__urgent">重要</text>
                <text class="tm__time">{{ fromNow(m.time) }}</text>
              </view>
              <text class="tm__title">{{ m.title }}</text>
              <view v-if="tab === 'risk' || tab === 'dynamic'" class="tm__go" @click.stop="jump(tab)">去处理 ›</view>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="teacher" active="message" :badges="{ message: unreadTotal }" />
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { fromNow } from '@/utils/format'
import { go } from '@/utils/nav'
export default {
  data() { return { data: null, state: 'loading', tab: 'system' } },
  onLoad() { this.load() },
  computed: {
    list() { return this.data ? (this.data.groups[this.tab] || []) : [] },
    unreadTotal() {
      if (!this.data) return 0
      return Object.values(this.data.groups).flat().filter((m) => !m.read).length
    }
  },
  methods: {
    fromNow,
    load() {
      this.state = 'loading'
      teacherApi.getMessages().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    open(m) { m.read = true },
    jump(tab) { go(tab === 'risk' ? '/pages/teacher/risk-students/index' : '/pages/teacher/todos/index') }
  }
}
</script>

<style scoped>
.tm__tabs { padding-bottom: var(--space-3); }
.tm__item.is-unread { border-left: 3px solid var(--teacher-600); }
.tm__top { display: flex; align-items: center; gap: var(--space-2); }
.tm__dot { width: 7px; height: 7px; border-radius: var(--radius-full); background: transparent; }
.tm__dot.is-on { background: var(--danger-500); }
.tm__module { font-size: var(--font-size-xs); color: var(--teacher-700); }
.tm__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-sm); }
.tm__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.tm__title { display: block; font-size: var(--font-size-md); color: var(--text-primary); margin-top: 6px; line-height: 1.4; }
.tm__go { margin-top: 8px; font-size: var(--font-size-sm); color: var(--teacher-700); }
</style>
