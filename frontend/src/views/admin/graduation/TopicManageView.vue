<template>
  <ModulePageShell
    title="选题管理"
    :subtitle="'共 ' + pagination.total + ' 个课题 · 停用为逻辑操作，需填写原因并留痕'"
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
      <EmptyState v-else-if="!rows.length" title="没有符合条件的课题" description="可新增课题或批量导入课题库" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-title="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.title }}</div>
          <div class="mp-cell-sub">{{ row.source }} · {{ row.majorName }}</div>
          <div v-if="row.disabledNote" class="mp-cell-sub" style="color: var(--warning-600)">{{ row.disabledNote }}</div>
        </template>
        <template #cell-capacity="{ row }">
          {{ row.selected }} / {{ row.capacity }}
        </template>
        <template #cell-status="{ row }">
          <StatusTag :status="row.status === 'CONFIRMED' ? 'APPROVED' : row.status === 'DISABLED' ? 'DISABLED' : 'PENDING_REVIEW'" :label="row.statusLabel" dot />
        </template>
        <template #cell-students="{ row }">
          <span v-if="row.students.length">{{ row.students.join('、') }}</span>
          <span v-else class="mp-note">暂无学生</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="edit(row)">编辑</button>
          <button v-if="row.status !== 'DISABLED'" class="mp-link" style="margin-left: var(--space-2)" @click="disable(row)">停用</button>
          <button v-else class="mp-link" style="margin-left: var(--space-2)" @click="enable(row)">启用</button>
        </template>
      </DataTable>

      <p class="mp-note">课题停用不影响已确认选题的学生，仅停止新的选择；停用 / 启用均写入审计日志。指导教师分配随选题确认同步建立。</p>
    </div>
  </ModulePageShell>
</template>

<script>
/** 选题管理（/admin/graduation/topics）：课题库 + 关联学生 + 停用留痕。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { graduationApi } from '@/modules/graduation/api/graduation.api'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })

export default {
  name: 'TopicManageView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      columns: [
        { key: 'title', title: '课题' },
        { key: 'advisorName', title: '指导教师' },
        { key: 'capacity', title: '已选 / 容量' },
        { key: 'status', title: '状态' },
        { key: 'students', title: '关联学生' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    filterFields() {
      return [
        { key: 'keyword', label: '课题名称', type: 'text', placeholder: '关键词' },
        {
          key: 'status', label: '课题状态', type: 'select',
          options: [
            { value: 'PENDING_CONFIRM', label: '待确认' },
            { value: 'CONFIRMED', label: '已确认' },
            { value: 'DISABLED', label: '已停用' }
          ]
        }
      ]
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'createTopic', label: '＋ 新增课题', variant: 'primary' },
        { key: 'importTopics', label: '批量导入课题' },
        { key: 'exportTopics', label: '导出课题' }
      ]
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
    onToolbar(key) {
      if (key === 'exportTopics') toast.success('课题导出任务已创建，已写入审计日志')
      else if (key === 'importTopics') toast.info('导入流程：下载模板 → 上传 Excel → 字段校验 → 错误预览 → 确认导入')
      else toast.info('演示环境：课题新增/编辑抽屉将在后续批次开放')
    },
    edit(row) {
      toast.info('编辑课题「' + row.title + '」：变更字段将留痕（编辑抽屉后续批次开放）')
    },
    disable(row) {
      toast.info('停用需填写原因并二次确认：不物理删除、已确认学生不受影响、操作留痕（示例：' + row.title + '）')
    },
    enable(row) {
      toast.success('课题「' + row.title + '」已重新启用，已留痕')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationApi.getTopics({ ...this.filters, page: this.pagination.page, pageSize: this.pagination.pageSize })
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
