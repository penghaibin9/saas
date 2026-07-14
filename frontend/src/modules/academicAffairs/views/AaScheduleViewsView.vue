<template>
  <ModulePageShell
    title="课表三视图"
    subtitle="班级 / 教师 / 学生三视角查看同一批次课表（只读）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/schedule')">返回批次</button>
      <button class="mp-btn" @click="printView">打印当前视图</button>
    </template>

    <div class="mp-stack">
      <div class="aa-tabs">
        <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
      </div>

      <div class="aa-filter">
        <label class="aa-filter__item">
          {{ currentTab.field }}
          <input v-model.trim="query" class="aa-input aa-input--sm" :placeholder="currentTab.placeholder" @keyup.enter="loadView" />
        </label>
        <button class="mp-btn" @click="loadView">查看课表</button>
      </div>

      <LoadingState v-if="loading" />
      <AppSectionCard v-else :title="viewTitle">
        <p v-if="note" class="mp-note">{{ note }}</p>
        <AaScheduleGrid :items="items" :slots="slots" :editable="false" />
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 课表三视图（/admin/academic-affairs/schedule/:batchId/views）：class/teacher/student 三视角只读。 */
import { ModulePageShell, LoadingState } from '@/components/business'
import { AppSectionCard } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const TABS = [
  { key: 'class', label: '班级课表', field: '班级ID', placeholder: 'classId' },
  { key: 'teacher', label: '教师课表', field: '教师工号', placeholder: 'teacherKey' },
  { key: 'student', label: '学生课表', field: '学生ID', placeholder: 'studentId' }
]

export default {
  name: 'AaScheduleViewsView',
  components: { ModulePageShell, LoadingState, AppSectionCard, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { tabs: TABS, tab: 'class', query: '', slots: [], items: [], note: '', loading: false }
  },
  computed: {
    batchId() { return this.$route.params.batchId },
    currentTab() { return TABS.find((t) => t.key === this.tab) },
    viewTitle() { return this.currentTab.label + (this.query ? ` · ${this.query}` : '') }
  },
  watch: {
    tab() { this.items = []; this.note = ''; this.query = '' }
  },
  created() { this.loadSlots() },
  methods: {
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async loadView() {
      if (!this.query) { toast.error(`请填写${this.currentTab.field}`); return }
      this.loading = true
      this.note = ''
      let res
      if (this.tab === 'class') res = await academicAffairsApi.getScheduleClassView(this.batchId, this.query)
      else if (this.tab === 'teacher') res = await academicAffairsApi.getScheduleTeacherView(this.batchId, this.query)
      else res = await academicAffairsApi.getScheduleStudentView(this.batchId, this.query)
      if (res.code === 0) {
        this.items = (res.data && res.data.items) || []
        this.note = (res.data && res.data.note) || ''
      } else {
        toast.error(res.message || '加载失败')
      }
      this.loading = false
    },
    printView() {
      if (this.tab === 'teacher' && this.query) {
        window.open(`/admin/academic-affairs/print/schedule/${this.batchId}?type=teacher&key=${encodeURIComponent(this.query)}`, '_blank')
      } else if (this.query) {
        window.open(`/admin/academic-affairs/print/schedule/${this.batchId}?type=class&key=${encodeURIComponent(this.query)}`, '_blank')
      } else {
        toast.error('请先载入某个课表再打印')
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-200, #e5e6eb); }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-500, #646a73); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600, #2563eb); border-bottom-color: var(--primary-500, #3b82f6); font-weight: 500; }
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 160px; }
</style>
