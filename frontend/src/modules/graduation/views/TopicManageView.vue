<template>
  <ModulePageShell
    title="选题管理"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="gd-actions">
        <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
        <AppExportButton :export-fn="exportTopicsFn">导出 Excel</AppExportButton>
      </div>
    </template>

    <div class="mp-stack">
      <GraduationBatchStrip />
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <!-- 空态分两种：筛选无果 ≠ 题目库还没入池。后者是跨页依赖，老师最容易卡在这里，
           所以直接给去题目库的按钮，而不是只写一句「请先在题目库申报」。 -->
      <EmptyState
        v-else-if="!rows.length && filtered"
        title="没有符合条件的课题"
        description="当前筛选条件下没有课题。可以放宽条件，或清空筛选看全部。"
      >
        <template #actions>
          <button class="mp-btn" @click="reset">清空筛选</button>
        </template>
      </EmptyState>
      <EmptyState
        v-else-if="!rows.length"
        title="还没有课题入池"
        description="学生能选的题，都来自题目库。老师申报的题目要先经管理员审核通过才会入池，入池后才会出现在这里、学生才选得到。"
      >
        <template #actions>
          <button class="mp-btn mp-btn--primary" @click="$router.push('/admin/graduation/topic-lib?panel=pending')">去审核待审题目</button>
          <button class="mp-btn" @click="$router.push('/admin/graduation/topic-lib?panel=list')">去题目库</button>
          <button class="mp-btn" @click="$router.push('/admin/help?topic=gd-card-topic-review')">怎么审核题目？</button>
        </template>
      </EmptyState>
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-title="{ row }">
          <div class="mp-cell-main" style="font-size: var(--font-size-sm)">{{ row.title }}</div>
          <div class="mp-cell-sub">{{ row.sourceLabel }} · {{ row.majorName || '—' }}</div>
          <div v-if="row.disabledNote" class="mp-cell-sub" style="color: var(--warning-600)">{{ row.disabledNote }}</div>
        </template>
        <template #cell-capacity="{ row }">
          <span :class="{ 'mp-note': row.isFull }">{{ row.selected }} / {{ row.capacity }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
        </template>
        <template #cell-students="{ row }">
          <span v-if="row.studentNames && row.studentNames.length">{{ row.studentNames.join('、') }}</span>
          <span v-else class="mp-note">暂无学生</span>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <button v-if="canEdit(row)" class="mp-link" style="margin-left: var(--space-2)" @click="openEdit(row)">编辑</button>
          <button
            v-if="row.status === 'CONFIRMED'"
            class="mp-link"
            style="margin-left: var(--space-2)"
            @click="askDisable(row)"
          >停用</button>
          <button
            v-if="row.status === 'DISABLED'"
            class="mp-link"
            style="margin-left: var(--space-2)"
            @click="askEnable(row)"
          >启用</button>
          <button
            class="mp-link"
            style="margin-left: var(--space-2)"
            @click="goAssign(row)"
          >分配学生</button>
        </template>
      </DataTable>
      <p class="mp-note">展示已审核入池课题及关联学生；停用不影响已选学生；分配请跳转「毕设学生 · 未选题」。</p>
    </div>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入题目库"
      template-name="题目库导入模板.xlsx"
      :required-fields="['题目名称']"
      :preview-fields="['title', 'advisorName', 'capacity', 'submitReview']"
      :download-template-fn="() => gdTopicApi.downloadImportTemplate()"
      :upload-fn="(file) => gdTopicApi.uploadImportXlsx(file)"
      :confirm-fn="({ rows }) => gdTopicApi.importConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => gdTopicApi.downloadImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel"
      :submitting="submitting"
      @confirm="onConfirm"
    />
    <!-- 首次进入本模块时的 4 步说明；「已看过」存后端偏好，顶栏「?」可重看 -->
    <AppPageGuide guide-key="graduation.gd-topics" />
  </ModulePageShell>
</template>

<script>
/** 选题管理（/admin/graduation/topics）：已入池课题 + 关联学生 + 停用/分配；接 gd-topics 真实 API。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExportButton, AppPageGuide } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { GD_TOPIC_STATUS } from '@/modules/graduation/constants/graduation-topic.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', dateStart: '', dateEnd: '' })

import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'

export default {
  name: 'TopicManageView',
  components: { AppPageGuide, GraduationBatchStrip,
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppExcelImportDrawer, AppExportButton
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null }
    }
  },
  computed: {
    /** 是否处于筛选态：用于区分「筛选没结果」和「题目库真的还没入池」两种空态 */
    filtered() {
      const f = this.filters
      return !!(f.keyword || f.status || f.dateStart || f.dateEnd)
    },
    columns() {
      return [
        { key: 'title', title: '课题' },
        { key: 'advisorName', title: '指导教师' },
        { key: 'capacity', title: '已选 / 容量' },
        { key: 'status', title: '状态' },
        { key: 'students', title: '关联学生' },
        { key: 'actions', title: '操作', width: '240px' }
      ]
    },
    filterFields() {
      return [
        { key: 'keyword', label: '课题名称', type: 'text', placeholder: '关键词' },
        { key: 'status', label: '课题状态', type: 'select', options: GD_TOPIC_STATUS.filter((s) => s.value !== 'ARCHIVED') },
        {
          key: 'date', label: '选题时间', type: 'daterange',
          startKey: 'dateStart', endKey: 'dateEnd',
          memoryKey: 'graduation.topics.dateRange', emptyLabel: '全部时间'
        }
      ]
    },
    toolbarActions() {
      return [
        { key: 'topicLib', label: '题目库申报', variant: 'primary' },
        { key: 'importTopics', label: '导入 Excel' }
      ]
    },
    pageSubtitle() {
      return `共 ${this.pagination.total} 个已入池课题 · 课题停用不影响已确认学生`
    }
  },
  created() {
    this.load()
  },
  methods: {
    canEdit(row) {
      return row.status !== 'ARCHIVED' && row.reviewStatus !== 'PENDING_REVIEW' && !(row.selected > 0 && row.reviewStatus === 'APPROVED')
    },
    buildParams() {
      return {
        page: this.pagination.page,
        pageSize: this.pagination.pageSize,
        keyword: this.filters.keyword || undefined,
        status: this.filters.status || undefined,
        reviewStatus: 'APPROVED',
        archiveView: 'active'
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await gdTopicApi.getTopics(this.buildParams())
      this.loading = false
      if (res.code !== 0) { this.error = res.message; return }
      this.rows = res.data.list
      this.pagination.total = res.data.total
    },
    onPageChange(page) { this.pagination.page = page; this.load() },
    search() { this.pagination.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.pagination.page = 1; this.load() },
    onToolbar(key) {
      if (key === 'topicLib') this.$router.push('/admin/graduation/topic-lib?panel=list')
      if (key === 'importTopics') this.importVisible = true
    },
    openEdit(row) {
      this.$router.push(`/admin/graduation/topics/${row.id}/edit`)
    },
    openDetail(row) {
      this.$router.push(`/admin/graduation/topics/${row.id}`)
    },
    askDisable(row) {
      this.confirm = { visible: true, title: '停用课题', message: `停用「${row.title}」后不可再分配新学生。`, type: 'warning', confirmText: '停用', requireReason: true, reasonLabel: '停用原因', action: 'disable', row }
    },
    askEnable(row) {
      this.confirm = { visible: true, title: '启用课题', message: `确认重新启用「${row.title}」？`, type: 'primary', confirmText: '启用', requireReason: false, action: 'enable', row }
    },
    async onConfirm({ reason }) {
      const row = this.confirm.row
      this.submitting = true
      let r = { code: 1 }
      if (this.confirm.action === 'disable') r = await gdTopicApi.disableTopic(row.id, { reason })
      if (this.confirm.action === 'enable') r = await gdTopicApi.enableTopic(row.id)
      this.submitting = false
      if (r.code !== 0) { toast.error(r.message); return }
      toast.success('操作成功')
      this.confirm.visible = false
      this.load()
    },
    goAssign() {
      this.$router.push('/admin/graduation/students?panel=topic')
    },
    onImported() { this.importVisible = false; toast.success('导入完成'); this.load() },
    exportTopicsFn() {
      const p = this.buildParams()
      delete p.page
      delete p.pageSize
      return gdTopicApi.exportTopics(p)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gd-actions { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
</style>
