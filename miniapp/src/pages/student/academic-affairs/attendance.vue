<template>
  <view class="page-wrap">
    <AcademicPageNav variant="default" title="我的考勤" show-back />
    <AcademicPageState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <view class="card">
          <text class="t-sm">出勤 {{ d.summary.PRESENT || 0 }} · 迟到 {{ d.summary.LATE || 0 }} · 旷课 {{ d.summary.ABSENT || 0 }} · 请假 {{ d.summary.LEAVE || 0 }}</text>
          <text class="mk__sub">{{ d.note }}</text>
        <text class="mk__sub">{{ attendanceCoverageText }}</text>
        </view>
        <AcademicPageState v-if="!d.items.length" state="empty" title="暂无考勤记录" :description="d.note" />
        <view v-if="courseFilter" class="card"><text>当前课程：{{ courseFilter }}</text><button class="btn btn-ghost" @click="courseFilter = ''">查看全部考勤</button><text class="mk__sub">按课程名称筛选，请继续核对课次日期与节次。</text></view>
        <view v-for="it in filteredItems.slice(0, listLimit)" :key="it.sessionId" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ it.courseName || '课堂点名' }}</text>
            <text class="mk__sub">{{ it.sessionDate }} · 第{{ it.slotNo || '—' }}节</text>
          </view>
          <text class="at__status">{{ attendanceText(it.status) }}</text>
        </view>
        <text v-if="courseFilter && !filteredItems.length" class="mk__sub">尚未查到这门课程的本人考勤记录。</text>
        <button v-if="filteredItems.length > listLimit" class="btn" @click="listLimit += 20">查看更多记录</button>
        <text class="mk__sub">未提交与无课不记为缺勤。对记录有疑问，请联系任课老师核对课次。</text>
        <button class="btn btn-primary" @click="go('/pages/student/academic-affairs/schedule')">查看正式课表</button>
      </view>
    </AcademicPageState>
    <MobileTabBar side="student" active="" />
  </view>
</template>
<script>
import AcademicPageNav from './AcademicPageNav.vue'
import AcademicPageState from './AcademicPageState.vue'
import { studentApi } from '@/services/studentApi'
import { academicReadPage } from './read-page'
import { go } from '@/utils/nav'
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { d: null, state: 'loading', courseFilter: '', clearReadDataOnForbidden: true } },
  computed: {
    filteredItems() { return (this.d?.items || []).filter(item => !this.courseFilter || item.courseName === this.courseFilter) },
    attendanceCoverageText() {
      const returned = (this.d?.items || []).length
      const total = Number(this.d?.total)
      return Number.isFinite(total) && total > returned
        ? `当前返回 ${returned}/${total} 条本人已提交考勤；当前接口未提供翻页。`
        : `当前返回 ${returned} 条本人已提交考勤。`
    }
  },
  onLoad(options = {}) { this.courseFilter = String(options.course || ''); this.load() },
  methods: {
    resetAcademicContext() { this.courseFilter = '' },
    go,
    attendanceText(status) { return { PRESENT: '出勤', LATE: '迟到', ABSENT: '旷课', LEAVE: '请假', EARLY_LEAVE: '早退', NOT_SUBMITTED: '未提交' }[status] || '待核对' },
    load() {
      return this.readAcademic(() => studentApi.getMyAttendance(), (d) => {
        if (!Array.isArray(d.items) || !d.summary || typeof d.summary !== 'object' || Array.isArray(d.summary)) throw new Error('考勤信息无法核对')
        this.d = d
      })
    }
  }
}
</script>
<style scoped>
.at__status { flex-shrink: 0; padding: 4px 8px; border-radius: 8px; background: var(--brand-50, #edf3fc); color: var(--brand-primary); font-size: 12px; }
.page-wrap { font-family: -apple-system, BlinkMacSystemFont, "Microsoft YaHei", sans-serif; padding-bottom: calc(64px + env(safe-area-inset-bottom)); }
button, input, textarea { font-family: inherit; }
.mk__sub { display:block; color: var(--t3); font-size: 12px; margin-top: 4px; }
</style>
