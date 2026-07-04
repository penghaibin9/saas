<template>
  <ModulePageShell
    title="实习学生"
    :subtitle="'共 ' + pagination.total + ' 人 · 手机号/学号默认脱敏展示'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的实习学生" description="可调整筛选条件后重新查询" />
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
          <button class="mp-link" :class="{ 'is-disabled': !can('batchAssignAdvisor') }" :title="reason('batchAssignAdvisor')" @click="batch('batchAssignAdvisor')">批量分配指导老师</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('batchRemind') }" :title="reason('batchRemind')" @click="batch('batchRemind')">批量提醒</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('exportGroup') }" :title="reason('exportGroup')" @click="batch('exportGroup')">导出所选</button>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ maskNo(row.studentNo) }} · {{ maskPhone(row.phone) }}</div>
        </template>
        <template #cell-enterprise="{ row }">
          <template v-if="row.enterpriseName">
            <div class="mp-cell-main">{{ row.enterpriseName }}</div>
            <div class="mp-cell-sub">{{ row.positionName }}</div>
          </template>
          <span v-else class="mp-note">未分配企业</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status" :label="row.statusLabel" dot />
        </template>
        <template #cell-checkin="{ row }">
          <StatusTag :type="row.checkinTone" :label="row.checkinSummary" />
        </template>
        <template #cell-risk="{ row }">
          <RiskTag v-if="row.riskLevel !== 'NONE'" :level="row.riskLevel" />
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/students/' + row.id)">查看</button>
          <button class="mp-link is-disabled" style="margin-left: var(--space-2)" :title="reason('editStudent')">编辑</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 实习学生列表（/admin/internship/students）：高级筛选 + 批量条 + 权限按钮 + 脱敏。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, RiskTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', classId: '', enterpriseId: '', status: '', riskLevel: '' })

export default {
  name: 'InternshipStudentListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState },
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
        { key: 'className', title: '班级' },
        { key: 'enterprise', title: '企业 / 岗位' },
        { key: 'advisorName', title: '指导老师' },
        { key: 'status', title: '实习状态' },
        { key: 'checkin', title: '近 7 日打卡' },
        { key: 'reportSummary', title: '周报' },
        { key: 'risk', title: '风险' },
        { key: 'actions', title: '操作', width: '120px' }
      ]
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号 / 企业' },
        { key: 'classId', label: '班级', type: 'select', options: o.classes },
        { key: 'enterpriseId', label: '企业', type: 'select', options: o.enterprises },
        { key: 'status', label: '实习状态', type: 'select', options: o.internshipStatus },
        { key: 'riskLevel', label: '风险等级', type: 'select', options: o.riskLevel }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createStudent', label: '＋ 新增实习学生', variant: 'primary' },
        { key: 'importStudents', label: '批量导入' },
        { key: 'exportGroup', label: '批量导出' }
      ]
        .filter((a) => pa[a.key] && pa[a.key].visible)
        .map((a) => ({ ...a, disabled: !pa[a.key].allowed, disabledReason: pa[a.key].reason }))
    }
  },
  created() {
    this.load()
  },
  methods: {
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    maskPhone(v) {
      return v ? v.slice(0, 3) + '****' + v.slice(-4) : '未登记'
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
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
      if (key === 'exportGroup') toast.success('导出任务已创建：字段已脱敏、文件含水印，本次导出已写入审计日志')
    },
    batch(key) {
      if (!this.can(key)) return
      if (key === 'batchRemind') toast.success('已向 ' + this.selected.length + ' 名学生发送提醒（站内信 + 小程序），已留痕')
      if (key === 'exportGroup') toast.success('已导出所选 ' + this.selected.length + ' 条（脱敏 + 水印），已留痕')
      this.selected = []
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await internshipApi.getStudents({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
