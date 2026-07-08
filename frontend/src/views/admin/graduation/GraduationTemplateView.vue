<template>
  <ModulePageShell
    :title="typeLabel"
    :subtitle="'毕设' + typeLabel + '统一维护 · 草稿→启用→停用→归档 · 同类型默认模板唯一'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 新建' + typeLabel, variant: 'primary' }]" @action="openCreate" />
    </template>

    <div class="mp-stack">
      <div class="mp-tabs">
        <button v-for="t in tabs" :key="t.value" class="mp-tab" :class="{ 'is-active': filters.status === t.value }" @click="switchTab(t.value)">
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="'当前暂无' + typeLabel" :description="'点击右上角「新建' + typeLabel + '」创建'" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-name="{ row }">
          <div class="mp-cell-main">{{ row.name }}
            <StatusTag v-if="row.isDefault" type="success" label="默认" />
          </div>
          <div class="mp-cell-sub">{{ row.version }} · {{ row.applicableNote || '适用全校' }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTone(row.status)" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openEdit(row)">编辑</button>
          <button v-if="row.status === 'DRAFT' || row.status === 'DISABLED'" class="mp-link" style="margin-left:var(--space-2)" @click="doStatus(row, 'ENABLE')">启用</button>
          <button v-if="row.status === 'ENABLED'" class="mp-link" style="margin-left:var(--space-2)" @click="doStatus(row, 'DISABLE')">停用</button>
          <button v-if="row.status === 'ENABLED' && !row.isDefault" class="mp-link" style="margin-left:var(--space-2)" @click="doDefault(row)">设默认</button>
          <button v-if="row.status === 'DRAFT' || row.status === 'DISABLED'" class="mp-link mp-link--danger" style="margin-left:var(--space-2)" @click="doStatus(row, 'ARCHIVE')">归档</button>
        </template>
      </DataTable>
    </div>

    <AppDrawer v-model:visible="drawer.visible" :title="drawer.id ? '编辑' + typeLabel : '新建' + typeLabel">
      <form class="ie-form" @submit.prevent="save">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">模板名称 <i>*</i></span>
          <input v-model.trim="form.name" class="ie-in" :placeholder="'如 2026届' + typeLabel" />
        </label>
        <label class="ie-fld"><span class="ie-lbl">版本号</span><input v-model.trim="form.version" class="ie-in" placeholder="v1" /></label>
        <label class="ie-fld"><span class="ie-lbl">适用范围说明</span><input v-model.trim="form.applicableNote" class="ie-in" placeholder="如 软件学院/全校" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">模板正文</span>
          <textarea v-model="form.content" class="ie-in" rows="6" :placeholder="'可用占位变量：' + varHint"></textarea>
        </label>
        <div class="ie-fld ie-fld--full" v-if="variables.length">
          <span class="ie-lbl">可用占位变量</span>
          <div class="tpl-vars">
            <button type="button" v-for="v in variables" :key="v" class="tpl-var" @click="insertVar(v)">{{ '{' + v + '}' }}</button>
          </div>
        </div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><input v-model.trim="form.remark" class="ie-in" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="drawer.visible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">{{ drawer.id ? '保存' : '创建' }}</button>
        </div>
      </form>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :submitting="submitting"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 毕设模板中心（/admin/graduation/templates?type=MATERIAL|TASKBOOK|PROPOSAL）。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { graduationTemplateApi } from '@/modules/graduation/api/graduation-template.api'
import { toast } from '@/utils/toast'

const TYPE_LABEL = { MATERIAL: '材料模板', TASKBOOK: '任务书模板', PROPOSAL: '开题模板' }

export default {
  name: 'GraduationTemplateView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], submitting: false,
      filters: { status: '' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      drawer: { visible: false, id: null },
      form: { name: '', version: 'v1', applicableNote: '', content: '', remark: '' },
      formError: '',
      variables: [],
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确定', action: '', row: null },
      tabs: [
        { value: '', label: '全部' },
        { value: 'ENABLED', label: '启用中' },
        { value: 'DRAFT', label: '草稿' },
        { value: 'DISABLED', label: '已停用' },
        { value: 'ARCHIVED', label: '已归档' }
      ],
      columns: [
        { key: 'name', title: '模板' },
        { key: 'status', title: '状态' },
        { key: 'updateTime', title: '更新时间' },
        { key: 'actions', title: '操作', width: '260px' }
      ]
    }
  },
  computed: {
    templateType() { return this.$route.query.type || 'MATERIAL' },
    typeLabel() { return TYPE_LABEL[this.templateType] || '材料模板' },
    varHint() { return this.variables.map((v) => '{' + v + '}').join(' ') }
  },
  watch: {
    '$route.query.type'() { this.pagination.page = 1; this.filters.status = ''; this.loadVariables(); this.load() }
  },
  created() {
    this.loadVariables()
    this.load()
  },
  methods: {
    statusTone(s) { return { ENABLED: 'success', DRAFT: 'warning', DISABLED: 'default', ARCHIVED: 'info' }[s] || 'default' },
    async loadVariables() {
      const res = await graduationTemplateApi.getVariables()
      if (res.code === 0) this.variables = res.data[this.templateType] || []
    },
    switchTab(v) { this.filters.status = v; this.pagination.page = 1; this.load() },
    onPageChange(p) { this.pagination.page = p; this.load() },
    openCreate() {
      this.drawer = { visible: true, id: null }
      this.form = { name: '', version: 'v1', applicableNote: '', content: '', remark: '' }
      this.formError = ''
    },
    async openEdit(row) {
      const res = await graduationTemplateApi.getTemplate(row.id)
      if (res.code !== 0) { toast.error(res.message); return }
      const d = res.data
      this.drawer = { visible: true, id: d.id }
      this.form = { name: d.name, version: d.version, applicableNote: d.applicableNote, content: d.content, remark: d.remark }
      this.formError = ''
    },
    insertVar(v) { this.form.content = (this.form.content || '') + '{' + v + '}' },
    async save() {
      this.formError = ''
      if (!this.form.name) { this.formError = '模板名称必填'; return }
      this.submitting = true
      const body = { templateType: this.templateType, ...this.form }
      const res = this.drawer.id
        ? await graduationTemplateApi.updateTemplate(this.drawer.id, body)
        : await graduationTemplateApi.createTemplate(body)
      this.submitting = false
      if (res.code === 0) { toast.success(this.drawer.id ? '已保存' : '已创建'); this.drawer.visible = false; this.load() }
      else this.formError = res.message || '保存失败'
    },
    doStatus(row, action) {
      const map = { ENABLE: { t: '启用模板', m: `启用「${row.name}」？`, tone: 'primary', c: '启用' },
        DISABLE: { t: '停用模板', m: `停用「${row.name}」？停用后不可被引用。`, tone: 'warning', c: '停用' },
        ARCHIVE: { t: '归档模板', m: `归档「${row.name}」？归档后不可编辑。`, tone: 'danger', c: '归档' } }
      const c = map[action]
      this.confirm = { visible: true, title: c.t, message: c.m, type: c.tone, confirmText: c.c, action, row }
    },
    doDefault(row) {
      this.confirm = { visible: true, title: '设为默认', message: `将「${row.name}」设为该类型默认模板？原默认自动取消。`, type: 'primary', confirmText: '设默认', action: 'DEFAULT', row }
    },
    async onConfirm() {
      const row = this.confirm.row
      this.submitting = true
      const res = this.confirm.action === 'DEFAULT'
        ? await graduationTemplateApi.setDefault(row.id)
        : await graduationTemplateApi.setStatus(row.id, this.confirm.action)
      this.submitting = false
      if (res.code === 0) { toast.success('操作成功'); this.confirm.visible = false; this.load() }
      else toast.error(res.message || '操作失败')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await graduationTemplateApi.getTemplates({
        templateType: this.templateType, status: this.filters.status,
        page: this.pagination.page, pageSize: this.pagination.pageSize
      })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else this.error = res.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.tpl-vars { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-top: var(--space-1); }
.tpl-var { font-size: var(--font-size-xs); color: var(--brand-primary); background: var(--primary-50); border: 1px solid var(--primary-100); padding: 3px 8px; border-radius: var(--radius-sm); cursor: pointer; }
</style>
