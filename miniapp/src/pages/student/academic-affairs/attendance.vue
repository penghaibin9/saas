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
            <button v-if="sourceId(it)" class="btn btn-ghost at__source-button" @click="openSource(it)">查看考勤来源</button>
          </view>
          <text class="at__status">{{ attendanceText(it.status) }}</text>
        </view>
        <view v-if="sourceLoading || sourceError || sourceDetail" class="card at__source-card">
          <view class="at__source-head"><text class="t-md">考勤来源</text><button class="btn btn-ghost" @click="closeSource">关闭</button></view>
          <text v-if="sourceLoading" class="mk__sub">正在核验该场考勤来源…</text>
          <view v-else-if="sourceError" class="stack">
            <text class="mk__sub">{{ sourceError }}</text>
            <button class="btn btn-ghost" @click="retrySource">重新核验</button>
          </view>
          <view v-else-if="sourceDetail" class="stack">
            <text class="mk__sub">此来源只供核对历史记录，不改变本人考勤状态。</text>
            <view class="at__source-section">
              <text class="t-md">点名时冻结的正式课次依据</text>
              <text>课程：{{ sourceDetail.courseName || '待核对' }}</text>
              <text>上课日期：{{ sourceDetail.sessionDate }}</text>
              <text>教学周与节次：第{{ sourceDetail.weekNo }}周 · 第{{ sourceDetail.slotNo }}节 · 上课时段未保存</text>
              <text>课表安排星期：{{ weekdayText(sourceDetail.weekday) }}</text>
              <text>学期：{{ sourceDetail.termCode || '待核对' }}</text>
              <text>当时发布版本：第{{ sourceDetail.scopeHeadVersion }}版</text>
              <text>发布日期：{{ sourceDateText(sourceDetail.publishedAt) }}</text>
            </view>
            <view class="at__source-section">
              <text class="t-md">保留的历史课表资料</text>
              <text class="mk__sub">以下为历史文字资料，不作为冻结的点名依据。</text>
              <text>任课教师：{{ sourceDetail.teacherName || '未记录' }}</text>
              <text>教学班：{{ sourceDetail.className || '未记录' }}</text>
              <text>教室：{{ sourceDetail.classroom || '未记录' }}</text>
            </view>
          </view>
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
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { academicReadPage } from './read-page'
import { go } from '@/utils/nav'
const PAGE_SIZE = 20
const pageNumber = value => Math.max(1, Number(value) || 1)
const taskId = value => /^[1-9]\d*$/.test(String(value || '')) ? String(value) : ''
export default {
  components: { AcademicPageNav, AcademicPageState },
  mixins: [academicReadPage],
  data() { return { d: null, state: 'loading', courseFilter: '', teachingTaskId: '', clearReadDataOnForbidden: true,
    sourceEpoch: 0, sourceTargetId: '', sourceLoading: false, sourceError: '', sourceDetail: null } },
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
  onShow() { this.closeSource() },
  onHide() { this.closeSource() },
  onUnload() { this.closeSource() },
  methods: {
    resetAcademicContext() { this.closeSource(); this.courseFilter = ''; this.teachingTaskId = '' },
    go,
    attendanceText(status) { return { PRESENT: '出勤', LATE: '迟到', ABSENT: '旷课', LEAVE: '请假', EARLY_LEAVE: '早退', NOT_SUBMITTED: '未提交' }[status] || '待核对' },
    sourceId(row) {
      const id = row?.sessionId
      return typeof id === 'string' && /^[1-9]\d*$/.test(id) ? id : ''
    },
    weekdayText(value) { return ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][Number(value) - 1] || '星期待核对' },
    isRealDate(value) {
      if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false
      const parsed = new Date(`${value}T00:00:00.000Z`)
      return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
    },
    sourceDateText(value) {
      const date = typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value) ? value.slice(0, 10) : ''
      return this.isRealDate(date) ? `${date.slice(0, 4)}年${date.slice(5, 7)}月${date.slice(8, 10)}日` : '未记录'
    },
    closeSource() {
      this.sourceEpoch += 1
      this.sourceTargetId = ''
      this.sourceLoading = false
      this.sourceError = ''
      this.sourceDetail = null
    },
    retrySource() {
      const row = (this.d?.items || []).find(item => this.sourceId(item) === this.sourceTargetId)
      return row ? this.openSource(row) : this.closeSource()
    },
    async openSource(row) {
      const id = this.sourceId(row)
      const listedRow = (this.d?.items || []).find(item => item === row && this.sourceId(item) === id)
      this.closeSource()
      if (!id || !listedRow || this.state !== 'ready' || this.readHidden || this.readIdentity !== currentSessionGeneration()) return
      const identity = currentSessionGeneration()
      const listEpoch = this.readEpoch
      const epoch = this.sourceEpoch
      this.sourceTargetId = id
      this.sourceLoading = true
      const current = () => epoch === this.sourceEpoch && listEpoch === this.readEpoch &&
        this.sourceTargetId === id && !this.readHidden && identity === currentSessionGeneration() &&
        identity === this.readIdentity && this.state === 'ready' && (this.d?.items || []).includes(listedRow)
      try {
        const response = await studentApi.getMyAttendance({ session_id: id })
        if (!current()) return
        const item = Array.isArray(response?.items) && response.items.length === 1 ? response.items[0] : null
        const source = item?.sourceDetail
        const scheduleItemId = source?.scheduleItemId
        const sameOccurrence = source?.verified === true && this.sourceId(item) === id &&
          this.sourceId(source) === id && typeof scheduleItemId === 'string' && /^[1-9]\d*$/.test(scheduleItemId) &&
          typeof source.batchId === 'string' && /^[1-9]\d*$/.test(source.batchId) &&
          typeof source.termId === 'string' && /^[1-9]\d*$/.test(source.termId) &&
          typeof source.termCode === 'string' && source.termCode.trim() &&
          typeof source.courseName === 'string' && source.courseName.trim() &&
          this.isRealDate(source.sessionDate) &&
          (source.publishedAt == null || (typeof source.publishedAt === 'string' &&
            /^\d{4}-\d{2}-\d{2}T/.test(source.publishedAt) && this.isRealDate(source.publishedAt.slice(0, 10)))) &&
          Number.isSafeInteger(source.weekNo) && source.weekNo > 0 &&
          Number.isSafeInteger(source.weekday) && source.weekday >= 1 && source.weekday <= 7 &&
          Number.isSafeInteger(source.slotNo) && source.slotNo > 0 &&
          Number.isSafeInteger(source.scopeHeadVersion) && source.scopeHeadVersion >= 0 &&
          listedRow.scheduleItemId === scheduleItemId && item.scheduleItemId === scheduleItemId &&
          String(source.sessionDate || '') === String(listedRow.sessionDate || '') &&
          String(item.sessionDate || '') === String(listedRow.sessionDate || '') &&
          Number(source.slotNo) === Number(listedRow.slotNo) && Number(item.slotNo) === Number(listedRow.slotNo)
        if (sameOccurrence) this.sourceDetail = source
        else this.sourceError = '该场考勤来源暂时无法核验，请稍后重新核验或联系任课老师。'
      } catch (error) {
        if (current()) {
          const forbidden = Number(error?.httpStatus || error?.statusCode) === 403 || /^403/.test(String(error?.code || '')) || error?.code === 'NO_PERMISSION'
          this.sourceError = forbidden ? '当前无权核验该场考勤来源，请重新登录后再试。' : '考勤来源读取失败，请稍后重新核验。'
        }
      } finally {
        if (current()) this.sourceLoading = false
      }
    },
    clearCourseFilter() { this.courseFilter = ''; this.teachingTaskId = ''; return this.load(1) },
    changePage(page) { return this.load(page) },
    load(requestedPage = null) {
      this.closeSource()
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
.at__source-button { margin: 6px 0 0; padding: 4px 10px; font-size: 12px; }
.at__source-card { margin-top: 10px; }
.at__source-head { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.at__source-head .btn { margin:0; }
.at__source-section { display:grid; gap:6px; font-size:13px; }
</style>
