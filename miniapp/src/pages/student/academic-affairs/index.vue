<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="教务中心" subtitle="课表 · 成绩 · 学籍 · 毕业" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="status">
        <!-- 学籍状态卡 -->
        <view class="aa__status" :class="status.enrolled ? 'is-ok' : 'is-warn'">
          <text class="aa__status-t">学籍状态</text>
          <text class="aa__status-v">{{ statusText(status.studentStatus) }}</text>
          <text class="aa__status-tag">{{ status.enrolled ? '在籍' : '非在籍' }}</text>
        </view>

        <view class="stack">
          <MobileActionCard title="我的课表" description="本学期课表(单双周)" icon="📅"
            action-text="查看" @action="go('/pages/student/academic-affairs/schedule')"
            @click="go('/pages/student/academic-affairs/schedule')" />
          <MobileActionCard title="我的成绩" description="成绩单 · 学分 · 挂科" icon="📊"
            action-text="查看" @action="go('/pages/student/academic-affairs/transcript')"
            @click="go('/pages/student/academic-affairs/transcript')" />
          <MobileActionCard title="学籍与异动" description="休学/复学/转专业申请" icon="📋"
            action-text="查看" @action="go('/pages/student/academic-affairs/status')"
            @click="go('/pages/student/academic-affairs/status')" />
          <MobileActionCard title="毕业进度" description="毕业资格七项审核" icon="🎓"
            action-text="查看" @action="go('/pages/student/academic-affairs/graduation')"
            @click="go('/pages/student/academic-affairs/graduation')" />
        </view>
      </view>
    </MobileGlobalState>
    <MobileTabBar side="student" active="home" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go } from '@/utils/nav'
const ST = { REGISTERED: '在籍注册', NORMAL: '在籍', SUSPENDED: '休学中', RETAINED: '留级',
  WITHDRAWN: '已退学', GRADUATED: '已毕业', COMPLETED: '已结业', PENDING_REGISTER: '待注册' }
export default {
  data() { return { status: null, state: 'loading' } },
  onLoad() { this.load() },
  methods: {
    go,
    statusText(s) { return ST[s] || s },
    load() {
      this.state = 'loading'
      studentApi.getMyAcadStatus().then((d) => { this.status = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    }
  }
}
</script>

<style scoped>
.aa__status { border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); color: #fff; }
.aa__status.is-ok { background: var(--brand-primary); }
.aa__status.is-warn { background: #d97706; }
.aa__status-t { display: block; font-size: var(--font-size-sm); opacity: 0.85; }
.aa__status-v { display: block; font-size: 20px; font-weight: 700; margin-top: 4px; }
.aa__status-tag { display: inline-block; margin-top: 6px; font-size: var(--font-size-xs); background: rgba(255,255,255,0.25); padding: 2px 10px; border-radius: var(--radius-full); }
</style>
