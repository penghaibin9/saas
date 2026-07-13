<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="消息中心" />
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="msg__tabs page-pad">
          <MobileSegmented :items="data.tabs" v-model="tab" />
        </view>
        <view class="page-pad" style="padding-top:0;">
          <MobileGlobalState v-if="!list.length" state="empty" title="暂无消息" description="这里会收到待办、通知、服务进度与课程教务消息。" />
          <view v-else class="stack-sm">
            <view v-for="m in pagedSlice(list)" :key="m.id" class="msg__item card" :class="{ 'is-unread': !m.read }" @click="open(m)">
              <view class="msg__item-top">
                <text class="msg__dot" :class="{ 'is-on': !m.read }" />
                <text class="msg__module">{{ m.module }}</text>
                <text v-if="m.level === 'high'" class="msg__urgent">重要</text>
                <text class="msg__time">{{ fromNow(m.time) }}</text>
              </view>
              <text class="msg__title">{{ m.title }}</text>
              <view v-if="m.deadline" class="msg__sub">截止 {{ deadlineText(m.deadline) }}</view>
              <view v-if="m.status" class="msg__sub"><MobileStatusTag :status="m.status" /></view>
              <view v-if="m.actionable || m.receipt" class="msg__actions">
                <text v-if="m.actionable" class="msg__btn is-primary" @click.stop="handle(m)">去处理</text>
                <text v-if="m.receipt" class="msg__btn" @click.stop="toast('回执确认功能即将开放')">确认回执</text>
              </view>
            </view>
            <view v-if="pagedFooter(list) === 'more'" class="msg__paging" @click="pagedLoadMore">上拉加载更多</view>
            <view v-else-if="pagedFooter(list) === 'end'" class="msg__paging is-end">没有更多了</view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="message" :badges="{ message: unreadTotal }" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { fromNow, deadlineText } from '@/utils/format'
import { listPaging } from '@/utils/listPaging'
import { toast, go } from '@/utils/nav'
export default {
  mixins: [listPaging(20)],
  data() { return { data: null, state: 'loading', tab: 'todo' } },
  onLoad() { this.load() },
  // onReachBottom 必须写在页面本身，mp-weixin 才会注册
  onReachBottom() { this.pagedReachBottom() },
  watch: {
    // 切换 tab 回到第一批
    tab() { this.pagedReset() }
  },
  computed: {
    list() { return this.data ? (this.data.groups[this.tab] || []) : [] },
    unreadTotal() {
      if (!this.data) return 0
      return Object.values(this.data.groups).flat().filter((m) => !m.read).length
    }
  },
  methods: {
    toast, fromNow, deadlineText,
    pagingList() { return this.list },
    load() {
      this.state = 'loading'
      studentApi.getMessages().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    /** 打开消息：本地即时置灰 + 真实通知（msg- 前缀）同步服务器已读，失败不打扰阅读 */
    open(m) {
      m.read = true
      this._syncRead(m)
    },
    _syncRead(m) {
      if (m._synced || !/^msg-\d+$/.test(String(m.id))) return
      m._synced = true
      studentApi.markMessageRead(String(m.id).replace('msg-', '')).catch(() => { m._synced = false })
    },
    handle(m) {
      m.read = true
      this._syncRead(m)
      if (m.status === 'RETURNED') return go('/pages/student/my-applications/index')
      go('/pages/student/campus-service/index')
    }
  }
}
</script>

<style scoped>
.msg__tabs { padding-bottom: var(--space-3); }
.msg__item.is-unread { border-left: 3px solid var(--brand-primary); }
.msg__item-top { display: flex; align-items: center; gap: var(--space-2); }
.msg__dot { width: 7px; height: 7px; border-radius: var(--radius-full); background: transparent; }
.msg__dot.is-on { background: var(--danger-500); }
.msg__module { font-size: var(--font-size-xs); color: var(--brand-primary); }
.msg__urgent { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-sm); }
.msg__time { margin-left: auto; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.msg__title { display: block; font-size: var(--font-size-md); color: var(--text-primary); margin-top: 6px; line-height: 1.4; }
.msg__sub { margin-top: 6px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.msg__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.msg__btn { font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: 5px 12px; }
.msg__btn.is-primary { color: #fff; background: var(--brand-primary); border-color: var(--brand-primary); }
.msg__paging { text-align: center; padding: var(--space-3) 0; font-size: var(--font-size-sm); color: var(--brand-primary); }
.msg__paging.is-end { color: var(--text-tertiary); }
</style>
