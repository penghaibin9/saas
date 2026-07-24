<template>
  <ModulePageShell
    title="课堂考勤统计"
    subtitle="按学生汇总各堂次 出勤/迟到/旷课/请假 次数与缺勤率（仅统计已提交场次）。产品口径：教师逐生点名仅在小程序；本页为 PC 统计查询，不提供补点名入口。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <span class="aa-filter__label">视图</span>
        <AppSelect v-model="panel" :options="panelOptions" style="min-width:140px" @change="onPanelChange" />
        <span class="aa-filter__label">行政班</span>
        <AppClassPicker v-model="classId" placeholder="全部班级" style="max-width:220px" />
        <span class="aa-filter__label">学期</span>
        <AppTermCodePicker v-model="termCode" placeholder="全部学期" style="max-width:220px" />
        <span class="aa-filter__label">点名类别</span>
        <AppSelect v-model="sessionType" :options="typeOptions" style="min-width:120px" @change="load" />
        <AppButton variant="ghost" @click="load">查询</AppButton>
        <AppButton variant="secondary" :loading="scanning" @click="scanAbsent">旷课预警扫描</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <template v-if="panel === 'sessions'">
          <AppSectionCard title="考勤场次（已提交）">
            <EmptyState v-if="!sessions.length" title="暂无考勤场次" description="教师在移动端完成并提交课堂点名后，场次出现在此" />
            <DataTable v-else :columns="sessionColumns" :rows="sessions" row-key="sessionId" />
          </AppSectionCard>
        </template>
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
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
/** 课堂考勤统计（/admin/academic-affairs/attendance-stats）：汇总 + 场次查询 + 旷课预警扫描。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppMetricCard, AppSectionCard, AppSelect, AppClassPicker, AppTermCodePicker } from '@/components/common'
import { academicAffairsApi, academicAffairsWarningApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaAttendanceStatsView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppButton, AppMetricCard, AppSectionCard, AppSelect, AppClassPicker, AppTermCodePicker
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    const q = (this.$route && this.$route.query) || {}
    return {
      loading: true, error: '', scanning: false,
      panel: q.panel === 'sessions' ? 'sessions' : 'stats',
      classId: '', termCode: '', sessionType: '',
      data: { sessionCount: 0, students: [] },
      sessions: [],
      panelOptions: [
        { label: '学生汇总', value: 'stats' },
        { label: '场次查询', value: 'sessions' }
      ],
      typeOptions: [
        { label: '全部', value: '' }, { label: '常规', value: '常规' }, { label: '实训', value: '实训' },
        { label: '晚自习', value: '晚自习' }, { label: '其他', value: '其他' }
      ],
      columns: [
        { key: 'realName', title: '学生' }, { key: 'studentNo', title: '学号' },
        { key: 'sessions', title: '总堂次', align: 'center' }, { key: 'present', title: '出勤', align: 'center' },
        { key: 'late', title: '迟到', align: 'center' }, { key: 'absent', title: '旷课', align: 'center' },
        { key: 'leave', title: '请假', align: 'center' }, { key: 'absentRate', title: '缺勤率', align: 'center' }
      ],
      sessionColumns: [
        { key: 'sessionId', title: '场次ID' }, { key: 'classId', title: '班级ID' },
        { key: 'courseName', title: '课程' }, { key: 'sessionDate', title: '日期' },
        { key: 'sessionType', title: '类别' }, { key: 'status', title: '状态' },
        { key: 'absentCount', title: '旷课人数', align: 'center' }
      ]
    }
  },
  computed: {
    absentStudentCount() { return (this.data.students || []).filter((s) => s.absent > 0).length }
  },
  watch: {
    '$route.query.panel'(v) {
      this.panel = v === 'sessions' ? 'sessions' : 'stats'
      this.load()
    }
  },
  created() { this.load() },
  methods: {
    pct(v) { return Math.round((v || 0) * 100) },
    rowClass(row) { return row.absent >= 3 ? 'aa-row-danger' : '' },
    onPanelChange() {
      const q = { ...(this.$route.query || {}), panel: this.panel === 'sessions' ? 'sessions' : undefined }
      if (!q.panel) delete q.panel
      this.$router.replace({ query: q }).catch(() => {})
      this.load()
    },
    filterParams() {
      const params = {}
      if (this.classId) params.classId = this.classId
      if (this.termCode) params.termCode = this.termCode
      if (this.sessionType) params.sessionType = this.sessionType
      return params
    },
    async load() {
      this.loading = true
      this.error = ''
      const params = this.filterParams()
      if (this.panel === 'sessions') {
        const res = await academicAffairsApi.getAttendanceSessions({ ...params, page: 1, pageSize: 50 })
        if (res.code === 0) this.sessions = res.data?.list || res.data?.items || []
        else this.error = res.message
      } else {
        const res = await academicAffairsApi.getAttendanceStats(params)
        if (res.code === 0) this.data = { sessionCount: 0, students: [], ...res.data }
        else this.error = res.message
      }
      this.loading = false
    },
    async scanAbsent() {
      this.scanning = true
      const res = await academicAffairsWarningApi.scan('attendance')
      this.scanning = false
      if (res.code === 0) {
        const d = res.data || {}
        toast.success(`旷课预警扫描完成：新增 ${d.created ?? d.newCount ?? 0}`)
      } else {
        toast.error(res.message || '扫描失败')
      }
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
:deep(.aa-row-danger) { background: var(--danger-50, #fff1f0); }
</style>
