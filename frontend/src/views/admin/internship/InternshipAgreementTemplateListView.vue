<template>
  <ModulePageShell
    title="实习协议模板库"
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
      <EmptyState v-else-if="!rows.length" title="暂无协议模板" description="可「＋ 新建模板」创建实习三方协议 / 安全责任书等模板" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}<span v-if="row.isDefault" class="at-default">默认</span></div>
          <div class="mp-cell-sub">{{ row.category || '未分类' }} · {{ row.version }}</div>
        </template>
        <template #cell-scope="{ row }">
          <span class="mp-cell-sub">{{ row.scopeSummary }}</span>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openDetail(row)">详情</button>
          <button v-if="row.status !== 'ARCHIVED'" class="mp-link" style="margin-left: var(--space-2)" @click="openEdit(row)">编辑</button>
          <button v-if="['DRAFT', 'DISABLED'].includes(row.status)" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'ENABLE')">启用</button>
          <button v-else-if="row.status === 'ENABLED'" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'DISABLE')">停用</button>
          <button v-if="row.status === 'ENABLED' && !row.isDefault" class="mp-link" style="margin-left: var(--space-2)" @click="askDefault(row, true)">设默认</button>
          <button v-if="row.isDefault" class="mp-link" style="margin-left: var(--space-2)" @click="askDefault(row, false)">取消默认</button>
          <button v-if="row.status !== 'ARCHIVED'" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askStatus(row, 'ARCHIVE')">归档</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑 -->
    <AppDrawer v-model:visible="editVisible" :title="editing ? '编辑协议模板' : '新建协议模板'">
      <form class="ie-form" @submit.prevent="submitEdit">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">模板名称 <i>*</i></span><input v-model.trim="form.name" class="ie-in" placeholder="如 顶岗实习三方协议" /></label>
        <label class="ie-fld"><span class="ie-lbl">协议类型</span>
          <select v-model="form.category" class="ie-in">
            <option value="">未分类</option>
            <option v-for="c in categoryOpts" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">版本号</span><input v-model.trim="form.version" class="ie-in" placeholder="v1.0" /></label>
        <label class="ie-fld"><span class="ie-lbl">适用学院ID</span><input v-model.trim="form.scopeCollegeIds" class="ie-in" placeholder="逗号分隔，留空=全校" /></label>
        <label class="ie-fld"><span class="ie-lbl">适用专业ID</span><input v-model.trim="form.scopeMajorIds" class="ie-in" placeholder="逗号分隔，留空=全校" /></label>
        <label class="ie-fld"><span class="ie-lbl">适用年级</span><input v-model.trim="form.scopeGrades" class="ie-in" placeholder="如 2024级,2023级" /></label>
        <label class="ie-fld"><span class="ie-lbl">适用批次ID</span><input v-model.trim="form.scopeBatchIds" class="ie-in" placeholder="逗号分隔，留空=不限" /></label>
        <div class="ie-fld ie-fld--full">
          <span class="ie-lbl">模板变量（勾选后可在正文用双花括号 + key 占位，如 <code v-text="braced('studentName')"></code>）</span>
          <div class="at-vars">
            <label v-for="v in variablePresets" :key="v.key" class="at-var">
              <input type="checkbox" :value="v.key" v-model="form.variableKeys" />
              <span>{{ v.label }} <code v-text="v.key"></code></span>
            </label>
          </div>
        </div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">模板正文</span><textarea v-model="form.body" class="ie-in" rows="6" :placeholder="bodyPlaceholder" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><input v-model.trim="form.remark" class="ie-in" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">{{ submitting ? '提交中…' : '保存' }}</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 详情 -->
    <AppDrawer v-model:visible="detailVisible" title="协议模板详情">
      <div v-if="detail" class="at-detail">
        <div class="at-detail__head">
          <h3>{{ detail.name }}<span v-if="detail.isDefault" class="at-default">默认</span></h3>
          <StatusTag :type="detail.statusTone" :label="detail.statusLabel" dot />
        </div>
        <dl class="at-meta">
          <div><dt>协议类型</dt><dd>{{ detail.category || '未分类' }}</dd></div>
          <div><dt>版本号</dt><dd>{{ detail.version }}</dd></div>
          <div><dt>适用范围</dt><dd>{{ detail.scopeSummary }}</dd></div>
          <div><dt>备注</dt><dd>{{ detail.remark || '—' }}</dd></div>
        </dl>
        <div class="at-sec">
          <div class="at-sec__t">模板变量</div>
          <div v-if="detail.variables && detail.variables.length" class="at-vars">
            <span v-for="v in detail.variables" :key="v.key" class="at-var-tag">{{ v.label }} <code v-text="braced(v.key)"></code></span>
          </div>
          <p v-else class="mp-cell-sub">未设置变量</p>
        </div>
        <div class="at-sec">
          <div class="at-sec__t">模板正文</div>
          <pre class="at-body">{{ detail.body || '（空）' }}</pre>
        </div>
        <div class="at-sec">
          <div class="at-sec__t">操作留痕</div>
          <ul class="at-trail">
            <li v-for="(a, i) in detail.auditTrail" :key="i">
              <b>{{ a.action }}</b> · {{ a.operator || '系统' }} · {{ a.occurredAt }}
            </li>
          </ul>
        </div>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 实习协议模板库（/admin/internship/agreement-templates）：筛选 + 增改抽屉(适用范围/变量勾选/正文) + 状态机 + 默认模板 + 详情(含审计)。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { agreementTemplateApi } from '@/modules/internship/api/agreement-template.api'
import { toast } from '@/utils/toast'

const STATUS_OPTS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'ENABLED', label: '启用中' },
  { value: 'DISABLED', label: '已停用' },
  { value: 'ARCHIVED', label: '已归档' }
]
const CATEGORY_OPTS = ['三方协议', '顶岗实习协议', '安全责任书', '实习承诺书', '保密协议']
const EMPTY_FILTERS = () => ({ keyword: '', status: '', category: '' })
const EMPTY_FORM = () => ({
  name: '', category: '', version: 'v1.0', scopeCollegeIds: '', scopeMajorIds: '',
  scopeGrades: '', scopeBatchIds: '', body: '', remark: '', variableKeys: []
})
const toArr = (s) => (s || '').split(/[,，]/).map((x) => x.trim()).filter(Boolean)

export default {
  name: 'InternshipAgreementTemplateListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      variablePresets: [],
      editVisible: false, editing: null, form: EMPTY_FORM(), formError: '',
      detailVisible: false, detail: null,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'name', title: '模板 / 类型·版本' },
        { key: 'scope', title: '适用范围' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '280px' }
      ]
    }
  },
  computed: {
    statusOpts() { return STATUS_OPTS },
    categoryOpts() { return CATEGORY_OPTS },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '模板名称 / 类型' },
        { key: 'status', label: '状态', type: 'select', options: STATUS_OPTS },
        { key: 'category', label: '类型', type: 'select', options: CATEGORY_OPTS.map((c) => ({ value: c, label: c })) }
      ]
    },
    toolbarActions() {
      return [{ key: 'create', label: '＋ 新建模板', variant: 'primary' }]
    },
    pageSubtitle() {
      return `共 ${this.total} 个协议模板 · 支持适用范围 / 版本 / 默认模板 / 变量占位`
    },
    bodyPlaceholder() {
      // 用 braced() 拼占位符，避免在模板里直接写双花括号（Vue 会当插值解析）
      return `甲方：${this.braced('schoolName')}  乙方：${this.braced('companyName')}  实习学生：${this.braced('studentName')} ……`
    }
  },
  async created() {
    const v = await agreementTemplateApi.getVariablePresets()
    if (v.code === 0) this.variablePresets = v.data
    this.load()
  },
  methods: {
    braced(key) {
      return '{' + '{' + key + '}' + '}'
    },
    async load() {
      this.loading = true; this.error = ''
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      const res = await agreementTemplateApi.getTemplates(p)
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
    },
    openCreate() {
      this.editing = null; this.form = EMPTY_FORM(); this.formError = ''; this.editVisible = true
    },
    openEdit(row) {
      this.editing = row
      this.form = {
        name: row.name, category: row.category || '', version: row.version,
        scopeCollegeIds: (row.scopeCollegeIds || []).join(','),
        scopeMajorIds: (row.scopeMajorIds || []).join(','),
        scopeGrades: (row.scopeGrades || []).join(','),
        scopeBatchIds: (row.scopeBatchIds || []).join(','),
        body: '', remark: row.remark || '', variableKeys: []
      }
      this.formError = ''
      // 拉全量详情补 body/variables
      agreementTemplateApi.getTemplateDetail(row.id).then((res) => {
        if (res.code === 0) {
          this.form.body = res.data.body || ''
          this.form.variableKeys = (res.data.variables || []).map((v) => v.key)
        }
      })
      this.editVisible = true
    },
    _buildBody() {
      const preset = new Map(this.variablePresets.map((v) => [v.key, v]))
      const variables = (this.form.variableKeys || []).map((k) => {
        const p = preset.get(k)
        return p ? { key: p.key, label: p.label, example: p.example } : { key: k, label: k, example: '' }
      })
      return {
        name: this.form.name, category: this.form.category || null, version: this.form.version || 'v1.0',
        scopeCollegeIds: toArr(this.form.scopeCollegeIds), scopeMajorIds: toArr(this.form.scopeMajorIds),
        scopeGrades: toArr(this.form.scopeGrades), scopeBatchIds: toArr(this.form.scopeBatchIds),
        body: this.form.body, variables, remark: this.form.remark
      }
    },
    async submitEdit() {
      this.formError = ''
      if (!this.form.name || this.form.name.length < 2) { this.formError = '模板名称至少 2 个字'; return }
      this.submitting = true
      try {
        const payload = this._buildBody()
        const res = this.editing
          ? await agreementTemplateApi.updateTemplate(this.editing.id, payload)
          : await agreementTemplateApi.createTemplate(payload)
        if (res.code === 0) { toast.success('已保存并写入留痕'); this.editVisible = false; this.load() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    async openDetail(row) {
      const res = await agreementTemplateApi.getTemplateDetail(row.id)
      if (res.code === 0) { this.detail = res.data; this.detailVisible = true } else toast.error(res.message)
    },
    askStatus(row, action) {
      const map = {
        ENABLE: { t: '启用模板', c: '确认启用', type: 'primary', reason: false },
        DISABLE: { t: '停用模板', c: '确认停用', type: 'warning', reason: false },
        ARCHIVE: { t: '归档模板', c: '确认归档', type: 'danger', reason: true }
      }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.name}」执行「${m.t}」？${action === 'ARCHIVE' ? '（归档后不可编辑、不可再启用）' : ''}`, type: m.type, confirmText: m.c, requireReason: m.reason, reasonLabel: '原因', action: 'STATUS_' + action, row }
    },
    askDefault(row, on) {
      this.confirm = { visible: true, title: on ? '设为默认模板' : '取消默认', message: on ? `确认将「${row.name}」设为该类型默认协议模板？（同类型原默认会被替换）` : `确认取消「${row.name}」的默认标记？`, type: 'primary', confirmText: '确认', requireReason: false, action: on ? 'DEFAULT_ON' : 'DEFAULT_OFF', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action.startsWith('STATUS_')) res = await agreementTemplateApi.setStatus(row.id, { action: action.slice(7), reason: reason || '' })
        else if (action === 'DEFAULT_ON') res = await agreementTemplateApi.setDefault(row.id, true)
        else if (action === 'DEFAULT_OFF') res = await agreementTemplateApi.setDefault(row.id, false)
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.at-default { margin-left: var(--space-2); font-size: 11px; padding: 1px 6px; border-radius: 6px; background: var(--success-50, #ecfdf5); color: var(--success, #16a34a); }
.mp-link--danger { color: var(--danger, #dc2626); }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-2); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.at-vars { display: flex; flex-wrap: wrap; gap: 8px; }
.at-var { display: flex; align-items: center; gap: 4px; font-size: 12px; padding: 4px 8px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; }
.at-var code, .at-var-tag code { background: var(--bg-subtle, #f1f5f9); padding: 0 4px; border-radius: 4px; }
.at-detail__head { display: flex; align-items: center; justify-content: space-between; }
.at-detail__head h3 { margin: 0; font-size: 16px; }
.at-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 12px 0; }
.at-meta dt { font-size: 12px; color: var(--t3, #64748b); }
.at-meta dd { margin: 2px 0 0; font-size: 13px; }
.at-sec { margin-top: 14px; }
.at-sec__t { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.at-var-tag { display: inline-block; margin: 0 6px 6px 0; font-size: 12px; padding: 2px 8px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; }
.at-body { white-space: pre-wrap; word-break: break-word; background: var(--bg-subtle, #f8fafc); border: 1px solid var(--line, #e2e8f0); border-radius: 8px; padding: 10px; font-size: 12px; max-height: 240px; overflow: auto; }
.at-trail { margin: 0; padding-left: 18px; font-size: 12px; color: var(--t2, #475569); }
.at-trail li { margin-bottom: 4px; }
</style>
