<template>
  <ModulePageShell
    title="学期课表"
    subtitle="按学期查看整学期课表（不按周过滤），支持班级/教师/教室/学生/教学班五维度切换"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/schedule')">课表批次</button>
    </template>

    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item aa-filter__item--grow">
          学期
          <select v-model="termId" class="aa-select" @change="load">
            <option value="">当前已发布批次</option>
            <option v-for="t in terms" :key="t.termId" :value="t.termId">{{ t.yearCode }} 第 {{ t.termNo }} 学期</option>
          </select>
        </label>
        <button v-if="canPrint" class="mp-btn" @click="goPrint">打印本页课表</button>
      </div>

      <nav class="aa-tabs">
        <button v-for="t in DIMS" :key="t.key" class="aa-tab" :class="{ 'is-active': dim === t.key }" @click="switchDim(t.key)">{{ t.label }}</button>
      </nav>

      <!-- 班级 -->
      <div v-if="dim === 'class'" class="aa-dim-body">
        <div class="aa-filter">
          <label class="aa-filter__item aa-filter__item--grow">
            班级
            <AppClassPicker v-model="classId" :remote-search="searchClasses" placeholder="搜索班级名称" @change="onClassChange" />
          </label>
        </div>
      </div>
      <!-- 教师 -->
      <div v-else-if="dim === 'teacher'" class="aa-dim-body">
        <div class="aa-filter">
          <label class="aa-filter__item">
            教师工号
            <input v-model.trim="teacherKey" class="aa-input" placeholder="输入教师工号/登录名" @keyup.enter="load" />
          </label>
          <button v-if="selfKey" class="mp-btn" @click="teacherKey = selfKey; load()">查看本人课表</button>
          <button class="mp-btn mp-btn--primary" :disabled="!teacherKey" @click="load">查询</button>
        </div>
      </div>
      <!-- 教室 -->
      <div v-else-if="dim === 'room'" class="aa-dim-body">
        <div class="aa-filter">
          <label class="aa-filter__item aa-filter__item--grow">
            教室
            <AppRemoteSelect v-model="classroomId" :remote-search="searchRooms" placeholder="搜索楼栋/教室编号" @change="onRoomChange" />
          </label>
        </div>
      </div>
      <!-- 学生 -->
      <div v-else-if="dim === 'student'" class="aa-dim-body">
        <div class="aa-reg-search">
          <input v-model.trim="stuKw" class="aa-input aa-input--grow" placeholder="按姓名/学号检索学生" @keyup.enter="searchStudents" />
          <button class="mp-btn" :disabled="stuSearching" @click="searchStudents">检索</button>
        </div>
        <ul v-if="stuCandidates.length" class="aa-cand-list">
          <li v-for="s in stuCandidates" :key="s.studentId" class="aa-cand-item">
            <span>{{ s.realName }} · 学号 {{ s.studentNo }}</span>
            <button class="mp-link" @click="pickStudent(s)">查看课表</button>
          </li>
        </ul>
      </div>
      <!-- 教学班 -->
      <div v-else-if="dim === 'teachingClass'" class="aa-dim-body">
        <div class="aa-reg-search">
          <input v-model.trim="tcKw" class="aa-input aa-input--grow" placeholder="按教学班名称/课程名筛选（本页已加载列表内筛选）" />
        </div>
        <ul v-if="filteredTeachingClasses.length" class="aa-cand-list">
          <li v-for="c in filteredTeachingClasses" :key="c.teachingClassCode" class="aa-cand-item">
            <span>{{ c.teachingClassName || c.teachingClassCode }}</span>
            <button class="mp-link" @click="pickTeachingClass(c)">查看课表</button>
          </li>
        </ul>
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
import { AppSectionCard, AppClassPicker, AppRemoteSelect } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi, academicAffairsOrgApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

const DIMS = [
  { key: 'class', label: '班级' }, { key: 'teacher', label: '教师' }, { key: 'room', label: '教室' },
  { key: 'student', label: '学生' }, { key: 'teachingClass', label: '教学班' }
]

export default {
  name: 'AaSemesterScheduleView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppSectionCard, AppClassPicker, AppRemoteSelect, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    const u = currentUserFromToken() || {}
    return {
      DIMS, dim: 'class',
      terms: [], termId: '', batchId: '',
      slots: [], items: [], note: '', loading: false, error: '',
      classId: '', className: '',
      teacherKey: '', selfKey: String(u.userId || u.loginName || ''),
      classroomId: '', classroomText: '',
      stuKw: '', stuSearching: false, stuCandidates: [], studentId: '', studentName: '',
      tcKw: '', teachingClasses: [], teachingClassCode: '', teachingClassName: ''
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
    filteredTeachingClasses() {
      const kw = this.tcKw.trim().toLowerCase()
      if (!kw) return this.teachingClasses
      return this.teachingClasses.filter((c) =>
        (c.teachingClassName || '').toLowerCase().includes(kw) || (c.teachingClassCode || '').toLowerCase().includes(kw))
    },
    canPrint() {
      return this.batchId && (this.dim === 'class' || this.dim === 'teacher') && this.hasSelection
    }
  },
  created() {
    this.loadSlots()
    this.loadTerms()
  },
  methods: {
    switchDim(key) {
      this.dim = key
      this.items = []; this.note = ''; this.error = ''; this.batchId = ''
      if (key === 'teachingClass' && !this.teachingClasses.length) this.loadTeachingClasses()
    },
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) this.terms = res.data.list
      const curRes = await academicAffairsApi.getCurrentTerm()
      if (curRes.code === 0 && curRes.data && curRes.data.termId) this.termId = String(curRes.data.termId)
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async searchClasses(keyword) {
      const res = await academicAffairsOrgApi.listClasses({ keyword, pageSize: 20 })
      if (res.code !== 0) return []
      return (res.data.list || []).map((c) => ({ label: c.className, value: c.id }))
    },
    onClassChange(_v, items) {
      this.className = (items && items[0] && items[0].label) || ''
      this.load()
    },
    async searchRooms(keyword) {
      const res = await academicAffairsApi.getClassroomOptions(keyword)
      if (res.code !== 0) return []
      return (res.data || []).map((c) => ({ label: c.label || `${c.buildingName || ''}${c.roomCode || ''}`, value: c.classroomId }))
    },
    onRoomChange(_v, items) {
      this.classroomText = (items && items[0] && items[0].label) || ''
      this.load()
    },
    async searchStudents() {
      if (this.stuSearching) return
      this.stuSearching = true
      const res = await academicAffairsApi.getRoster({ keyword: this.stuKw || undefined, page: 1, pageSize: 20 })
      this.stuCandidates = res.code === 0 ? res.data.list : []
      this.stuSearching = false
    },
    pickStudent(s) {
      this.studentId = s.studentId
      this.studentName = s.realName
      this.stuCandidates = []
      this.load()
    },
    async loadTeachingClasses() {
      const res = await academicAffairsOrgApi.listTeachingClasses({ page: 1, pageSize: 200 })
      if (res.code === 0) this.teachingClasses = res.data.list || []
    },
    pickTeachingClass(c) {
      this.teachingClassCode = c.teachingClassCode
      this.teachingClassName = c.teachingClassName
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
