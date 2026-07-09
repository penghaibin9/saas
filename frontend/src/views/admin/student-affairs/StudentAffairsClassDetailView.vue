<template>
  <AppPageShell
    title="班级详情"
    subtitle="班级学生、辅导员/班主任绑定、班干部、通讯录、风险、请假、宿舍统计和档案入口。"
    data-scope-name="后端按班级范围校验"
    watermark-purpose="班级详情查看"
  >
    <template #actions>
      <AppPermissionButton variant="secondary" code="studentAffairs.classes.back" @click="$router.push('/admin/student-affairs/classes')">
        返回班级列表
      </AppPermissionButton>
      <AppPermissionButton variant="secondary" code="studentAffairs.classes.refresh" @click="load">
        刷新
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载班级详情…"
      @retry="load"
      @back="$router.push('/admin/student-affairs/classes')"
    >
      <div class="sa-detail-grid">
        <AppSectionCard title="班级档案">
          <AppDescriptionList :items="classItems" bordered />
        </AppSectionCard>

        <AppSectionCard title="班级组织">
          <div class="sa-tags">
            <AppStatusTag type="info" label="辅导员绑定" />
            <AppStatusTag type="info" label="班主任绑定" />
            <AppStatusTag type="success" :label="`班干部 ${cadres.length} 人`" />
          </div>
          <ul class="sa-list">
            <li v-for="cadre in cadres" :key="cadre.cadreId">
              <span>{{ cadre.position }}</span>
              <AppStatusTag :status="cadre.status" />
            </li>
          </ul>
        </AppSectionCard>

        <AppSectionCard title="班级风险概览">
          <div class="sa-tags">
            <AppRiskTag :level="riskStudents ? 'MEDIUM' : 'LOW'" :label="`${riskStudents} 人`" />
            <AppPermissionButton size="sm" variant="secondary" code="studentAffairs.risk.view" @click="$router.push('/admin/student-affairs/risk')">
              进入风险预警
            </AppPermissionButton>
          </div>
        </AppSectionCard>

        <AppSectionCard title="班级请假 / 宿舍统计">
          <div class="sa-metrics">
            <AppMetricCard title="学生数" :value="students.length" unit="人" />
            <AppMetricCard title="请假摘要" value="B3 串联" accent="warning" />
            <AppMetricCard title="宿舍摘要" value="B2 串联" accent="success" />
          </div>
        </AppSectionCard>
      </div>

      <AppSectionCard title="班级学生与通讯录">
        <div class="sa-table">
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>学籍状态</th>
                <th>风险</th>
                <th>联系方式</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in students" :key="row.studentId">
                <td>
                  <strong>{{ row.realName }}</strong>
                  <small>{{ row.studentNo }}</small>
                </td>
                <td><AppStatusTag :status="row.studentStatus" /></td>
                <td><AppRiskTag :level="row.riskLevel || 'LOW'" size="sm" /></td>
                <td><AppSensitiveText :value="row.phoneMasked || '未设置'" /></td>
                <td>
                  <AppPermissionButton size="sm" variant="secondary" code="studentAffairs.profile.view" @click="$router.push(`/admin/student-affairs/profile/${row.studentId}`)">
                    学生画像
                  </AppPermissionButton>
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
  AppDescriptionList,
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppSensitiveText,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'StudentAffairsClassDetailView',
  components: {
    AppDescriptionList,
    AppGlobalState,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppSensitiveText,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      errorMessage: '',
      classInfo: {},
      students: [],
      cadres: []
    }
  },
  computed: {
    classId() {
      return this.$route.params.classId
    },
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return this.classInfo.classId ? 'ready' : 'empty'
    },
    classItems() {
      return [
        { label: '班级名称', value: this.classInfo.className },
        { label: '年级', value: this.classInfo.grade },
        { label: '专业 ID', value: this.classInfo.majorId },
        { label: '学生数', value: `${this.students.length} 人` },
        { label: '班级档案', value: '已提供归档入口' },
        { label: '数据范围', value: '后端按 classId 校验' }
      ]
    },
    riskStudents() {
      return this.students.filter((s) => ['MEDIUM', 'HIGH', 'CRITICAL'].includes(s.riskLevel)).length
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
        const classesRes = await studentAffairsApi.listClasses()
        this.classInfo = (classesRes.data.items || []).find((c) => c.classId === String(this.classId)) || {}
        const [cadresRes, studentsRes] = await Promise.all([
          studentAffairsApi.listClassCadres(this.classId),
          studentAffairsApi.listStudents({ page: 1, pageSize: 500 })
        ])
        this.cadres = cadresRes.data.items || []
        this.students = (studentsRes.data.items || []).filter(
          (s) => s.className === this.classInfo.className || s.classId === this.classInfo.classId
        )
      } catch (e) {
        this.errorMessage = e?.message || '班级详情加载失败'
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.sa-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: var(--space-4);
}
.sa-tags,
.sa-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  align-items: center;
}
.sa-list {
  list-style: none;
  margin: var(--space-3) 0 0;
  padding: 0;
  display: grid;
  gap: var(--space-2);
}
.sa-list li {
  display: flex;
  justify-content: space-between;
  gap: var(--space-3);
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
</style>

