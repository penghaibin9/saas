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
        <view v-if="courseFilter || teachingTaskId" class="card"><text>当前课程：{{ courseFilter || '指定课程' }}</text><button class="btn btn-ghost" @click="clearCourseFilter">查看全部考勤</button><text class="mk__sub">已按正式课表的课程与教学任务筛选，请继续核对课次日期与节次。</text></view>
        <view v-for="it in d.items" :key="it.sessionId" class="list-row">
          <view class="flex-1">
            <text class="t-md">{{ it.courseName || '课堂点名' }}</text>
            <text class="mk__sub">{{ it.sessionDate }} · 第{{ it.slotNo || '—' }}节</text>
          </view>
          <text class="at__status">{{ attendanceText(it.status) }}</text>
        </view>
        <text v-if="(courseFilter || teachingTaskId) && !d.items.length" class="mk__sub">尚未查到这门课程的本人考勤记录。</text>
        <view v-if="showPagination" class="at__pages">
          <button v-if="attendancePage > 1" class="btn" :disabled="state === 'loading'" @click="changePage(attendancePage - 1)">上一页</button>
          <text>第 {{ attendancePage }}/{{ attendancePageCount }} 页，共 {{ d.total }} 条</text>
          <button v-if="d.hasMore" class="btn" :disabled="state === 'loading'" @click="changePage(attendancePage + 1)">下一页</button>
        </view>
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
const PAGE_SIZE = 20
const pageNumber = value => Math.max(1, Number(value) || 1)
const taskId = value => /^[1-9]\d*$/.test(String(value || '')) ? String(value) : ''
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { d: null, state: 'loading', courseFilter: '', teachingTaskId: '', clearReadDataOnForbidden: true } },
  computed: {
    attendancePage() { return pageNumber(this.d?.page) },
    attendancePageCount() { return Math.max(1, Math.ceil(Number(this.d?.total || 0) / Math.max(1, Number(this.d?.pageSize || PAGE_SIZE)))) },
    showPagination() { return Number(this.d?.total || 0) > Number(this.d?.pageSize || PAGE_SIZE) },
    attendanceCoverageText() {
      const returned = (this.d?.items || []).length
      const total = Number(this.d?.total)
      return Number.isFinite(total)
        ? `当前第 ${this.attendancePage} 页显示 ${returned} 条，共 ${total} 条本人已提交考勤。`
        : `当前显示 ${returned} 条本人已提交考勤。`
    }
  },
  onLoad(options = {}) {
    this.courseFilter = String(options.course || '')
    this.teachingTaskId = taskId(options.teachingTaskId || options.taskId)
    this.load()
  },
  methods: {
    resetAcademicContext() { this.courseFilter = ''; this.teachingTaskId = '' },
    go,
    attendanceText(status) { return { PRESENT: '出勤', LATE: '迟到', ABSENT: '旷课', LEAVE: '请假', EARLY_LEAVE: '早退', NOT_SUBMITTED: '未提交' }[status] || '待核对' },
    clearCourseFilter() { this.courseFilter = ''; this.teachingTaskId = ''; return this.load(1) },
    changePage(page) { return this.load(page) },
    load(requestedPage = null) {
      return this.readAcademic(() => {
        const page = pageNumber(requestedPage || this.d?.page)
        const params = { page, pageSize: PAGE_SIZE }
        if (this.courseFilter) params.course = this.courseFilter
        if (this.teachingTaskId) params.teachingTaskId = this.teachingTaskId
        return studentApi.getMyAttendance(params)
      }, (d) => {
        if (!Array.isArray(d.items) || !d.summary || typeof d.summary !== 'object' || Array.isArray(d.summary)) throw new Error('考勤信息无法核对')
        this.d = {
          ...d,
          page: pageNumber(d.page),
          pageSize: Number(d.pageSize || PAGE_SIZE),
          total: Number(d.total || 0),
          hasMore: Boolean(d.hasMore)
        }
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
.at__pages { display:flex; align-items:center; justify-content:space-between; gap:8px; color:var(--text-tertiary); font-size:12px; }
.at__pages .btn { margin:0; min-width:72px; }
</style>
