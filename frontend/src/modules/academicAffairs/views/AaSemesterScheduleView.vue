<template>
  <ModulePageShell
    title="学期课表"
    subtitle="按学期查看整学期课表（不按周过滤），支持班级/教师/教室/学生/教学班五维度切换"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">课表批次</AppButton>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          学期
          <AppTermEntityPicker v-model="termId" placeholder="选择学期" @change="load" />
        </label>
        <AppPrintButton v-if="canPrint" :handler="goPrint" label="打印本页课表" />
      </div>

      <nav class="aa-tabs">
        <button v-for="t in DIMS" :key="t.key" class="aa-tab" :class="{ 'is-active': dim === t.key }" @click="switchDim(t.key)">{{ t.label }}</button>
      </nav>

      <!-- 班级 -->
      <div v-if="dim === 'class'" class="aa-dim-body">
        <div class="aa-filter">
          <label class="aa-filter__item aa-filter__item--grow">
            班级
            <AppClassPicker v-model="classId" placeholder="搜索班级名称" @change="onClassChange" />
          </label>
        </div>
      </div>
      <!-- 教师 -->
      <div v-else-if="dim === 'teacher'" class="aa-dim-body">
        <div class="aa-filter">
          <label class="aa-filter__item">
            教师
            <AppTeacherPicker v-model="teacherKey" placeholder="搜索教师姓名/工号" @change="load" />
          </label>
          <AppButton v-if="selfKey" @click="teacherKey = selfKey; load()">查看本人课表</AppButton>
          <AppButton variant="primary" :disabled="!teacherKey" @click="load">查询</AppButton>
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
          <AppTeachingClassPicker v-model="teachingClassCode" class="aa-input--grow" placeholder="按教学班名称/课程名搜索" @change="onTeachingClassChange" />
        </div>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!hasSelection" title="请先选择查询对象" :description="dimHint" />
      <template v-else>
        <p v-if="note" class="mp-note">{{ note }}</p>
        <AppSectionCard :title="resultTitle">
          <AaScheduleGrid :items="items" :slots="slots" :editable="false" @item-click="onItemClick" />
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
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { loadCurrentAcademicTerm } from '@/modules/academicAffairs/pickerAdapters'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

const DIMS = [
  { key: 'class', label: '班级' }, { key: 'teacher', label: '教师' }, { key: 'room', label: '教室' },
  { key: 'student', label: '学生' }, { key: 'teachingClass', label: '教学班' }
]

export default {
  name: 'AaSemesterScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppClassPicker, AppTeacherPicker, AppClassroomPicker, AppStudentPicker, AppTeachingClassPicker, AppTermEntityPicker, AppPrintButton, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    const u = currentUserFromToken() || {}
    return {
      DIMS, dim: 'class',
      termId: '', batchId: '',
      slots: [], items: [], note: '', loading: false, error: '',
      classId: '', className: '',
      teacherKey: '', selfKey: String(u.userId || u.loginName || ''),
      classroomId: '', classroomText: '',
      studentId: '', studentName: '',
      teachingClassCode: '', teachingClassName: ''
    }
  },
  computed: {
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
    canPrint() {
      return this.batchId && (this.dim === 'class' || this.dim === 'teacher') && this.hasSelection
    }
  },
  created() {
    this.loadSlots()
    this.initializeCurrentTerm()
  },
  methods: {
    switchDim(key) {
      this.dim = key
      this.items = []; this.note = ''; this.error = ''; this.batchId = ''
    },
    async initializeCurrentTerm() {
      try {
        const current = await loadCurrentAcademicTerm()
        if (current && current.termId) this.termId = String(current.termId)
      } catch (error) {
        this.error = error.message || '当前学期加载失败'
      }
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
      const routeData = this.$router.resolve(`/admin/academic-affairs/print/schedule/${this.batchId}?type=${this.dim}&key=${encodeURIComponent(key)}`)
      window.open(routeData.href, '_blank')
    },
    async load() {
      if (!this.hasSelection) return
      this.loading = true
      this.error = ''
      const params = { termId: this.termId || undefined }
      let res
      if (this.dim === 'class') res = await academicAffairsApi.getClassSchedule(this.classId, params)
      else if (this.dim === 'teacher') res = await academicAffairsApi.getTeacherSchedule(this.teacherKey, params)
      else if (this.dim === 'room') res = await academicAffairsApi.getRoomSchedule(this.classroomId, params)
      else if (this.dim === 'student') res = await academicAffairsApi.getStudentSchedule(this.studentId, params)
      else res = await academicAffairsApi.getTeachingClassSchedule(this.teachingClassCode, params)
      this.loading = false
      if (res.code === 0) {
        this.items = res.data.items || []
        this.note = res.data.note || ''
        this.batchId = res.data.batchId || ''
      } else {
        this.error = res.message
        this.items = []
        this.batchId = ''
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
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
</style>
