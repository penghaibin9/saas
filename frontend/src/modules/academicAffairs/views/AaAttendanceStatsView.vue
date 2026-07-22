<template>
  <ModulePageShell
    title="课堂考勤统计"
    subtitle="按学生汇总各堂次 出勤/迟到/旷课/请假 次数与缺勤率（仅统计已提交场次；教师逐生点名在移动端）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <span class="aa-filter__label">行政班</span>
        <AppClassPicker v-model="classId" placeholder="全部班级" style="max-width:220px" />
        <span class="aa-filter__label">学期</span>
        <AppTermCodePicker v-model="termCode" placeholder="全部学期" style="max-width:220px" />
        <span class="aa-filter__label">点名类别</span>
        <AppSelect v-model="sessionType" :options="typeOptions" style="min-width:120px" @change="load" />
        <AppButton variant="ghost" @click="load">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <div class="aa-metric-grid">
          <AppMetricCard title="已统计场次" :value="data.sessionCount" unit="次" />
          <AppMetricCard title="涉及学生" :value="data.students.length" unit="人" />
          <AppMetricCard title="有旷课学生" :value="absentStudentCount" unit="人" />
        </div>

        <AppSectionCard title="学生考勤汇总（按旷课次数降序）">
          <EmptyState v-if="!data.students.length" title="暂无考勤统计" description="教师在移动端完成并提交课堂点名后，这里出现跨堂次汇总" />
          <DataTable v-else :columns="columns" :rows="data.students" row-key="studentId" :row-class="rowClass">
            <template #cell-absent="{ row }"><span :class="{ 'aa-cell-danger': row.absent > 0 }">{{ row.absent }}</span></template>
            <template #cell-absentRate="{ row }">{{ pct(row.absentRate) }}%</template>
          </DataTable>
        </AppSectionCard>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 课堂考勤统计（/admin/academic-affairs/attendance-stats）：GET /attendance/stats（跨堂次按学生汇总）。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppSectionCard, AppSelect, AppClassPicker, AppTermCodePicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaAttendanceStatsView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppButton, AppMetricCard, AppSectionCard, AppSelect, AppClassPicker, AppTermCodePicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', classId: '', termCode: '', sessionType: '',
      data: { sessionCount: 0, students: [] },
      typeOptions: [
        { label: '全部', value: '' }, { label: '常规', value: '常规' }, { label: '实训', value: '实训' },
        { label: '晚自习', value: '晚自习' }, { label: '其他', value: '其他' }
      ],
      columns: [
        { key: 'realName', title: '学生' }, { key: 'studentNo', title: '学号' },
        { key: 'sessions', title: '总堂次', align: 'center' }, { key: 'present', title: '出勤', align: 'center' },
        { key: 'late', title: '迟到', align: 'center' }, { key: 'absent', title: '旷课', align: 'center' },
        { key: 'leave', title: '请假', align: 'center' }, { key: 'absentRate', title: '缺勤率', align: 'center' }
      ]
    }
  },
  computed: {
    absentStudentCount() { return (this.data.students || []).filter((s) => s.absent > 0).length }
  },
  created() { this.load() },
  methods: {
    pct(v) { return Math.round((v || 0) * 100) },
    rowClass(row) { return row.absent >= 3 ? 'aa-row-danger' : '' },
    async load() {
      this.loading = true
      this.error = ''
      const params = {}
      if (this.classId) params.classId = this.classId
      if (this.termCode) params.termCode = this.termCode
      if (this.sessionType) params.sessionType = this.sessionType
      const res = await academicAffairsApi.getAttendanceStats(params)
      if (res.code === 0) this.data = { sessionCount: 0, students: [], ...res.data }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-filter { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.aa-filter__label { font-size: 13px; color: var(--text-700, #4e5969); }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.aa-cell-danger { color: var(--danger-600, #f53f3f); font-weight: 600; }
/* 旷课≥3 整行标红（旷课多的重点学生一眼可见）——DataTable rowClass 上色 */
:deep(.aa-row-danger) { background: var(--danger-50, #fff1f0); }
</style>
