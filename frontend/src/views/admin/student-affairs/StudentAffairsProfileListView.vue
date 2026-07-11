<template>
  <AppPageShell
    title="学生画像"
    subtitle="按当前学工身份的数据范围查看学生主档摘要、风险标签、请假与宿舍摘要入口。"
    data-scope-name="后端按当前身份返回"
    watermark-purpose="学生画像列表查看"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.profile.refresh" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="true" />
    </template>

    <AppSectionCard title="筛选">
      <div class="sa-filter">
        <AppSearchBox v-model="filters.keyword" placeholder="搜索姓名、学号" @search="load" />
        <select v-model="filters.riskLevel" class="sa-select" @change="load">
          <option value="">全部风险</option>
          <option value="LOW">低风险</option>
          <option value="MEDIUM">中风险</option>
          <option value="HIGH">高风险</option>
          <option value="CRITICAL">严重风险</option>
        </select>
        <AppPermissionButton code="studentAffairs.profile.search" variant="secondary" @click="load">
          查询
        </AppPermissionButton>
      </div>
    </AppSectionCard>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载学生画像列表…"
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <AppSectionCard title="学生列表">
        <div class="sa-table">
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>班级</th>
                <th>学籍状态</th>
                <th>风险</th>
                <th>联系方式</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in students" :key="row.studentId">
                <td>
                  <strong>{{ row.realName }}</strong>
                  <small>{{ row.studentNo }}</small>
                </td>
                <td>{{ row.className }}</td>
                <td><AppStatusTag :status="row.studentStatus" /></td>
                <td><AppRiskTag :level="row.riskLevel || 'LOW'" size="sm" /></td>
                <td><AppSensitiveText :value="row.phoneMasked || '未设置'" /></td>
                <td>{{ formatDate(row.updatedAt) }}</td>
                <td>
                  <AppPermissionButton
                    code="studentAffairs.profile.view"
                    size="sm"
                    variant="secondary"
                    @click="$router.push(`/admin/student-affairs/profile/${row.studentId}`)"
                  >
                    查看画像
                  </AppPermissionButton>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <AppPagination
          :page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          @change="onPageChange"
        />
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppExportButton,
  AppGlobalState,
  AppPageShell,
  AppPagination,
  AppPermissionButton,
  AppRiskTag,
  AppSearchBox,
  AppSectionCard,
  AppSensitiveText,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/student-affairs/api/studentAffairs.api'

export default {
  name: 'StudentAffairsProfileListView',
  components: {
    AppExportButton,
    AppGlobalState,
    AppPageShell,
    AppPagination,
    AppPermissionButton,
    AppRiskTag,
    AppSearchBox,
    AppSectionCard,
    AppSensitiveText,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      errorMessage: '',
      filters: { keyword: '', riskLevel: '' },
      students: [],
      pagination: { page: 1, pageSize: 10, total: 0 }
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return this.students.length ? 'ready' : 'empty'
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
        const res = await studentAffairsApi.listStudents({ ...this.filters, ...this.pagination })
        this.students = res.data.items
        this.pagination.total = res.data.total
      } catch (e) {
        this.errorMessage = e?.message || '学生画像列表加载失败'
      } finally {
        this.loading = false
      }
    },
    onPageChange(next) {
      this.pagination.page = next.page || next
      if (next.pageSize) this.pagination.pageSize = next.pageSize
      this.load()
    },
    formatDate(v) {
      return (v || '').replace('T', ' ').slice(0, 16) || '未设置'
    },
    exportLedger() {
      return studentAffairsApi.exportProfileLedger({ purpose: '学工学生画像台账导出' })
    }
  }
}
</script>

<style scoped>
.sa-filter {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.sa-select {
  height: 34px;
  min-width: 140px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  padding: 0 var(--space-3);
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
  vertical-align: middle;
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

