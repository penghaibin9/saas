<template>
  <view class="page-wrap">
    <!-- 顶部品牌栏 + 身份 -->
    <MobileNavBar variant="brand" :title="brand.schoolName" :subtitle="brand.platformShortName">
      <template #right>
        <view class="home__bell" @click="go('/pages/student/messages/index')">
          <text class="home__bell-icon">✉</text>
          <text v-if="home && home.metrics.unread" class="home__bell-badge">{{ home.metrics.unread }}</text>
        </view>
      </template>
    </MobileNavBar>

    <view class="home__topbg" />

    <MobileGlobalState :state="state" @retry="load">
      <view class="home__body">
        <!-- 用户问候 + 校园码 -->
        <view class="home__hi">
          <view class="flex-1">
            <text class="home__hi-name">{{ greeting }}，{{ user.name }}</text>
            <text class="home__hi-sub">{{ user.className }} · {{ user.stageText }}</text>
          </view>
          <view class="home__code" @click="toast('校园码将随学校门禁对接后启用')">
            <text class="home__code-icon">▣</text>
            <text class="home__code-txt">校园码</text>
          </view>
        </view>

        <view class="page-pad stack">
          <!-- 阶段主卡 -->
          <view class="home__stage">
            <view class="row-between">
              <text class="home__stage-title">{{ home.stageCard.title }}</text>
              <MobileStatusTag :label="home.stageCard.stageText" type="processing" />
            </view>
            <text class="home__stage-sub">{{ home.stageCard.subtitle }}</text>
            <view class="home__stage-prog">
              <MobileProgress :value="home.stageCard.progress" tone="brand" />
            </view>
          </view>

          <!-- 下一步行动 -->
          <view class="section-head"><text class="section-head__title">下一步该做什么</text></view>
          <MobileActionCard
            :title="home.nextAction.title"
            :description="home.nextAction.desc + ' · ' + deadlineText(home.nextAction.deadline)"
            icon="→"
            :action-text="home.nextAction.actionText"
            @action="go(home.nextAction.route)"
            @click="go(home.nextAction.route)"
          />

          <!-- 当前阻断 -->
          <template v-if="home.blockers.length">
            <MobileInlineAlert
              v-for="b in home.blockers"
              :key="b.id"
              type="warning"
              :title="b.title"
              :description="b.reason"
            >
              <template #actions>
                <text class="home__alert-btn" @click="go('/pages/student/my-applications/index')">{{ b.solveText }}</text>
              </template>
            </MobileInlineAlert>
          </template>

          <!-- 快捷服务 -->
          <view class="section-head"><text class="section-head__title">常用服务</text></view>
          <view class="home__grid card">
            <view
              v-for="q in home.quickServices"
              :key="q.key"
              class="home__grid-item"
              @click="go(q.route)"
            >
              <view class="home__grid-icon">{{ q.icon }}</view>
              <text class="home__grid-label">{{ q.label }}</text>
            </view>
          </view>

          <!-- 今日课程 -->
          <view class="section-head">
            <text class="section-head__title">今日课程</text>
            <text class="section-head__more" @click="go('/pages/student/academic/index')">学业进度 ›</text>
          </view>
          <view class="card stack-sm">
            <view v-for="c in home.todayCourses" :key="c.id" class="home__course">
              <view class="home__course-time" :class="{ 'is-now': c.status === 'current' }">
                <text>{{ c.time.split('-')[0] }}</text>
                <text class="home__course-dur">{{ c.time.split('-')[1] }}</text>
              </view>
              <view class="home__course-line" :class="{ 'is-now': c.status === 'current' }" />
              <view class="flex-1">
                <text class="home__course-name">{{ c.name }}</text>
                <text class="home__course-place">{{ c.place }}</text>
              </view>
              <text v-if="c.status === 'current'" class="home__course-tag">进行中</text>
            </view>
          </view>

          <!-- 待办 -->
          <view class="section-head">
            <text class="section-head__title">我的待办</text>
            <text class="section-head__more" @click="go('/pages/student/messages/index')">全部 ›</text>
          </view>
          <view class="stack-sm">
            <MobileTodoCard
              v-for="t in home.todos"
              :key="t.id"
              :title="t.title"
              :source-module="t.module"
              :deadline="fmtDeadline(t.deadline)"
              :status="t.status"
              action-text="去办理"
              @handle="go('/pages/student/campus-service/index')"
            />
          </view>

          <!-- 通知 -->
          <view class="section-head"><text class="section-head__title">校园通知</text></view>
          <view class="card stack-sm">
            <view v-for="n in home.notices" :key="n.id" class="home__notice">
              <text v-if="n.important" class="home__notice-tag">重要</text>
              <text class="home__notice-title ellipsis flex-1">{{ n.title }}</text>
              <text class="home__notice-src">{{ n.source }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileTabBar side="student" active="home" :badges="{ message: home ? home.metrics.unread : 0 }" />
  </view>
</template>

<script>
import { tenantBrandConfig } from '@/config'
import { useSessionStore } from '@/stores/session'
import { studentApi } from '@/services/studentApi'
import { deadlineText, fromNow } from '@/utils/format'
import { go, toast } from '@/utils/nav'

export default {
  data() {
    return { brand: tenantBrandConfig, home: null, state: 'loading', user: {}, greeting: '你好' }
  },
  onLoad() {
    const session = useSessionStore()
    this.user = session.mockUser || {}
    this.load()
  },
  onPullDownRefresh() {
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    go, toast, deadlineText,
    fmtDeadline(d) {
      return deadlineText(d)
    },
    load(done) {
      this.state = 'loading'
      studentApi.getHome().then((data) => {
        this.home = data
        this.greeting = data.greeting || '你好'
        this.state = 'ready'
        done && done()
      }).catch(() => {
        this.state = 'error'
        done && done()
      })
    }
  }
}
</script>

<style scoped>
.home__topbg { position: absolute; top: 0; left: 0; right: 0; height: 200px; background: var(--brand-gradient); z-index: -1; }
.home__bell { position: relative; }
.home__bell-icon { color: #fff; font-size: 20px; }
.home__bell-badge {
  position: absolute; top: -6px; right: -8px; min-width: 15px; height: 15px; padding: 0 3px;
  background: var(--danger-500); color: #fff; font-size: 10px; line-height: 15px; text-align: center; border-radius: var(--radius-full);
}
.home__hi { display: flex; align-items: center; padding: var(--space-4) var(--page-padding-mobile) var(--space-3); }
.home__hi-name { color: #fff; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.home__hi-sub { display: block; color: rgba(255,255,255,0.88); font-size: var(--font-size-sm); margin-top: 2px; }
.home__code { display: flex; flex-direction: column; align-items: center; background: rgba(255,255,255,0.18); padding: var(--space-2) var(--space-3); border-radius: var(--radius-md); }
.home__code-icon { color: #fff; font-size: 22px; }
.home__code-txt { color: #fff; font-size: 11px; margin-top: 2px; }
.home__stage {
  background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--card-padding-mobile);
  box-shadow: var(--shadow-float); margin-top: calc(-1 * var(--space-2));
}
.home__stage-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.home__stage-sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: var(--space-2) 0 var(--space-3); }
.home__alert-btn { font-size: var(--font-size-sm); color: var(--warning-700); font-weight: var(--font-weight-medium); }
.home__grid { display: flex; flex-wrap: wrap; }
.home__grid-item { width: 25%; display: flex; flex-direction: column; align-items: center; gap: var(--space-1); padding: var(--space-2) 0; }
.home__grid-icon {
  width: 46px; height: 46px; border-radius: var(--radius-md); background: var(--primary-50);
  color: var(--brand-primary); display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.home__grid-label { font-size: var(--font-size-xs); color: var(--text-secondary); }
.home__course { display: flex; align-items: stretch; gap: var(--space-3); }
.home__course-time { width: 52px; display: flex; flex-direction: column; color: var(--text-secondary); font-size: var(--font-size-sm); }
.home__course-time.is-now { color: var(--brand-primary); font-weight: var(--font-weight-semibold); }
.home__course-dur { font-size: 11px; color: var(--text-tertiary); }
.home__course-line { width: 3px; border-radius: 3px; background: var(--border-base); }
.home__course-line.is-now { background: var(--brand-primary); }
.home__course-name { font-size: var(--font-size-md); color: var(--text-primary); }
.home__course-place { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.home__course-tag { align-self: center; font-size: var(--font-size-xs); color: var(--brand-primary); background: var(--primary-50); padding: 2px 8px; border-radius: var(--radius-full); }
.home__notice { display: flex; align-items: center; gap: var(--space-2); }
.home__notice-tag { font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-sm); flex-shrink: 0; }
.home__notice-title { font-size: var(--font-size-base); color: var(--text-primary); }
.home__notice-src { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
</style>
