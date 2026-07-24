<template>
  <AppPageShell
    title="学生画像"
    subtitle="按当前学工身份的数据范围查看学生主档摘要、风险标签、请假与宿舍摘要入口。"
    data-scope-name="后端按当前身份返回"
    watermark-purpose="学生画像列表查看"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.student.view')" code="studentAffairs.student.view" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
      <AppExportButton :export-fn="exportLedger" :has-permission="true" />
    </template>

    <AppSectionCard title="筛选">
      <div class="sa-filter">
        <AppSearchBox v-model="filters.keyword" placeholder="搜索姓名、学号" @search="onSearch" />
        <AppSelect v-model="filters.riskLevel" class="sa-select" :options="RISK_FILTER_OPTIONS" placeholder="" @change="onSearch" />
        <AppPermissionButton :allowed="canBtn('studentAffairs.student.view')" code="studentAffairs.student.view" variant="secondary" @click="onSearch">
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
      <DataTable
        :columns="columns"
        :rows="students"
        row-key="studentId"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.realName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-className="{ row }">
          {{ row.className || '—' }}
        </template>
        <template #cell-studentStatus="{ row }">
          <AppStatusTag :status="row.studentStatus" />
        </template>
        <template #cell-riskLevel="{ row }">
          <AppRiskTag :level="row.riskLevel || 'LOW'" size="sm" />
        </template>
        <template #cell-phone="{ row }">
          <AppSensitiveText :value="row.phoneMasked || '未设置'" />
        </template>
        <template #cell-updatedAt="{ row }">
          <AppDateDisplay :value="row.updatedAt" mode="datetime" empty-text="未设置" />
        </template>
        <template #cell-actions="{ row }">
          <AppPermissionButton :allowed="canBtn('studentAffairs.student.view')"
            code="studentAffairs.student.view"
            size="sm"
            variant="secondary"
            @click="$router.push(`/admin/student-affairs/profile/${row.studentId}`)"
          >
            查看画像
          </AppPermissionButton>
        </template>
      </DataTable>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppDateDisplay,
  AppExportButton,
  AppGlobalState,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSearchBox,
  AppSectionCard,
  AppSelect,
  AppSensitiveText,
  AppStatusTag
} from '@/components/common'
import { DataTable } from '@/components/business'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const RISK_FILTER_OPTIONS = [
  { value: '', label: '全部风险' },
  { value: 'LOW', label: '低风险' },
  { value: 'MEDIUM', label: '中风险' },
  { value: 'HIGH', label: '高风险' },
  { value: 'CRITICAL', label: '严重风险' }
]

// 列定义（key='actions' 的列点击不冒泡行点击，见 business/DataTable 约定）
const COLUMNS = [
  { key: 'student', title: '学生', width: '180px' },
  { key: 'className', title: '班级' },
  { key: 'studentStatus', title: '学籍状态' },
  { key: 'riskLevel', title: '风险' },
  { key: 'phone', title: '联系方式' },
  { key: 'updatedAt', title: '更新时间' },
  { key: 'actions', title: '操作', align: 'right', width: '120px' }
]

export default {
  name: 'StudentAffairsProfileListView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppDateDisplay,
    AppExportButton,
    AppGlobalState,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSearchBox,
    AppSectionCard,
    AppSelect,
    AppSensitiveText,
    AppStatusTag,
    DataTable
  },
  data() {
    return {
      RISK_FILTER_OPTIONS,
      columns: COLUMNS,
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
    canBtn(code) { return canCode(this.ctx, code) },
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
    // 筛选变更回到第一页再查，避免停留在越界页码
    onSearch() {
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
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
  width: 150px;
}
/* 两行单元格（主名 + 学号）：与教务房屋风格统一（mp-cell-main / mp-cell-sub） */
.mp-cell-main {
  font-weight: var(--font-weight-semibold);
  color: var(--t1);
  font-size: 14.5px;
}
.mp-cell-sub {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--t3);
  font-variant-numeric: tabular-nums;
}
</style>
