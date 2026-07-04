<template>
  <ModulePageShell
    title="打卡异常"
    :subtitle="'待核实 ' + pendingCount + ' 条 · 承接学生小程序 P11 打卡异常说明'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
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
          <StatusTag :type="row.type === 'MISSING' ? 'warning' : 'danger'" :label="row.typeLabel" />
          <div v-if="row.streak" class="mp-cell-sub" style="color: var(--danger-600)">{{ row.streak }}</div>
        </template>
        <template #cell-deviceRisk="{ row }">
          <span :style="row.deviceRisk !== '正常' ? 'color: var(--danger-600); font-weight: 500' : ''">{{ row.deviceRisk }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/exceptions/' + row.id)">
            {{ row.status === 'COMPLETED' ? '查看留痕' : '处理' }}
          </button>
        </template>
      </DataTable>

      <p class="mp-note">规则（冻结）：超范围不直接定性作弊，允许学生说明；模拟定位命中建议转风险；缺卡与审批中请假自动联动豁免。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 打卡异常列表（/admin/internship/exceptions）：P11 → T18/T19 → PC 完整处理入口。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', type: '', status: '' })

export default {
  name: 'AttendanceExceptionListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      selected: [],
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
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [{ key: 'exportExceptions', label: '导出异常记录' }]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
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
    onToolbar() {
      toast.success('异常记录导出任务已创建（脱敏 + 水印），已写入审计日志')
    },
    batchMark() {
      if (this.batchHasMock) return
      toast.success('已批量标记 ' + this.selected.length + ' 条为合理，处理结果已同步学生端并留痕')
      this.selected = []
      this.load()
    },
    exportSelected() {
      toast.success('已导出所选 ' + this.selected.length + ' 条异常记录，已留痕')
      this.selected = []
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
