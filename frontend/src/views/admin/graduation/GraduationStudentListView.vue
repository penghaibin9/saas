<template>
  <ModulePageShell
    title="毕设学生"
    :subtitle="'共 ' + pagination.total + ' 人 · 学号/手机号默认脱敏展示'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的毕设学生" description="可调整筛选条件后重新查询" />
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
          <button class="mp-link" :class="{ 'is-disabled': !can('batchAssignAdvisor') }" :title="reason('batchAssignAdvisor')" @click="batch('batchAssignAdvisor')">批量分配指导教师</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('batchRemind') }" :title="reason('batchRemind')" @click="batch('batchRemind')">批量提醒</button>
          <button class="mp-link" :class="{ 'is-disabled': !can('batchArchive') }" :title="reason('batchArchive')" @click="batch('batchArchive')">批量归档</button>
          <button class="mp-link" @click="batch('exportStats')">导出所选</button>
        </template>
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ maskNo(row.studentNo) }} · {{ row.className }}</div>
        </template>
        <template #cell-topic="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.topicTitle }}</div>
          <div class="mp-cell-sub">指导教师：{{ row.advisorName }}</div>
        </template>
        <template #cell-stage="{ row }">
          <StatusTag :type="stageTone(row.stage)" :label="row.stageLabel" dot />
        </template>
        <template #cell-material="{ row }">
          <div style="font-size: var(--font-size-sm)">{{ row.materialSummary }}</div>
          <div v-if="row.plagiarismRate !== '—'" class="mp-cell-sub">
            查重 <span :style="row.plagiarismTone === 'danger' ? 'color: var(--danger-600); font-weight: 500' : ''">{{ row.plagiarismRate }}</span>
          </div>
        </template>
        <template #cell-risk="{ row }">
          <RiskTag v-if="row.riskLevel !== 'NONE'" :level="row.riskLevel" />
          <span v-else class="mp-note">无</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/graduation/students/' + row.id)">查看</button>
          <button
            class="mp-link"
            :class="{ 'is-disabled': row.stage === 'ARCHIVED' }"
            :title="row.stage === 'ARCHIVED' ? '已归档记录只读，需先重新打开归档' : reason('editProject')"
            style="margin-left: var(--space-2)"
          >编辑</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 毕设学生列表（/admin/graduation/students）：节点状态 / 材料状态 / 风险筛选 + 批量条。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, RiskTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', classId: '', advisorId: '', stage: '', riskLevel: '' })
const STAGE_TONE = {
  TOPIC_SELECTING: 'default',
  TASKBOOK_CONFIRM: 'info',
  GUIDING: 'processing',
  MIDTERM: 'warning',
  FINAL_CHECK: 'processing',
  DEFENSE: 'warning',
  ARCHIVED: 'success'
}

export default {
  name: 'GraduationStudentListView',
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
        { key: 'topic', title: '课题 / 指导教师' },
        { key: 'stage', title: '节点状态' },
        { key: 'material', title: '材料 / 查重' },
        { key: 'risk', title: '风险' },
        { key: 'actions', title: '操作', width: '120px' }
      ]
    }
  },
  computed: {
    filterFields() {
      const o = this.ctx.statusOptions
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '姓名 / 学号 / 课题' },
        { key: 'classId', label: '班级', type: 'select', options: o.classes },
        { key: 'advisorId', label: '指导教师', type: 'select', options: o.advisors },
        { key: 'stage', label: '节点状态', type: 'select', options: o.stage },
        { key: 'riskLevel', label: '风险等级', type: 'select', options: o.riskLevel }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createProject', label: '＋ 新增毕设记录', variant: 'primary' },
        { key: 'importStudents', label: '批量导入' },
        { key: 'exportStats', label: '批量导出' }
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
    stageTone(stage) {
      return STAGE_TONE[stage] || 'default'
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
      if (key === 'exportStats') toast.success('导出任务已创建（脱敏 + 水印），已写入审计日志')
      else if (key === 'importStudents') toast.info('导入流程：下载模板 → 上传 Excel → 字段校验 → 错误预览 → 确认导入（本批次演示后续开放）')
      else toast.info('演示环境：该操作将在后续批次开放')
    },
    batch(key) {
      if (key !== 'exportStats' && !this.can(key)) return
      const n = this.selected.length
      if (key === 'batchAssignAdvisor') toast.success('已为 ' + n + ' 名学生发起指导教师分配（带教上限校验通过），已留痕')
      if (key === 'batchRemind') toast.success('已向 ' + n + ' 名学生发送节点提醒，已留痕')
      if (key === 'batchArchive') toast.info('批量归档前将检查缺失材料：材料不齐者自动剔除并列出原因')
      if (key === 'exportStats') toast.success('已导出所选 ' + n + ' 条（脱敏 + 水印），已留痕')
      this.selected = []
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getStudents({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
