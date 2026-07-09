<template>
  <ModulePageShell
    title="企业与岗位"
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
      <EmptyState v-else-if="!rows.length" title="暂无企业" description="可通过「＋ 新增企业」或「导入」补充企业库" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-company="{ row }">
          <div class="mp-cell-main">{{ row.name }}</div>
          <div class="mp-cell-sub">{{ row.creditCode || '无信用代码' }} · {{ row.sourceLabel }}</div>
        </template>
        <template #cell-contact="{ row }">
          <template v-if="row.contactPerson">
            <div class="mp-cell-main">{{ row.contactPerson }}</div>
            <div class="mp-cell-sub">{{ row.contactPhoneMasked || '未登记' }}</div>
          </template>
          <span v-else class="mp-note">未登记</span>
        </template>
        <template #cell-coopStatus="{ row }">
          <StatusTag :type="row.coopStatusTone" :label="row.coopStatusLabel" dot />
          <span v-if="row.blacklist" class="ie-bl">黑名单</span>
        </template>
        <template #cell-qualification="{ row }">
          <StatusTag :type="row.qualificationStatus === 'PASSED' ? 'success' : (row.qualificationStatus === 'FAILED' ? 'danger' : 'default')" :label="row.qualificationLabel" />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/enterprises/' + row.id)">详情</button>
          <button v-if="row.coopStatus === 'PENDING'" class="mp-link" :class="{ 'is-disabled': !can('reviewEnterprise') }" :title="reason('reviewEnterprise')" style="margin-left: var(--space-2)" @click="askReview(row)">审核</button>
          <button v-else-if="row.coopStatus === 'ACTIVE'" class="mp-link" style="margin-left: var(--space-2)" @click="askCoop(row, 'SUSPEND')">暂停</button>
          <button v-else-if="row.coopStatus === 'SUSPENDED'" class="mp-link" style="margin-left: var(--space-2)" @click="askCoop(row, 'RESUME')">恢复</button>
          <button v-if="!row.blacklist && row.coopStatus !== 'ARCHIVED'" class="mp-link mp-link--danger" :class="{ 'is-disabled': !can('blacklistEnterprise') }" :title="reason('blacklistEnterprise')" style="margin-left: var(--space-2)" @click="askBlacklist(row, true)">拉黑</button>
          <button v-if="row.blacklist" class="mp-link" :class="{ 'is-disabled': !can('blacklistEnterprise') }" :title="reason('blacklistEnterprise')" style="margin-left: var(--space-2)" @click="askBlacklist(row, false)">移出黑名单</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑 -->
    <AppDrawer v-model:visible="editVisible" :title="editing ? '编辑企业' : '新增企业'">
      <form class="ie-form" @submit.prevent="submitEdit">
        <label class="ie-fld"><span class="ie-lbl">企业名称 <i>*</i></span><input v-model.trim="form.name" class="ie-in" placeholder="营业执照全称" /></label>
        <label class="ie-fld"><span class="ie-lbl">统一社会信用代码</span><input v-model.trim="form.creditCode" class="ie-in" placeholder="租户内唯一" /></label>
        <label class="ie-fld"><span class="ie-lbl">行业</span>
          <select v-model="form.industry" class="ie-in"><option value="">请选择</option><option v-for="o in industryOptions" :key="o.value" :value="o.value">{{ o.label }}</option></select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">来源</span>
          <select v-model="form.source" class="ie-in"><option value="">请选择</option><option v-for="o in sourceOptions" :key="o.value" :value="o.value">{{ o.label }}</option></select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">地区</span><input v-model.trim="form.region" class="ie-in" placeholder="省/市" /></label>
        <label class="ie-fld"><span class="ie-lbl">规模</span><input v-model.trim="form.scale" class="ie-in" placeholder="微/小/中/大型" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">详细地址</span><input v-model.trim="form.address" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">联系人</span><input v-model.trim="form.contactPerson" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">联系电话</span><input v-model.trim="form.contactPhone" class="ie-in" placeholder="敏感字段，列表默认脱敏" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="form.remark" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">{{ submitting ? '提交中…' : '保存' }}</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 导入：Excel 模板导入（推荐）+ 高级粘贴辅助 -->
    <AppDrawer v-model:visible="importVisible" title="导入企业">
      <div class="ie-form">
        <div class="ie-xlsx">
          <b>方式一 · Excel 模板导入（推荐）</b>
          <div class="ie-actions" style="margin: 6px 0 0">
            <button type="button" class="mp-btn" @click="downloadTemplate">下载 Excel 模板</button>
            <label class="mp-btn mp-btn--primary" style="cursor: pointer">
              上传 Excel
              <input type="file" accept=".xlsx" style="display: none" @change="onXlsxFile" />
            </label>
          </div>
          <p class="ie-hint">下载模板 → 按表头填写 → 上传 .xlsx，系统自动预校验；通过后可确认导入。</p>
        </div>
        <p class="ie-hint" style="margin-top: 8px"><b>方式二 · 高级粘贴导入</b>：适用于少量临时录入，正式批量导入请使用 Excel 模板。</p>
        <textarea v-model="importText" class="ie-in" rows="4" placeholder="企业名称,信用代码,行业,地区,联系人,联系电话" />
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="dryRunImport">粘贴预校验</button>
          <button v-if="importResult && importResult.errors.length" type="button" class="mp-btn" @click="downloadErrorXlsx">下载错误行 Excel</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="!importChecked || submitting" @click="confirmImport">确认导入</button>
        </div>
        <div v-if="importResult" class="ie-imp">
          <p>共 {{ importResult.total }} 行 · 通过 <b class="ie-ok">{{ importResult.validRows }}</b> · 失败 <b class="ie-bad">{{ importResult.invalidRows }}</b></p>
          <ul v-if="importResult.errors.length" class="ie-imp__errs">
            <li v-for="(e, i) in importResult.errors" :key="i">第 {{ e.rowNo }} 行 · {{ e.field }}：{{ e.message }}</li>
          </ul>
          <p v-else class="ie-ok">全部通过，可确认导入。</p>
        </div>
      </div>
    </AppDrawer>

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
/** 企业库列表（/admin/internship/enterprises）：筛选 + 增改抽屉 + 审核/暂停/黑名单状态机 + 真导入导出 + 脱敏。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', coopStatus: '', industry: '', region: '', blacklist: '' })
const EMPTY_FORM = () => ({ name: '', creditCode: '', industry: '', source: '', region: '', scale: '', address: '', contactPerson: '', contactPhone: '', remark: '' })
const ENTERPRISE_PANEL_PRESETS = {
  list: () => EMPTY_FILTERS(),
  detail: () => EMPTY_FILTERS(),
  contacts: () => EMPTY_FILTERS(),
  mentor: () => EMPTY_FILTERS(),
  qualification: () => ({ ...EMPTY_FILTERS(), coopStatus: 'PENDING' }),
  blacklist: () => ({ ...EMPTY_FILTERS(), blacklist: 'true' }),
  archive: () => ({ ...EMPTY_FILTERS(), coopStatus: 'ARCHIVED' }),
  stats: () => EMPTY_FILTERS(),
  cooperation: () => ({ ...EMPTY_FILTERS(), coopStatus: 'ACTIVE' }),
  positions: () => EMPTY_FILTERS()
}
const ENTERPRISE_PANEL_HINTS = {
  list: '合作企业主档 · 联系电话默认脱敏',
  detail: '点击行「详情」进入企业详情页',
  contacts: '联系人在企业详情页维护',
  mentor: '企业导师在企业详情页维护',
  qualification: '待审核企业 · 行内可「审核」资质',
  blacklist: '黑名单企业 · 可「移出黑名单」',
  archive: '已归档企业台账',
  stats: '统计能力待补强 · 当前为全量列表',
  cooperation: '合作中企业',
  positions: '关联岗位请前往岗位库筛选企业'
}

export default {
  name: 'InternshipEnterpriseListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, activePanel: 'list',
      rows: [], total: 0, page: 1, pageSize: 10,
      filters: EMPTY_FILTERS(),
      editVisible: false, editing: null, form: EMPTY_FORM(), formError: '',
      importVisible: false, importText: '', importChecked: false, importResult: null, importRows: [],
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null, extra: null },
      columns: [
        { key: 'company', title: '企业 / 信用代码' },
        { key: 'industry', title: '行业' },
        { key: 'region', title: '地区' },
        { key: 'contact', title: '联系人 / 电话' },
        { key: 'coopStatus', title: '合作状态' },
        { key: 'qualification', title: '资质' },
        { key: 'internCount', title: '实习生' },
        { key: 'actions', title: '操作', width: '220px' }
      ]
    }
  },
  computed: {
    perms() { return this.ctx.permissionActions || {} },
    coopStatusOptions() { return this.ctx.statusOptions.coopStatus || [] },
    sourceOptions() { return this.ctx.statusOptions.enterpriseSource || [] },
    industryOptions() { return this.ctx.statusOptions.enterpriseIndustry || [] },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '企业名称 / 信用代码 / 联系人' },
        { key: 'coopStatus', label: '合作状态', type: 'select', options: this.coopStatusOptions },
        { key: 'industry', label: '行业', type: 'select', options: this.industryOptions },
        { key: 'region', label: '地区', type: 'text', placeholder: '省/市' }
      ]
    },
    toolbarActions() {
      const pa = this.perms
      return [
        { key: 'create', label: '＋ 新增企业', variant: 'primary' },
        { key: 'import', label: '导入' },
        { key: 'export', label: '导出 Excel 台账' }
      ].filter((a) => !pa[a.key + 'Enterprise'] || pa[a.key + 'Enterprise'].visible !== false)
        .map((a) => {
          const p = pa[({ create: 'createEnterprise', import: 'importEnterprises', export: 'exportEnterprises' })[a.key]]
          return p ? { ...a, disabled: !p.allowed, disabledReason: p.reason } : a
        })
    },
    pageSubtitle() {
      const hint = ENTERPRISE_PANEL_HINTS[this.activePanel] || ENTERPRISE_PANEL_HINTS.list
      return `共 ${this.total} 家 · ${hint}`
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'list').toString())
      }
    }
  },
  methods: {
    applyPanel(panel) {
      const key = ENTERPRISE_PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (ENTERPRISE_PANEL_PRESETS[key] || ENTERPRISE_PANEL_PRESETS.list)()
      this.page = 1
      this.load()
    },
    can(key) { const p = this.perms[key]; return !!(p && p.allowed) },
    reason(key) { const p = this.perms[key]; return p && !p.allowed ? p.reason : '' },
    async load() {
      this.loading = true; this.error = ''
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      if (p.blacklist === '') delete p.blacklist
      else if (p.blacklist === 'true') p.blacklist = true
      const res = await internshipApi.getEnterprises(p)
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') { if (!this.can('createEnterprise')) return toast.error(this.reason('createEnterprise')); this.editing = null; this.form = EMPTY_FORM(); this.formError = ''; this.editVisible = true }
      if (key === 'import') { if (!this.can('importEnterprises')) return toast.error(this.reason('importEnterprises')); this.importText = ''; this.importResult = null; this.importChecked = false; this.importRows = []; this.importVisible = true }
      if (key === 'export') this.doExport()
    },
    async submitEdit() {
      this.formError = ''
      if (!this.form.name) { this.formError = '企业名称必填'; return }
      this.submitting = true
      try {
        const res = this.editing
          ? await internshipApi.updateEnterprise(this.editing.id, this.form)
          : await internshipApi.createEnterprise(this.form)
        if (res.code === 0) { toast.success('已保存并写入留痕'); this.editVisible = false; this.load() }
        else this.formError = res.message
      } finally { this.submitting = false }
    },
    askReview(row) {
      if (!this.can('reviewEnterprise')) return toast.error(this.reason('reviewEnterprise'))
      this.confirm = { visible: true, title: '企业资质审核', message: `确认「${row.name}」资质核验结果？通过→合作中，驳回→已驳回。`, type: 'primary', confirmText: '通过（资质合格）', requireReason: false, reasonLabel: '审核意见', action: 'REVIEW_APPROVE', row, extra: null }
    },
    askCoop(row, action) {
      const map = { SUSPEND: { t: '暂停合作', c: '确认暂停', type: 'warning' }, RESUME: { t: '恢复合作', c: '确认恢复', type: 'primary' } }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.name}」执行「${m.t}」？`, type: m.type, confirmText: m.c, requireReason: false, action: 'COOP_' + action, row, extra: null }
    },
    askBlacklist(row, on) {
      if (!this.can('blacklistEnterprise')) return toast.error(this.reason('blacklistEnterprise'))
      this.confirm = { visible: true, title: on ? '加入黑名单' : '移出黑名单', message: on ? `确认将「${row.name}」拉黑？拉黑后不再向学生推荐。` : `确认将「${row.name}」移出黑名单？恢复为合作中。`, type: on ? 'danger' : 'primary', confirmText: on ? '确认拉黑' : '确认移出', requireReason: on, reasonLabel: '拉黑原因', action: on ? 'BLACKLIST_ON' : 'BLACKLIST_OFF', row, extra: null }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action === 'REVIEW_APPROVE') res = await internshipApi.reviewEnterprise(row.id, { action: 'APPROVE', comment: reason || '' })
        else if (action.startsWith('COOP_')) res = await internshipApi.setEnterpriseCooperation(row.id, { action: action.slice(5), reason: reason || '' })
        else if (action === 'BLACKLIST_ON') res = await internshipApi.setEnterpriseBlacklist(row.id, { on: true, reason: reason || '' })
        else if (action === 'BLACKLIST_OFF') res = await internshipApi.setEnterpriseBlacklist(row.id, { on: false })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() }
        else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    },
    _parseImport() {
      return this.importText.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
        const p = l.split(',').map((x) => (x || '').trim())
        return {
          name: p[0], creditCode: p[1], industry: p[2], region: p[3],
          contactPerson: p[4] || '', contactPhone: p[5] || '', remark: p[8] || ''
        }
      })
    },
    downloadTemplate() {
      internshipApi.downloadEnterpriseTemplate().catch((e) => toast.error(e.message || '模板下载失败'))
    },
    async onXlsxFile(e) {
      const file = e.target.files && e.target.files[0]
      e.target.value = ''
      if (!file) return
      const res = await internshipApi.importEnterprisesXlsx(file)
      if (res.code !== 0) return toast.error(res.message)
      this.importRows = res.data.rows || []
      this.importResult = { total: res.data.total, validRows: res.data.validRows, invalidRows: res.data.invalidRows, errors: res.data.errors }
      this.importChecked = res.data.invalidRows === 0 && this.importRows.length > 0
      toast.success(`Excel 已解析 ${res.data.total} 行，通过 ${res.data.validRows} 行`)
    },
    async dryRunImport() {
      const rows = this._parseImport()
      if (!rows.length) return toast.error('请粘贴至少一行')
      this.importRows = rows
      const res = await internshipApi.importEnterprisesDryRun(rows)
      if (res.code === 0) { this.importResult = res.data; this.importChecked = res.data.invalidRows === 0 }
      else toast.error(res.message)
    },
    async confirmImport() {
      const rows = this.importRows && this.importRows.length ? this.importRows : this._parseImport()
      const res = await internshipApi.importEnterprisesConfirm(rows)
      if (res.code === 0) { toast.success(`已导入 ${res.data.created} 家（初始待审核）`); this.importVisible = false; this.load() }
      else toast.error(res.message)
    },
    async downloadErrorXlsx() {
      if (!this.importRows.length || !this.importResult?.errors?.length) return
      const res = await internshipApi.downloadEnterpriseImportErrors(this.importRows, this.importResult.errors)
      if (res.code === 0) {
        downloadXlsxFromApi(res.data, '企业导入错误行.xlsx')
        toast.success('错误行 Excel 已下载')
      } else toast.error(res.message)
    },
    async doExport() {
      if (!this.can('exportEnterprises')) return toast.error(this.reason('exportEnterprises'))
      const res = await internshipApi.downloadEnterpriseExport({ ...this.filters })
      if (res.code === 0) toast.success(`已导出 Excel 台账 ${res.data.rowCount} 家（脱敏，已写审计）`)
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.ie-bl { margin-left: var(--space-2); font-size: 11px; color: var(--danger, #dc2626); }
.mp-link--danger { color: var(--danger, #dc2626); }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-in:focus { outline: none; border-color: var(--pri, #2563eb); }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-hint { grid-column: 1 / -1; font-size: 12px; color: var(--t3, #64748b); margin: 0; }
.ie-xlsx { grid-column: 1 / -1; padding: 10px 12px; border: 1px dashed var(--line, #d9dee8); border-radius: 8px; font-size: 13px; background: var(--bg-subtle, #f8fafc); }
.ie-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-2); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ie-imp { grid-column: 1 / -1; font-size: 12px; }
.ie-imp__errs { margin: 4px 0 0; padding-left: 18px; color: var(--danger, #dc2626); }
.ie-ok { color: var(--success, #16a34a); }
.ie-bad { color: var(--danger, #dc2626); }
</style>
