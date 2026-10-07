<template>
  <ModulePageShell
    class="aa-schedule-workspace"
:title="isAcademicTeacher ? '我的学期课表' : '学期课表'"
    :subtitle="isAcademicTeacher ? '默认查看本人整学期正式课程；可切换本人授课班级、教学班和教室' : '查看整学期课程安排，保留各门课程的起止周与单双周。'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="!isAcademicTeacher" @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <AaScheduleObjectBar
        :name="scheduleObjectName"
        :identity="`${termId ? `学期 #${termId}` : '学期待选择'} · ${currentDim.label}视角 · 保留起止周与单双周`"
        source="来源：当前学期正式范围头；跨范围结果由服务端合并"
        :status="hasSelection ? '只读正式学期课表' : '对象待选择'"
        :owner="ctx.currentRole.roleName || '教务排课岗'"
        next-owner="师生按正式版本读取"
      />
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          学期
          <AppTermEntityPicker v-model="termId" placeholder="选择学期" @change="onTermChange" />
        </label>
        <AppPrintButton v-if="canPrint" :handler="goPrint" label="打印本页课表" />
      </div>

      <nav class="aa-tabs">
        <button v-for="t in visibleDims" :key="t.key" class="aa-tab" :class="{ 'is-active': dim === t.key }" @click="switchDim(t.key)">{{ t.label }}</button>
      </nav>

      <!-- 班级 -->
      <div v-if="dim === 'class'" class="aa-dim-body">
        <div class="aa-filter">
          <label class="aa-filter__item aa-filter__item--grow">
            班级
            <AppClassPicker v-model="classId" :query="{ termId: termId || undefined }" placeholder="搜索班级名称" @change="onClassChange" />
          </label>
        </div>
      </div>
      <!-- 教师 -->
      <div v-else-if="dim === 'teacher'" class="aa-dim-body">
        <div class="aa-filter">
          <label v-if="!isAcademicTeacher" class="aa-filter__item">
            教师
            <AppTeacherPicker v-model="teacherKey" :query="teacherKeyQuery" placeholder="搜索教师姓名/工号" @change="load" />
          </label>
          <span v-if="isAcademicTeacher" class="mp-note">当前对象：本人正式任课关系</span>
          <AppButton v-if="!isAcademicTeacher && selfKey" @click="teacherKey = selfKey; load()">查看本人课表</AppButton>
          <AppButton v-if="!isAcademicTeacher" variant="primary" :disabled="!teacherKey" @click="load">查询</AppButton>
        </div>
      </div>
      <!-- 教室 -->
      <div v-else-if="dim === 'room'" class="aa-dim-body">
        <div class="aa-filter">
          <label class="aa-filter__item aa-filter__item--grow">
            教室
            <AppClassroomPicker v-model="classroomId" placeholder="搜索楼栋/教室编号" @change="onRoomChange" />
          </label>
        </div>
      </div>
      <!-- 学生 -->
      <div v-else-if="dim === 'student'" class="aa-dim-body">
        <div class="aa-reg-search">
          <AppStudentPicker v-model="studentId" class="aa-input--grow" placeholder="按姓名/学号检索学生" @change="onStudentChange" />
        </div>
      </div>
      <!-- 教学班 -->
      <div v-else-if="dim === 'teachingClass'" class="aa-dim-body">
        <div class="aa-reg-search">
          <AppTeachingClassPicker v-model="teachingClassCode" :query="{ termId: termId || undefined }" class="aa-input--grow" placeholder="按教学班名称/课程名搜索" @change="onTeachingClassChange" />
        </div>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!hasSelection" title="请先选择查询对象" :description="dimHint" />
      <template v-else>
        <p v-if="note" class="mp-note">{{ note }}</p>
        <AppSectionCard compact :title="resultTitle">
          <div class="aa-semester-wrap" role="region" aria-label="整学期课程分段矩阵" tabindex="0">
            <table class="aa-semester-table">
              <thead>
                <tr>
                  <th scope="col">课程与教学对象</th>
                  <th scope="col">授课教师</th>
                  <th v-for="bucket in weekBuckets" :key="bucket.key" scope="col">{{ bucket.label }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in semesterRows" :key="row.key">
                  <th scope="row">
                    <strong>{{ row.courseName || '未命名课程' }}</strong>
                    <small>{{ row.className || row.teachingClassName || '教学对象随正式课位' }}</small>
                  </th>
                  <td>{{ row.teacherName || '待正式课位确认' }}</td>
                  <td v-for="bucket in weekBuckets" :key="bucket.key">
                    <button
                      v-for="entry in row.entriesByBucket[bucket.key]"
                      :key="entry.key"
                      type="button"
                      class="aa-semester-entry"
                      @click="onItemClick(entry.item)"
                    >
                      <strong>{{ weekdayLabel(entry.item.weekday) }} · 第{{ entry.item.slotNo }}节</strong>
                      <span>{{ entry.item.classroom || '地点待确认' }}</span>
                      <small>{{ entry.item.startWeek }}-{{ entry.item.endWeek }}周{{ parityLabel(entry.item.weekParity) }}</small>
                    </button>
                    <span v-if="!row.entriesByBucket[bucket.key].length" class="aa-semester-empty">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 学期课表（/admin/academic-affairs/schedule/semester）：13B 课表管理续工第三轮新增。
 * 组合型页面——学期优先入口 + 班级/教师/教室/学生/教学班五维度切换，恒不传 week（学期全量），
 * 零新增后端接口，复用与「周课表」相同的 5 个既有课表查询端点，仅前端组合。
 * 打印仅在「班级/教师」两维度提供（复用既有 D7 打印页 AaPrintScheduleView，其当前只支持
 * type=class|teacher 两种批次内视图；教室/学生/教学班打印留待后续按需扩展打印页，不在本卡内
 * 顺手改动已验收的 W4 打印页）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppClassPicker, AppTeacherPicker, AppClassroomPicker, AppStudentPicker, AppTeachingClassPicker, AppTermEntityPicker, AppPrintButton } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { loadCurrentAcademicTerm } from '@/modules/academicAffairs/pickerAdapters'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'
import AaScheduleObjectBar from '../components/AaScheduleObjectBar.vue'

const DIMS = [
  { key: 'class', label: '班级' }, { key: 'teacher', label: '教师' }, { key: 'room', label: '教室' },
  { key: 'student', label: '学生' }, { key: 'teachingClass', label: '教学班' }
]

export default {
  name: 'AaSemesterScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppClassPicker, AppTeacherPicker, AppClassroomPicker, AppStudentPicker, AppTeachingClassPicker, AppTermEntityPicker, AppPrintButton, AaScheduleObjectBar },
  props: { ctx: { type: Object, required: true } },
  data() {
    const u = currentUserFromToken() || {}
    return {
      DIMS, dim: 'class',
      termId: '', batchId: '', batchIds: [],
      slots: [], items: [], note: '', loading: false, error: '',
      classId: '', className: '',
      teacherKey: '', teacherKeyQuery: { valueField: 'loginName' }, selfKey: String(u.loginName || u.userId || ''),
      classroomId: '', classroomText: '',
      studentId: '', studentName: '',
      teachingClassCode: '', teachingClassName: ''
    }
  },
  computed: {
    isAcademicTeacher() {
      return String(this.ctx?.currentRole?.roleCode || this.ctx?.currentRole?.roleType || '').toUpperCase() === 'ACADEMIC_TEACHER'
    },
    visibleDims() {
      return this.isAcademicTeacher
        ? this.DIMS.filter(item => ['teacher', 'class', 'room', 'teachingClass'].includes(item.key))
        : this.DIMS
    },
    currentDim() { return this.DIMS.find((item) => item.key === this.dim) || this.DIMS[0] },
    scheduleObjectName() {
      return ({ class: this.className, teacher: this.teacherKey ? `教师 ${this.teacherKey}` : '', room: this.classroomText, student: this.studentName, teachingClass: this.teachingClassName })[this.dim] || '学期课表'
    },
    hasSelection() {
      if (this.dim === 'class') return !!this.classId
      if (this.dim === 'teacher') return !!this.teacherKey
      if (this.dim === 'room') return !!this.classroomId
      if (this.dim === 'student') return !!this.studentId
      return !!this.teachingClassCode
    },
    dimHint() {
      const m = { class: '搜索并选择班级', teacher: '输入教师工号或点击「查看本人课表」', room: '搜索并选择教室',
                 student: '检索并选择学生', teachingClass: '从下方列表选择教学班' }
      return m[this.dim]
    },
    resultTitle() {
      const name = { class: this.className, teacher: `教师 ${this.teacherKey}`, room: this.classroomText,
                    student: this.studentName, teachingClass: this.teachingClassName }[this.dim]
      return (name ? `${name} · ` : '') + '本学期课表'
    },
    weekBuckets() {
      const finalWeek = Math.max(18, ...this.items.map((item) => Number(item.endWeek) || 0))
      const buckets = []
      for (let start = 1; start <= finalWeek; start += 4) {
        const end = Math.min(start + 3, finalWeek)
        buckets.push({ key: `${start}-${end}`, start, end, label: `${start}-${end}周` })
      }
      return buckets
    },
    semesterRows() {
      const groups = new Map()
      this.items.forEach((item, index) => {
        const key = [item.taskId || item.teachingTaskId || item.courseName || index, item.teacherKey || item.teacherName || '', item.classId || item.className || '', item.teachingClassCode || ''].join(':')
        if (!groups.has(key)) {
          groups.set(key, {
            key,
            courseName: item.courseName,
            className: item.className,
            teachingClassName: item.teachingClassName,
            teacherName: item.teacherName,
            items: []
          })
        }
        groups.get(key).items.push(item)
      })
      return Array.from(groups.values()).map((row) => {
        const entriesByBucket = {}
        this.weekBuckets.forEach((bucket) => {
          entriesByBucket[bucket.key] = row.items
            .filter((item) => Number(item.startWeek || 1) <= bucket.end && Number(item.endWeek || bucket.end) >= bucket.start)
            .map((item, index) => ({ key: `${item.itemId || item.scheduleItemId || index}:${bucket.key}`, item }))
        })
        return { ...row, entriesByBucket }
      })
    },
    canPrint() {
      return this.batchIds.length === 1 && this.batchId &&
        (this.dim === 'class' || this.dim === 'teacher') && this.hasSelection
    }
  },
  created() {
    this.loadSlots()
    if (this.isAcademicTeacher && this.selfKey) {
      this.dim = 'teacher'
      this.teacherKey = this.selfKey
    }
    this.initializeCurrentTerm()
  },
  methods: {
    weekdayLabel(value) {
      return ['', '周一', '周二', '周三', '周四', '周五', '周六', '周日'][Number(value)] || `周${value || '待定'}`
    },
    parityLabel(value) {
      if (String(value || 'ALL').toUpperCase() === 'ODD') return ' · 单周'
      if (String(value || 'ALL').toUpperCase() === 'EVEN') return ' · 双周'
      return ''
    },
    switchDim(key) {
      if (!this.visibleDims.some(item => item.key === key)) return
      this.dim = key
      this.items = []; this.note = ''; this.error = ''; this.batchId = ''; this.batchIds = []
      if (this.isAcademicTeacher && key === 'teacher') {
        this.teacherKey = this.selfKey
        if (this.termId) this.load()
      }
    },
    async initializeCurrentTerm() {
      try {
        const current = await loadCurrentAcademicTerm()
        if (current && current.termId) this.termId = String(current.termId)
        if (this.isAcademicTeacher && this.teacherKey) await this.load()
      } catch (error) {
        this.error = error.message || '当前学期加载失败'
      }
    },
    onTermChange() {
      if (this.isAcademicTeacher && this.dim === 'class') {
        this.classId = ''; this.className = ''; this.items = []; this.note = ''; this.batchId = ''; this.batchIds = []
        return
      }
      if (this.isAcademicTeacher && this.dim === 'teachingClass') {
        this.teachingClassCode = ''; this.teachingClassName = ''; this.items = []; this.note = ''; this.batchId = ''; this.batchIds = []
        return
      }
      if (this.hasSelection) this.load()
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    onClassChange(_v, items) {
      this.className = (items && items[0] && items[0].label) || ''
      this.load()
    },
    onRoomChange(_v, items) {
      this.classroomText = (items && items[0] && items[0].label) || ''
      this.load()
    },
    onStudentChange(value, items) {
      const item = items?.[0]
      const student = item?.raw || item || {}
      this.studentName = student.realName || student.studentName || item?.label || ''
      if (!value) return
      this.load()
    },
    onTeachingClassChange(value, items) {
      const item = items?.[0]
      const row = item?.raw || item || {}
      this.teachingClassName = row.teachingClassName || row.className || item?.label || ''
      if (!value) return
      this.load()
    },
    onItemClick(it) {
      toast.success(`${it.courseName || ''} · ${it.teacherName || ''} · ${it.classroom || ''} · ${it.startWeek}-${it.endWeek}周`)
    },
    goPrint() {
      if (!this.canPrint) return
      const key = this.dim === 'class' ? this.classId : this.teacherKey
      this.$router.push({
        path: `/admin/academic-affairs/print/schedule/${this.batchId}`,
        query: { type: this.dim, key }
      })
    },
    async load() {
      if (this.isAcademicTeacher && this.dim === 'teacher') this.teacherKey = this.selfKey
      if (!this.hasSelection) return
      this.loading = true
      this.error = ''
      const params = { termId: this.termId || undefined }
      try {
        let res
        if (this.dim === 'class') res = await academicAffairsApi.getClassSchedule(this.classId, params)
        else if (this.dim === 'teacher') res = await academicAffairsApi.getTeacherSchedule(this.teacherKey, params)
        else if (this.dim === 'room') res = await academicAffairsApi.getRoomSchedule(this.classroomId, params)
        else if (this.dim === 'student') res = await academicAffairsApi.getStudentSchedule(this.studentId, params)
        else res = await academicAffairsApi.getTeachingClassSchedule(this.teachingClassCode, params)
        if (res.code === 0) {
          this.items = res.data?.items || []
          this.note = res.data?.note || ''
          this.batchId = res.data?.batchId || ''
          this.batchIds = res.data.batchIds || (this.batchId ? [this.batchId] : [])
        } else {
          this.error = res.message || '学期课表读取失败'
          this.items = []
          this.batchId = ''
          this.batchIds = []
        }
      } catch (error) {
        this.error = error?.message || '网络连接中断，未能读取学期课表'
        this.items = []
        this.batchId = ''
        this.batchIds = []
      } finally { this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/schedule-workspace.css';
.aa-filter { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; margin-bottom: 4px; }
.aa-filter__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); min-width: 160px; }
.aa-filter__item--grow { flex: 1; min-width: 260px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-tabs { display: flex; gap: 6px; border-bottom: 1px solid var(--border-100, #f0f1f2); }
.aa-tab { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--text-600, #566073); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600, #2563eb); border-bottom-color: var(--primary-500, #3b82f6); font-weight: 500; }
.aa-dim-body { min-height: 40px; }
.aa-reg-search { display: flex; gap: 12px; align-items: center; }
.aa-cand-list { list-style: none; margin: 0; padding: 0; border: 1px solid var(--border-100, #f0f1f2); border-radius: 6px; max-height: 280px; overflow-y: auto; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 13px; }
.aa-cand-item:last-child { border-bottom: none; }
.aa-semester-wrap { overflow-x: auto; border: 1px solid var(--border-200, #dbe3ed); border-radius: 10px; }
.aa-semester-table { width: 100%; min-width: 960px; border-collapse: collapse; table-layout: fixed; }
.aa-semester-table th, .aa-semester-table td { padding: 12px; border-right: 1px solid var(--border-100, #e9edf3); border-bottom: 1px solid var(--border-100, #e9edf3); text-align: left; vertical-align: top; }
.aa-semester-table thead th { color: var(--text-600, #566073); background: var(--fill-100, #f5f7fa); font-size: 12px; font-weight: 600; }
.aa-semester-table thead th:first-child { width: 180px; }
.aa-semester-table thead th:nth-child(2) { width: 110px; }
.aa-semester-table tbody th strong, .aa-semester-table tbody th small { display: block; }
.aa-semester-table tbody th strong { color: var(--text-900, #193252); font-size: 13px; }
.aa-semester-table tbody th small { margin-top: 5px; color: var(--text-500, #68788c); font-size: 11px; font-weight: 400; }
.aa-semester-table tbody td { color: var(--text-600, #566073); font-size: 12px; }
.aa-semester-table tr:last-child > * { border-bottom: 0; }
.aa-semester-table tr > *:last-child { border-right: 0; }
.aa-semester-entry { display: grid; width: 100%; gap: 4px; margin: 0 0 6px; padding: 8px; border: 1px solid #cfe0f6; border-radius: 7px; color: #284466; background: #f2f7fd; text-align: left; cursor: pointer; }
.aa-semester-entry strong { font-size: 12px; }
.aa-semester-entry span, .aa-semester-entry small { color: #617795; font-size: 11px; }
.aa-semester-empty { display: block; padding: 12px 0; color: var(--text-400, #8794aa); text-align: center; }
.aa-semester-wrap:focus-visible, .aa-semester-entry:focus-visible { outline: 2px solid var(--pri); outline-offset: -2px; }
</style>
