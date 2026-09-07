<template>
  <ModulePageShell
    class="aa-schedule-workspace"
    title="课表三视图"
    subtitle="按班级、教师或学生查看同一批次的课表。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/schedule')">返回批次</AppButton>
      <AppPrintButton :handler="printView" :disabled="loading || !!error || !loadedQuery" label="打印当前视图" />
    </template>

    <div class="mp-stack">
      <div class="aa-tabs">
        <button v-for="t in tabs" :key="t.key" class="aa-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
      </div>

      <div class="aa-filter">
        <label class="aa-filter__item">
          {{ currentTab.field }}
          <AppClassPicker v-if="tab === 'class'" v-model="query" placeholder="选择班级" />
          <AppTeacherPicker v-else-if="tab === 'teacher'" v-model="query" :query="teacherKeyQuery" placeholder="选择教师" />
          <AppStudentPicker v-else v-model="query" placeholder="选择学生" />
        </label>
        <AppButton @click="loadView">查看课表</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="loadView" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!loadedQuery" :title="`请先选择${currentTab.field}`" description="选择查询对象后，点击「查看课表」。" />
      <AppSectionCard compact v-else :title="viewTitle">
        <p v-if="note" class="mp-note">{{ note }}</p>
        <AaScheduleGrid :items="items" :slots="slots" :editable="false" />
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 课表三视图（/admin/academic-affairs/schedule/:batchId/views）：class/teacher/student 三视角只读。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppPrintButton, AppClassPicker, AppTeacherPicker, AppStudentPicker } from '@/components/common'
import AaScheduleGrid from '@/modules/academicAffairs/components/AaScheduleGrid.vue'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const TABS = [
  { key: 'class', label: '班级课表', field: '班级' },
  { key: 'teacher', label: '教师课表', field: '教师' },
  { key: 'student', label: '学生课表', field: '学生' }
]

export default {
  name: 'AaScheduleViewsView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppPrintButton, AppClassPicker, AppTeacherPicker, AppStudentPicker, AaScheduleGrid },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tabs: TABS, tab: 'class', query: '', slots: [], items: [], note: '', loading: false,
      teacherKeyQuery: { valueField: 'loginName' }, error: '', loadedQuery: '', requestVersion: 0
    }
  },
  computed: {
    batchId() { return this.$route.params.batchId },
    currentTab() { return TABS.find((t) => t.key === this.tab) },
    viewTitle() { return this.currentTab.label }
  },
  watch: {
    tab() { this.query = ''; this.resetView() },
    query() { this.resetView() }
  },
  created() { this.loadSlots() },
  methods: {
    resetView() {
      this.requestVersion += 1
      this.items = []; this.note = ''; this.error = ''; this.loadedQuery = ''; this.loading = false
    },
    async loadSlots() {
      const res = await academicAffairsApi.getTimeSlots()
      if (res.code === 0) this.slots = res.data
    },
    async loadView() {
      if (!this.query) { toast.error(`请选择${this.currentTab.field}`); return }
      const version = ++this.requestVersion
      const query = this.query
      this.loading = true
      this.note = ''
      this.error = ''
      this.loadedQuery = ''
      try {
        let res
        if (this.tab === 'class') res = await academicAffairsApi.getScheduleClassView(this.batchId, query)
        else if (this.tab === 'teacher') res = await academicAffairsApi.getScheduleTeacherView(this.batchId, query)
        else res = await academicAffairsApi.getScheduleStudentView(this.batchId, query)
        if (version !== this.requestVersion) return
        if (res.code === 0) {
          this.items = res.data?.items || []
          this.note = res.data?.note || ''
          this.loadedQuery = query
        } else this.error = res.message || '课表读取失败，请重试'
      } catch (exception) {
        if (version === this.requestVersion) this.error = exception?.message || '课表读取失败，请重试'
      } finally {
        if (version === this.requestVersion) this.loading = false
      }
    },
    printView() {
      if (this.loading || this.error || !this.loadedQuery || this.loadedQuery !== this.query) {
        toast.error('请先载入某个课表再打印')
        return
      }
      window.open(`/admin/academic-affairs/print/schedule/${this.batchId}?type=${this.tab}&key=${encodeURIComponent(this.loadedQuery)}`, '_blank', 'noopener')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/schedule-workspace.css';
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-200, #e5e6eb); }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-500, #646a73); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600, #2563eb); border-bottom-color: var(--primary-500, #3b82f6); font-weight: 500; }
.aa-filter { display: flex; gap: 16px; align-items: center; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 160px; }
</style>
