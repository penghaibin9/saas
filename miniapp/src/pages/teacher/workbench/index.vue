<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="brand.schoolName" :subtitle="'教师工作台'">
      <template #right>
        <view class="wb__bell" @click="go('/pages/teacher/messages/index')">
          <text class="wb__bell-icon">✉</text>
        </view>
      </template>
    </MobileNavBar>
    <view class="wb__topbg" />

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="wb">
        <!-- 当前身份卡 -->
        <view class="page-pad">
          <view class="wb__ctx" @click="go('/pages/role-switch/index')">
            <view class="wb__ctx-avatar">{{ (user.name||'师').slice(0,1) }}</view>
            <view class="flex-1">
              <view class="row" style="gap:6px;">
                <text class="wb__ctx-name">{{ user.name }}</text>
                <text class="wb__ctx-role">{{ wb.contextTitle }}</text>
              </view>
              <text class="wb__ctx-scope">数据范围 · {{ wb.contextScope }}</text>
            </view>
            <view class="wb__ctx-switch">
              <text class="wb__ctx-switch-txt">切换身份</text>
              <text class="wb__ctx-switch-count">{{ availableCount }} 个</text>
            </view>
          </view>

          <!-- 数据摘要 -->
          <view class="wb__metrics">
            <view v-for="m in wb.metrics" :key="m.key" class="wb__metric">
              <text class="wb__metric-val">{{ m.value }}</text>
              <text class="wb__metric-label">{{ m.label }}</text>
            </view>
          </view>
        </view>

        <view class="page-pad" style="padding-top:0;">
          <!-- 快捷操作（按身份） -->
          <view class="section-head"><text class="section-head__title">快捷操作</text></view>
          <view class="wb__quick card">
            <view v-for="q in roleConfig.quickActions" :key="q.key" class="wb__quick-item" @click="quick(q)">
              <view class="wb__quick-icon">{{ q.icon }}</view>
              <text class="wb__quick-label">{{ q.label }}</text>
            </view>
          </view>

          <!-- 即将超时 -->
          <view class="section-head">
            <text class="section-head__title">即将超时</text>
            <text class="section-head__more" @click="go('/pages/teacher/todos/index')">全部待办 ›</text>
          </view>
          <view class="stack-sm">
            <MobileTodoCard
              v-for="t in wb.dueSoon"
              :key="t.id"
              :title="t.title"
              :source-module="t.module"
              :student-name="t.student"
              :deadline="deadlineText(t.deadline)"
              :status="t.status"
              :overdue="isOverdue(t.deadline)"
              action-text="去处理"
              @handle="handleTodo(t)"
              @view="handleTodo(t)"
            />
          </view>

          <!-- 风险学生 -->
          <view class="section-head">
            <text class="section-head__title">风险学生</text>
            <text class="section-head__more" @click="go('/pages/teacher/risk-students/index')">查看全部 ›</text>
          </view>
          <view class="stack-sm">
            <view v-for="r in wb.riskStudents" :key="r.id" class="wb__risk card" @click="openStudent(r)">
              <view class="wb__risk-avatar">{{ r.name.slice(0,1) }}</view>
              <view class="flex-1">
                <view class="row" style="gap:6px;">
                  <text class="t-md t-bold">{{ r.name }}</text>
                  <MobileRiskTag :level="r.level" />
                </view>
                <text class="wb__risk-type">{{ r.className }} · {{ r.type }}</text>
              </view>
              <text class="wb__risk-btn" @click.stop="handleRisk(r)">处理</text>
            </view>
          </view>

          <!-- 最近学生动态 -->
          <view class="section-head"><text class="section-head__title">最近学生动态</text></view>
          <view class="card stack-sm">
            <view v-for="a in wb.recent" :key="a.id" class="wb__act">
              <text class="wb__act-dot" />
              <text class="wb__act-text flex-1"><text class="wb__act-name">{{ a.name }}</text> {{ a.text }}</text>
              <text class="wb__act-time">{{ fromNow(a.time) }}</text>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileTabBar side="teacher" active="workbench" :badges="{ todo: todoBadge }" />
  </view>
</template>

<script>
import { tenantBrandConfig } from '@/config'
import { useSessionStore } from '@/stores/session'
import { teacherApi } from '@/services/teacherApi'
import { deadlineText, isOverdue, fromNow } from '@/utils/format'
import { go, toast } from '@/utils/nav'

export default {
  data() { return { brand: tenantBrandConfig, wb: null, state: 'loading', user: {}, roleConfig: {}, availableCount: 1 } },
  computed: {
    todoBadge() {
      if (!this.wb) return 0
      const m = this.wb.metrics.find((x) => ['todo', 'weekly', 'review', 'warning'].includes(x.key))
      return m ? Number(m.value) || 0 : 0
    }
  },
  onShow() { this.load() },
  onPullDownRefresh() { this.load(() => uni.stopPullDownRefresh()) },
  methods: {
    go, deadlineText, isOverdue, fromNow,
    load(done) {
      const session = useSessionStore()
      this.user = session.mockUser || {}
      this.roleConfig = session.roleConfig
      this.availableCount = session.availableRoles.length || 1
      this.state = 'loading'
      teacherApi.getWorkbench(session.currentRole).then((d) => {
        this.wb = d; this.state = 'ready'; done && done()
      }).catch(() => { this.state = 'error'; done && done() })
    },
    quick(q) {
      const map = {
        weekly: '/pages/teacher/internship-review/index',
        'review-open': '/pages/teacher/graduation-guide/index',
        'review-mid': '/pages/teacher/graduation-guide/index',
        'review-result': '/pages/teacher/graduation-guide/index',
        checkin: '/pages/teacher/internship-review/index',
        leave: '/pages/teacher/approval/index',
        approval: '/pages/teacher/approval/index',
        risk: '/pages/teacher/risk-students/index',
        follow: '/pages/teacher/employment-follow/index',
        unemployed: '/pages/teacher/employment-follow/index',
        warning: '/pages/teacher/risk-students/index',
        overview: '/pages/teacher/workbench/index'
      }
      if (map[q.key]) return go(map[q.key])
      toast(q.label + '（演示）')
    },
    handleTodo(t) { go('/pages/teacher/todos/index') },
    handleRisk(r) { go('/pages/teacher/risk-students/index') },
    openStudent(r) { go('/pages/teacher/student-detail/index?id=' + r.id) }
  }
}
</script>

<style scoped>
.wb__topbg { position: absolute; top: 0; left: 0; right: 0; height: 190px; background: var(--brand-gradient-teacher); z-index: -1; }
.wb__bell-icon { color: #fff; font-size: 20px; }
.wb__ctx { display: flex; align-items: center; gap: var(--space-3); background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--card-padding-mobile); box-shadow: var(--shadow-float); margin-top: var(--space-2); }
.wb__ctx-avatar { width: 46px; height: 46px; border-radius: var(--radius-full); background: var(--brand-gradient-teacher); color: #fff; display: flex; align-items: center; justify-content: center; font-size: var(--font-size-lg); }
.wb__ctx-name { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.wb__ctx-role { font-size: var(--font-size-xs); color: var(--teacher-700); background: var(--teacher-50); padding: 2px 8px; border-radius: var(--radius-full); }
.wb__ctx-scope { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.wb__ctx-switch { display: flex; flex-direction: column; align-items: center; }
.wb__ctx-switch-txt { font-size: var(--font-size-xs); color: var(--teacher-700); }
.wb__ctx-switch-count { font-size: 10px; color: var(--text-tertiary); }
.wb__metrics { display: flex; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) 0; margin-top: var(--card-gap-mobile); box-shadow: var(--shadow-card); }
.wb__metric { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px; position: relative; }
.wb__metric + .wb__metric::before { content: ''; position: absolute; left: 0; top: 20%; height: 60%; width: 1px; background: var(--border-light); }
.wb__metric-val { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--teacher-700); }
.wb__metric-label { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wb__quick { display: flex; flex-wrap: wrap; }
.wb__quick-item { width: 25%; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: var(--space-3) 0; }
.wb__quick-icon { width: 46px; height: 46px; border-radius: var(--radius-md); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: 22px; }
.wb__quick-label { font-size: var(--font-size-xs); color: var(--text-secondary); }
.wb__risk { display: flex; align-items: center; gap: var(--space-3); }
.wb__risk-avatar { width: 40px; height: 40px; border-radius: var(--radius-full); background: var(--danger-50); color: var(--danger-600); display: flex; align-items: center; justify-content: center; }
.wb__risk-type { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.wb__risk-btn { font-size: var(--font-size-sm); color: #fff; background: var(--danger-500); border-radius: var(--radius-md); padding: 6px 14px; }
.wb__act { display: flex; align-items: center; gap: var(--space-2); }
.wb__act-dot { width: 6px; height: 6px; border-radius: var(--radius-full); background: var(--teacher-500); flex-shrink: 0; }
.wb__act-text { font-size: var(--font-size-sm); color: var(--text-secondary); }
.wb__act-name { color: var(--text-primary); font-weight: var(--font-weight-medium); }
.wb__act-time { font-size: var(--font-size-xs); color: var(--text-tertiary); flex-shrink: 0; }
</style>
