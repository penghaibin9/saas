<template>
  <ModulePageShell
    title="风险学生"
    :subtitle="'风险来源统一挂 INT-R 编码 · 关闭风险需填写原因并留痕'"
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
      <EmptyState v-else-if="!rows.length" title="当前数据范围内暂无风险学生" description="系统预警（INT-R01~R17）命中后会自动生成风险记录" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.className }}</div>
        </template>
        <template #cell-source="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.source }}</div>
          <div class="mp-cell-sub">{{ row.sourceDetail }}</div>
        </template>
        <template #cell-level="{ row }">
          <RiskTag :level="row.level" />
        </template>
        <template #cell-deadline="{ row }">
          <span :style="isUrgent(row.deadline) ? 'color: var(--danger-600); font-weight: 500' : ''">{{ row.deadline }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/students/' + row.internId)">查看学生</button>
          <button class="mp-link" style="margin-left: var(--space-2)" @click="remind(row)">提醒</button>
        </template>
      </DataTable>

      <p class="mp-note">跟进 / 升级 / 关闭风险入口在学生实习详情的风险页签内；关闭为审慎操作：原因必填 + 二次确认 + 永久留痕。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 风险学生列表（/admin/internship/risks）：风险等级 / 跟进状态 / 责任人 / 处理期限。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, RiskTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ level: '', status: '' })

export default {
  name: 'InternshipRiskView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'student', title: '学生' },
        { key: 'source', title: '风险来源' },
        { key: 'level', title: '等级' },
        { key: 'owner', title: '责任人' },
        { key: 'deadline', title: '处理期限' },
        { key: 'lastFollow', title: '最近跟进' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '140px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'level', label: '风险等级', type: 'select', options: this.ctx.statusOptions.riskLevel },
        {
          key: 'status', label: '跟进状态', type: 'select',
          options: [
            { value: 'PENDING_HANDLE', label: '待处理' },
            { value: 'PROCESSING', label: '跟进中' }
          ]
        }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'batchRemind', label: '批量发送提醒' },
        { key: 'exportRiskList', label: '导出风险名单' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    isUrgent(d) {
      return d && d <= '07-05'
    },
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
    onToolbar(key) {
      if (key === 'batchRemind') toast.success('已向全部风险学生责任人发送提醒，已留痕')
      if (key === 'exportRiskList') toast.success('风险名单导出任务已创建（仅限当前数据范围、含水印），已留痕')
    },
    remind(row) {
      toast.success('已提醒 ' + row.owner + ' 跟进 ' + row.studentName + ' 的风险记录，已留痕')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getRiskStudents({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
