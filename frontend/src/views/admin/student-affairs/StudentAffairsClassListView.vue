<template>
  <AppPageShell
    title="班级管理"
    subtitle="按当前学工身份的数据范围查看班级、学生、辅导员绑定、班干部和班级风险摘要。"
    data-scope-name="后端按当前身份返回"
    watermark-purpose="班级管理查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.classes.refresh" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="true" />
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载班级管理数据…"
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="sa-grid">
        <AppMetricCard title="班级数" :value="classes.length" unit="个" />
        <AppMetricCard title="学生数" :value="totalStudents" unit="人" />
        <AppMetricCard title="风险学生" :value="riskStudents" unit="人" accent="risk" />
        <AppMetricCard title="班级档案入口" value="已接入" accent="success" />
      </div>

      <AppSectionCard title="班级列表">
        <div class="sa-table">
          <table>
            <thead>
              <tr>
                <th>班级</th>
                <th>年级</th>
                <th>学生数</th>
                <th>风险概览</th>
                <th>请假统计</th>
                <th>宿舍统计</th>
                <th>班级组织</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="row.classId">
                <td>
                  <strong>{{ row.className }}</strong>
                  <small>专业 ID：{{ row.majorId || '未设置' }}</small>
                </td>
                <td>{{ row.grade || '未设置' }}</td>
                <td>{{ row.studentCount }}</td>
                <td><AppRiskTag :level="row.riskCount ? 'MEDIUM' : 'LOW'" :label="`${row.riskCount} 人`" /></td>
                <td><AppStatusTag type="info" :label="`${row.leaveCount} 条`" /></td>
                <td><AppStatusTag type="info" :label="row.dormLabel" /></td>
                <td>
                  <span>辅导员/班主任绑定</span>
                  <small>班干部 {{ row.cadreCount }} 人</small>
                </td>
                <td>
                  <div class="sa-actions">
                    <AppPermissionButton size="sm" variant="secondary" code="studentAffairs.classes.view" @click="open(row)">
                      班级详情
                    </AppPermissionButton>
                    <AppPermissionButton size="sm" variant="secondary" code="studentAffairs.profile.view" @click="openProfile(row)">
                      班级学生
                    </AppPermissionButton>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppExportButton,
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'StudentAffairsClassListView',
  components: {
    AppExportButton,
    AppGlobalState,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      errorMessage: '',
      classes: [],
      students: []
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return this.classes.length ? 'ready' : 'empty'
    },
    rows() {
      return this.classes.map((c) => {
        const students = this.students.filter((s) => s.className === c.className || s.classId === c.classId)
        return {
          ...c,
          studentCount: students.length,
          riskCount: students.filter((s) => ['MEDIUM', 'HIGH', 'CRITICAL'].includes(s.riskLevel)).length,
          leaveCount: 0,
          dormLabel: students.length ? '已串画像' : '暂无学生',
          cadreCount: c.cadreCount || 0
        }
      })
    },
    totalStudents() {
      return this.rows.reduce((sum, row) => sum + row.studentCount, 0)
    },
    riskStudents() {
      return this.rows.reduce((sum, row) => sum + row.riskCount, 0)
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const [classesRes, studentsRes] = await Promise.all([
          studentAffairsApi.listClasses(),
          studentAffairsApi.listStudents({ page: 1, pageSize: 500 })
        ])
        const classes = classesRes.data.items || []
        const cadrePairs = await Promise.all(
          classes.map((c) =>
            studentAffairsApi
              .listClassCadres(c.classId)
              .then((res) => [c.classId, (res.data.items || []).length])
              .catch(() => [c.classId, 0])
          )
        )
        const cadreMap = Object.fromEntries(cadrePairs)
        this.classes = classes.map((c) => ({ ...c, cadreCount: cadreMap[c.classId] || 0 }))
        this.students = studentsRes.data.items || []
      } catch (e) {
        this.errorMessage = e?.message || '班级管理数据加载失败'
      } finally {
        this.loading = false
      }
    },
    open(row) {
      this.$router.push(`/admin/student-affairs/classes/${row.classId}`)
    },
    openProfile(row) {
      this.$router.push({ path: '/admin/student-affairs/profile', query: { className: row.className } })
    },
    exportLedger() {
      return studentAffairsApi.exportProfileLedger({ purpose: '学工班级学生台账导出' })
    }
  }
}
</script>

<style scoped>
.sa-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
}
.sa-table {
  overflow-x: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: var(--space-3);
  border-bottom: 1px solid var(--border-light);
  text-align: left;
  font-size: var(--font-size-sm);
  vertical-align: top;
}
th {
  color: var(--text-tertiary);
  font-weight: var(--font-weight-medium);
}
td small {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>

