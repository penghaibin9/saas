<template>
  <ModulePageShell
    title="打卡与请假"
    :subtitle="'待核实 ' + pendingCount + ' 条 · 学生端提交的打卡异常说明会同步到这里'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton :export-fn="exportFn" :has-permission="exportPermission">⬇ 导出异常记录</AppExportButton>
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="今日暂无待处理打卡异常" description="当前数据范围内学生打卡全部正常，可查看历史处理记录" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        selectable
        v-model:selected="selected"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #batch-actions>
          <button class="mp-link" :class="{ 'is-disabled': batchHasMock }" :title="batchHasMock ? '所选含模拟定位记录，禁止批量标记合理，请逐条核实' : ''" @click="batchMark">批量标记合理</button>
          <button class="mp-link" @click="exportSelected">导出所选</button>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }} · {{ row.enterpriseName }}</div>
        </template>
        <template #cell-type="{ row }">
          <AppStatusTag :type="row.type === 'MISSING' ? 'warning' : 'danger'">{{ row.typeLabel }}</AppStatusTag>
          <div v-if="row.streak" class="mp-cell-sub" style="color: var(--danger-600)">{{ row.streak }}</div>
        </template>
        <template #cell-deviceRisk="{ row }">
          <span :style="row.deviceRisk !== '正常' ? 'color: var(--danger-600); font-weight: 500' : ''">{{ row.deviceRisk }}</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/exceptions/' + row.id)">
            {{ row.status === 'COMPLETED' ? '查看留痕' : '处理' }}
          </button>
        </template>
      </DataTable>

      <p class="mp-note">处理规则：超范围不直接定性作弊，允许学生说明；模拟定位命中建议转风险；缺卡与审批中请假自动联动豁免。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 打卡异常列表（/admin/internship/exceptions）：P11 → T18/T19 → PC 完整处理入口。 */
import {
  ModulePageShell, AdvancedFilter, DataTable,
  LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppStatusTag, AppExportButton } from '@/components/common'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { attendanceApi } from '@/modules/internship/api/attendance.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '' })

export default {
  name: 'AttendanceExceptionListView',
  components: { ModulePageShell, AdvancedFilter, DataTable, AppStatusTag, AppExportButton, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: [],
      batchSubmitting: false,
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'date', title: '日期 / 时段' },
        { key: 'type', title: '异常类型' },
        { key: 'distance', title: '距打卡点' },
        { key: 'deviceRisk', title: '设备风险' },
        { key: 'note', title: '学生说明' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '90px' }
      ]
    }
  },
  computed: {
    pendingCount() {
      return this.rows.filter((r) => r.status === 'PENDING_HANDLE').length
    },
    batchHasMock() {
      return this.rows.some((r) => this.selected.includes(r.id) && r.type === 'MOCK_LOCATION')
    },
    filterFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '学生', type: 'text', placeholder: '姓名' },
        { key: 'type', label: '异常类型', type: 'select', options: o.exceptionType },
        {
          key: 'status', label: '处理状态', type: 'select',
          options: [
            { value: 'PENDING_HANDLE', label: '待核实' },
            { value: 'COMPLETED', label: '已处理' }
          ]
        }
      ]
    },
    exportPermission() {
      const pa = this.ctx.permissionActions?.exportExceptions
      return !pa || pa.allowed
    }
  },
  created() {
    this.load()
  },
  methods: {
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    search() {
      this.pagination.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.pagination.page = 1
      this.load()
    },
    exportFn() {
      return attendanceApi.exportExceptions({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
    },
    batchMark() {
      if (this.batchHasMock || !this.selected.length || this.batchSubmitting) return
      this.batchSubmitting = true
      attendanceApi.batchHandleExceptions(this.selected, {
        action: 'REASONABLE',
        comment: '经批量核实，打卡情况合理'
      }).then((res) => {
        if (res.code === 0) {
          const d = res.data || {}
          toast.success(`已处理 ${d.processedCount || 0} 条，跳过 ${d.skippedCount || 0} 条（已留痕）`)
          this.selected = []
          this.load()
        } else {
          toast.error(res.message || '批量处理失败')
        }
      }).finally(() => { this.batchSubmitting = false })
    },
    async exportSelected() {
      if (!this.selected.length) {
        toast.error('请先选择要导出的记录')
        return
      }
      const res = await attendanceApi.exportExceptions({ ids: this.selected })
      if (res.code === 0) {
        downloadXlsxFromApi(res.data, res.data.filename || '打卡异常所选台账.xlsx')
        toast.success(`已导出所选 ${this.selected.length} 条异常记录，已留痕`)
        this.selected = []
      } else {
        toast.error(res.message || '导出失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getAttendanceExceptions({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
</style>
