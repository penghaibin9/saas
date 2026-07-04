<template>
  <ModulePageShell title="企业与岗位资源" subtitle="合作企业库 · 岗位资源 · 关联学生" :role-name="roleName" :data-scope-name="dataScopeName" watermark-purpose="企业岗位资源">
    <NoPermissionState v-if="noPermission" @back="$router.back()" />
    <template v-else>
      <div class="emp-cj-head">
        <div class="emp-tabs">
          <button type="button" class="emp-tabs__item" :class="{ 'is-active': tab === 'company' }" @click="switchTab('company')">合作企业</button>
          <button type="button" class="emp-tabs__item" :class="{ 'is-active': tab === 'job' }" @click="switchTab('job')">岗位资源</button>
        </div>
        <ModuleToolbar :actions="toolbarActions" :hint="`共 ${total} 条 · 操作全程留痕`" @action="onToolbar" />
      </div>

      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />

      <LoadingState v-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <EmptyState v-else-if="!rows.length" :title="tab === 'company' ? '暂无合作企业' : '暂无岗位资源'" description="可通过「新增 / 导入企业岗位」补充资源库" />
      <DataTable v-else :columns="tableColumns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-status="{ row }">
          <StatusTag
            :type="(tab === 'company' ? companyTagType : jobTagType)[row.status] || 'default'"
            :label="labelOf(tab === 'company' ? 'companyStatus' : 'jobStatus', row.status)"
            dot
          />
        </template>
        <template #cell-actions="{ row }">
          <TableActionColumn :actions="rowActions(row)" @action="(key) => onRowAction(key, row)" />
        </template>
      </DataTable>

      <!-- 新增 / 编辑 -->
      <EditDrawer
        v-model:visible="editVisible"
        :title="drawerTitle"
        :fields="editFields"
        :model="editing"
        :submitting="submitting"
        @submit="onEditSubmit"
      />

      <!-- 停用（逻辑删除） -->
      <DeleteConfirmDialog
        v-model:visible="disableVisible"
        :title="tab === 'company' ? '停用企业' : '停用岗位'"
        :message="disableTarget ? `确认停用「${disableTarget.name || disableTarget.title}」？停用后不再向学生推荐。` : ''"
        confirm-text="确认停用"
        reason-label="停用原因"
        :submitting="submitting"
        @confirm="onDisableConfirm"
      />

      <!-- 关联学生 -->
      <AppDrawer v-model:visible="relatedVisible" :title="related ? `关联学生与岗位 · ${related.company.name}` : '关联学生'">
        <template v-if="related">
          <h4 class="emp-rel-title">录用 / 签约学生（{{ related.students.length }}）</h4>
          <div v-for="s in related.students" :key="s.id" class="emp-rel-item" @click="$router.push(`/admin/employment/students/${s.id}`)">
            <b>{{ s.name }}</b>
            <span class="emp-inline-note">{{ s.className }} · {{ s.jobTitle || '—' }}</span>
            <StatusTag :type="destinationTagType[s.destinationType] || 'default'" :label="labelOf('destinationType', s.destinationType)" />
          </div>
          <EmptyState v-if="!related.students.length" title="暂无关联学生" />
          <h4 class="emp-rel-title" style="margin-top: var(--space-4)">在库岗位（{{ related.jobs.length }}）</h4>
          <div v-for="j in related.jobs" :key="j.id" class="emp-rel-item">
            <b>{{ j.title }}</b>
            <span class="emp-inline-note">{{ j.salaryRange }} · 需求 {{ j.headcount }} 人 · 已签 {{ j.signedCount }}</span>
            <StatusTag :type="jobTagType[j.status] || 'default'" :label="labelOf('jobStatus', j.status)" />
          </div>
        </template>
      </AppDrawer>

      <ImportDialog v-model:visible="importVisible" :template="importTemplate" :validate-fn="validateImportFn" :import-fn="confirmImportFn" @imported="load" />
      <ExportDialog
        v-model:visible="exportVisible"
        title="导出企业岗位"
        :options="exportOpts"
        :selected-count="0"
        :data-scope-name="dataScopeName"
        :export-fn="exportFn"
      />

      <AppDrawer v-model:visible="auditVisible" title="操作留痕 · 企业与岗位">
        <AuditTrailPanel :logs="auditLogs" />
      </AppDrawer>
    </template>
  </ModulePageShell>
</template>

<script>
/** 页面 8：/admin/employment/companies 企业与岗位资源（企业/岗位双 Tab，全套管理能力）。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, EmptyState, LoadingState, ErrorState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import { TableActionColumn, EditDrawer, ImportDialog, ExportDialog, AuditTrailPanel, DeleteConfirmDialog, NoPermissionState } from '@/modules/employment/components'
import * as api from '@/modules/employment/api/employment.api'
import { COMPANY_TAG_TYPE, JOB_TAG_TYPE, DESTINATION_TAG_TYPE, toLabelMap } from '@/modules/employment/constants/employment.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '' })

export default {
  name: 'EmploymentCompanyJobView',
  components: {
    ModulePageShell,
    ModuleToolbar,
    AdvancedFilter,
    DataTable,
    StatusTag,
    EmptyState,
    LoadingState,
    ErrorState,
    AppDrawer,
    TableActionColumn,
    EditDrawer,
    ImportDialog,
    ExportDialog,
    AuditTrailPanel,
    DeleteConfirmDialog,
    NoPermissionState
  },
  data() {
    return {
      ctx: null,
      tab: 'company',
      loading: true,
      error: '',
      submitting: false,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      filters: EMPTY_FILTERS(),
      statusOptions: {},
      companyColumns: [],
      jobColumns: [],
      companies: [],
      importTemplate: null,
      exportOpts: {},
      editVisible: false,
      editing: null,
      disableVisible: false,
      disableTarget: null,
      relatedVisible: false,
      related: null,
      importVisible: false,
      exportVisible: false,
      auditVisible: false,
      auditLogs: [],
      companyTagType: COMPANY_TAG_TYPE,
      jobTagType: JOB_TAG_TYPE,
      destinationTagType: DESTINATION_TAG_TYPE
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    perms() {
      return this.ctx?.permissionActions || {}
    },
    noPermission() {
      const p = this.perms['employment.record.view']
      return p ? !p.allowed : false
    },
    labelMaps() {
      return Object.fromEntries(Object.entries(this.statusOptions).map(([k, v]) => [k, toLabelMap(v)]))
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: this.tab === 'company' ? '企业名称 / 行业' : '岗位名称 / 企业' },
        {
          key: 'status',
          label: '状态',
          type: 'select',
          options: this.tab === 'company' ? this.statusOptions.companyStatus || [] : this.statusOptions.jobStatus || []
        }
      ]
    },
    tableColumns() {
      const cols = this.tab === 'company' ? this.companyColumns : this.jobColumns
      return cols.filter((c) => c.default || c.locked).map((c) => ({ key: c.key, title: c.title }))
    },
    drawerTitle() {
      if (this.tab === 'company') return this.editing ? '编辑企业' : '新增企业'
      return this.editing ? '编辑岗位' : '新增岗位'
    },
    toolbarActions() {
      const createKey = this.tab === 'company' ? 'employment.company.create' : 'employment.job.create'
      const create = this.perms[createKey]
      const imp = this.perms['employment.company.import']
      const exp = this.perms['employment.company.export']
      return [
        create && !create.visible
          ? null
          : {
              key: 'create',
              label: this.tab === 'company' ? '新增企业' : '新增岗位',
              variant: 'primary',
              disabled: create ? !create.allowed : false,
              disabledReason: create?.reason
            },
        imp && !imp.visible ? null : { key: 'import', label: '导入企业岗位', disabled: imp ? !imp.allowed : false, disabledReason: imp?.reason },
        exp && !exp.visible ? null : { key: 'export', label: '导出企业岗位', disabled: exp ? !exp.allowed : false, disabledReason: exp?.reason },
        { key: 'audit', label: '操作留痕' }
      ].filter(Boolean)
    },
    editFields() {
      if (this.tab === 'company') {
        return [
          { key: 'name', label: '企业名称', type: 'text', required: true },
          { key: 'creditCode', label: '统一社会信用代码', type: 'text', required: true },
          { key: 'industry', label: '行业', type: 'text', required: true },
          { key: 'nature', label: '企业性质', type: 'text' },
          { key: 'city', label: '所在城市', type: 'text' },
          { key: 'contactPerson', label: '联系人', type: 'text' },
          { key: 'contactPhone', label: '联系电话', type: 'text', placeholder: '敏感字段，列表默认脱敏' },
          {
            key: 'cooperationLevel',
            label: '合作级别',
            type: 'select',
            options: [
              { value: '深度合作', label: '深度合作' },
              { value: '常规合作', label: '常规合作' }
            ]
          }
        ]
      }
      return [
        {
          key: 'companyId',
          label: '所属企业',
          type: 'select',
          required: true,
          options: this.companies.map((c) => ({ value: c.id, label: c.name }))
        },
        { key: 'title', label: '岗位名称', type: 'text', required: true },
        { key: 'category', label: '岗位类别', type: 'text' },
        { key: 'salaryRange', label: '薪资区间', type: 'text', placeholder: '如 5k-7k' },
        { key: 'headcount', label: '需求人数', type: 'number' }
      ]
    }
  },
  async created() {
    await this.init()
  },
  methods: {
    labelOf(dict, value) {
      return this.labelMaps[dict]?.[value] || value || '—'
    },
    async init() {
      const [ctx, status, companyCols, jobCols, tpl, exp, companies] = await Promise.all([
        api.getEmploymentContext(),
        api.getStatusOptions(),
        api.getFieldColumns('companyList'),
        api.getFieldColumns('jobList'),
        api.getImportTemplate('companyList'),
        api.getExportOptions('companyList'),
        api.getCompanies({ page: 1, pageSize: 100 })
      ])
      if (ctx.code === 0) this.ctx = ctx.data
      if (status.code === 0) this.statusOptions = status.data
      if (companyCols.code === 0) this.companyColumns = companyCols.data
      if (jobCols.code === 0) this.jobColumns = jobCols.data
      if (tpl.code === 0) this.importTemplate = tpl.data
      if (exp.code === 0) this.exportOpts = exp.data
      if (companies.code === 0) this.companies = companies.data.list
      await this.load()
    },
    switchTab(tab) {
      if (this.tab === tab) return
      this.tab = tab
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    async load() {
      this.loading = true
      this.error = ''
      try {
        const fn = this.tab === 'company' ? api.getCompanies : api.getJobs
        const res = await fn({ ...this.filters, page: this.page, pageSize: this.pageSize })
        if (res.code === 0) {
          this.rows = res.data.list
          this.total = res.data.total
        } else this.error = res.message
      } catch (e) {
        this.error = e.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    search() {
      this.page = 1
      this.load()
    },
    reset() {
      this.filters = EMPTY_FILTERS()
      this.page = 1
      this.load()
    },
    turnPage(p) {
      this.page = p
      this.load()
    },
    rowActions(row) {
      const editKey = this.tab === 'company' ? 'employment.company.edit' : 'employment.job.edit'
      const disableKey = this.tab === 'company' ? 'employment.company.disable' : 'employment.job.disable'
      const edit = this.perms[editKey]
      const disable = this.perms[disableKey]
      const disabled = this.tab === 'company' ? row.status === 'DISABLED' : row.status === 'CLOSED'
      const actions = []
      if (this.tab === 'company') actions.push({ key: 'related', label: '关联学生' })
      actions.push(
        { key: 'edit', label: '编辑', disabled: edit ? !edit.allowed : false, disabledReason: edit?.reason, visible: edit ? edit.visible : true },
        {
          key: 'disable',
          label: '停用',
          danger: true,
          disabled: (disable ? !disable.allowed : false) || disabled,
          disabledReason: disabled ? '已停用' : disable?.reason,
          visible: disable ? disable.visible : true
        }
      )
      return actions
    },
    onRowAction(key, row) {
      if (key === 'related') this.openRelated(row)
      if (key === 'edit') {
        this.editing = row
        this.editVisible = true
      }
      if (key === 'disable') {
        this.disableTarget = row
        this.disableVisible = true
      }
    },
    async openRelated(row) {
      const res = await api.getCompanyRelatedStudents(row.id)
      if (res.code === 0) {
        this.related = res.data
        this.relatedVisible = true
      } else toast.error(res.message)
    },
    onToolbar(key) {
      if (key === 'create') {
        this.editing = null
        this.editVisible = true
      }
      if (key === 'import') this.importVisible = true
      if (key === 'export') this.exportVisible = true
      if (key === 'audit') this.openAudit()
    },
    async openAudit() {
      const res = await api.getAuditLogs({})
      if (res.code === 0) this.auditLogs = res.data.list.filter((l) => ['COMPANY', 'JOB', 'IMPORT', 'EXPORT'].includes(l.bizType))
      this.auditVisible = true
    },
    async onEditSubmit(form) {
      this.submitting = true
      try {
        let res
        if (this.tab === 'company') {
          res = this.editing ? await api.updateCompany(this.editing.id, form) : await api.createCompany(form)
        } else {
          res = this.editing ? await api.updateJob(this.editing.id, form) : await api.createJob(form)
        }
        if (res.code === 0) {
          toast.success('已保存并写入留痕')
          this.editVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    async onDisableConfirm({ reason }) {
      if (!this.disableTarget) return
      this.submitting = true
      try {
        const fn = this.tab === 'company' ? api.disableCompany : api.disableJob
        const res = await fn(this.disableTarget.id, { reason })
        if (res.code === 0) {
          toast.success('已停用（逻辑删除），原因已留痕')
          this.disableVisible = false
          this.load()
        } else toast.error(res.message)
      } finally {
        this.submitting = false
      }
    },
    validateImportFn(fileName) {
      return api.validateImport('companyList', fileName)
    },
    confirmImportFn(payload) {
      return api.confirmImport('companyList', payload)
    },
    exportFn(payload) {
      return api.createExport('companyList', payload)
    }
  }
}
</script>

<style scoped>
@import './employment-page.css';

.emp-cj-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.emp-rel-title {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}
.emp-rel-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) 0;
  border-bottom: 1px dashed var(--border-light);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.emp-rel-item:last-child {
  border-bottom: none;
}
.emp-rel-item .emp-inline-note {
  flex: 1;
}
</style>
