<template>
  <ModulePageShell
    title="课堂考勤统计"
    subtitle="按学生汇总各堂次 出勤/迟到/旷课/请假 次数与缺勤率（仅统计已提交场次；教师逐生点名在移动端）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div class="aa-filter">
        <label class="aa-filter__item">行政班ID<input v-model.trim="classId" class="aa-input aa-input--sm" placeholder="选填，空=范围内全部" @keyup.enter="load" /></label>
        <label class="aa-filter__item">学期<input v-model.trim="termCode" class="aa-input aa-input--sm" placeholder="学期码，选填" @keyup.enter="load" /></label>
        <label class="aa-filter__item">点名类别
          <select v-model="sessionType" class="aa-input aa-input--sm" @change="load">
            <option value="">全部</option>
            <option value="常规">常规</option>
            <option value="实训">实训</option>
            <option value="晚自习">晚自习</option>
            <option value="其他">其他</option>
          </select>
        </label>
        <button class="mp-btn" @click="load">查询</button>
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
          <div v-else class="aa-table-wrap">
            <table class="aa-table">
              <thead>
                <tr>
                  <th class="aa-th-name">学生</th><th>学号</th><th>总堂次</th>
                  <th>出勤</th><th>迟到</th><th>旷课</th><th>请假</th><th>缺勤率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in data.students" :key="s.studentId" :class="{ 'aa-row-warn': s.absent >= 3 }">
                  <td class="aa-td-name">{{ s.realName }}</td>
                  <td>{{ s.studentNo }}</td>
                  <td>{{ s.sessions }}</td>
                  <td>{{ s.present }}</td>
                  <td>{{ s.late }}</td>
                  <td :class="{ 'aa-cell-danger': s.absent > 0 }">{{ s.absent }}</td>
                  <td>{{ s.leave }}</td>
                  <td>{{ pct(s.absentRate) }}%</td>
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
/** 课堂考勤统计（/admin/academic-affairs/attendance-stats）：GET /attendance/stats（跨堂次按学生汇总）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppMetricCard, AppSectionCard } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'

export default {
  name: 'AaAttendanceStatsView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppMetricCard, AppSectionCard },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', classId: '', termCode: '', sessionType: '', data: { sessionCount: 0, students: [] } }
  },
  computed: {
    absentStudentCount() { return (this.data.students || []).filter((s) => s.absent > 0).length }
  },
  created() { this.load() },
  methods: {
    pct(v) { return Math.round((v || 0) * 100) },
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
.aa-filter { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.aa-filter__item { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-input { height: 32px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; }
.aa-input--sm { width: 180px; }
.aa-metric-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 12px; }
.aa-table-wrap { overflow-x: auto; }
.aa-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.aa-table th, .aa-table td { padding: 8px 10px; text-align: center; border-bottom: 1px solid var(--border-200, #e5e6eb); white-space: nowrap; }
.aa-table th { color: var(--text-700, #4e5969); font-weight: 600; background: var(--fill-100, #f7f8fa); }
.aa-table td { color: var(--text-900, #1f2329); }
.aa-th-name, .aa-td-name { text-align: left; min-width: 120px; }
.aa-cell-danger { color: var(--danger-600, #f53f3f); font-weight: 600; }
.aa-row-warn { background: var(--danger-50, #fff1f0); }
</style>
