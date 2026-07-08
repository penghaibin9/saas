<template>
  <ModulePageShell
    title="选题管理"
    :subtitle="pageSubtitle"
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
      <EmptyState v-else-if="!rows.length" title="暂无已入池课题" description="请先在「题目库」申报并审核通过，或导入 Excel" />
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

    <AppDrawer v-model:visible="editVisible" :title="editing ? '编辑课题' : '编辑课题'">
      <form class="ie-form" @submit.prevent="submitEdit">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目名称 <i>*</i></span>
          <input v-model.trim="form.title" class="ie-in" />
        </label>
        <label class="ie-fld"><span class="ie-lbl">指导教师</span><input v-model.trim="form.advisorName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">容量</span>
          <input v-model.number="form.capacity" type="number" min="1" max="99" class="ie-in" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">题目要求</span>
          <textarea v-model.trim="form.requirements" class="ie-in" rows="3" />
        </label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <AppDrawer v-model:visible="detailVisible" :title="detail ? detail.title : '课题详情'">
      <template v-if="detail">
        <div class="gb-kv"><span>指导教师</span><span>{{ detail.advisorName || '—' }}</span></div>
        <div class="gb-kv"><span>容量</span><span>{{ detail.selected }}/{{ detail.capacity }}</span></div>
        <div class="gb-sec">
          <p class="ie-hint">已选学生</p>
          <EmptyState v-if="!assigned.length" title="暂无" />
          <ul v-else class="gb-trail">
            <li v-for="s in assigned" :key="s.id" class="gb-trail__item">
              <span>{{ s.name }}（{{ s.studentNo }}）</span>
            </li>
          </ul>
        </div>
      </template>
    </AppDrawer>

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
  </ModulePageShell>
</template>

<script>
/** 选题管理（/admin/graduation/topics）：已入池课题 + 关联学生 + 停用/分配；接 gd-topics 真实 API。 */
import {
  ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable,
  StatusTag, LoadingState, ErrorState, EmptyState
} from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { GD_TOPIC_STATUS } from '@/modules/graduation/constants/graduation-topic.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', dateStart: '', dateEnd: '' })

export default {
  name: 'TopicManageView',
  components: {
    ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, AppExcelImportDrawer
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], filters: EMPTY_FILTERS(),
      pagination: { page: 1, pageSize: 10, total: 0 },
      editVisible: false, editing: null, form: { title: '', advisorName: '', capacity: 1, requirements: '' }, formError: '',
      detailVisible: false, detail: null, assigned: [],
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null }
    }
  },
  computed: {
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
        { key: 'importTopics', label: '导入 Excel' },
        { key: 'exportTopics', label: '导出 Excel' }
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
      if (key === 'exportTopics') this.doExport()
    },
    openEdit(row) {
      this.editing = row
      this.form = { title: row.title, advisorName: row.advisorName || '', capacity: row.capacity, requirements: row.requirements || '' }
      this.formError = ''
      this.editVisible = true
    },
    async submitEdit() {
      if (!this.form.title || this.form.title.length < 2) { this.formError = '题目至少2字'; return }
      this.submitting = true
      const r = await gdTopicApi.updateTopic(this.editing.id, this.form)
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success('已保存')
      this.editVisible = false
      this.load()
    },
    async openDetail(row) {
      const d = await gdTopicApi.getTopicDetail(row.id)
      if (d.code !== 0) { toast.error(d.message); return }
      this.detail = d.data
      const a = await gdTopicApi.getAssignedStudents(row.id)
      this.assigned = a.code === 0 ? (a.data || []) : []
      this.detailVisible = true
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
    async doExport() {
      const p = this.buildParams()
      delete p.page
      delete p.pageSize
      const r = await gdTopicApi.downloadExport(p)
      if (r.code !== 0) toast.error(r.message || '导出失败')
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gb-kv { display: flex; justify-content: space-between; padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
.gb-sec { margin-top: var(--space-4); }
.gb-trail { list-style: none; padding: 0; margin: 0; }
.gb-trail__item { padding: var(--space-2) 0; border-bottom: 1px solid var(--color-border-subtle); }
</style>
