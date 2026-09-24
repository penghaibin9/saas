<template>
  <ModulePageShell
    title="全部模板"
    :subtitle="`${typeLabel}统一维护 · 草稿→启用→停用→归档 · 同类型默认模板唯一`"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <section class="gt-command" aria-label="模板工作结论">
      <div>
        <span>当前工作区</span>
        <strong>{{ typeLabel }} · {{ currentStatusLabel }}</strong>
        <small>共 {{ pagination.total }} 条；归档模板永久只读，启停与默认唯一性由服务端状态机校验。</small>
      </div>
      <div class="gt-command__facts">
        <span><b>{{ rows.length }}</b> 当前页</span>
        <span><b>{{ enabledOnPage }}</b> 启用中</span>
        <span><b>{{ archivedOnPage }}</b> 归档只读</span>
      </div>
    </section>

    <div class="mp-stack">
      <nav class="gt-types" aria-label="模板类型">
        <button
          v-for="item in typeTabs"
          :key="item.value"
          type="button"
          :class="{ 'is-active': activeType === item.value }"
          :disabled="submitting"
          @click="switchType(item.value)"
        >
          <span>{{ item.label }}</span>
          <small>{{ item.hint }}</small>
        </button>
      </nav>

      <div class="mp-tabs" aria-label="模板状态">
        <button
          v-for="t in tabs"
          :key="t.value"
          class="mp-tab"
          :class="{ 'is-active': filters.status === t.value }"
          :disabled="submitting"
          @click="switchTab(t.value)"
        >
          {{ t.label }}
        </button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState
        v-else-if="!rows.length && filters.status"
        :title="'当前页签没有' + typeLabel"
        :description="'切到「全部」可以看这一类的所有' + typeLabel + '。'"
      >
        <template #actions>
          <button class="mp-btn" :disabled="submitting" @click="switchTab('')">看全部</button>
        </template>
      </EmptyState>
      <EmptyState
        v-else-if="!rows.length"
        :title="'还没有' + typeLabel"
        :description="emptyDesc"
      >
        <template #actions>
          <button class="mp-btn mp-btn--primary" :disabled="!canWrite || submitting" @click="openCreate">＋ 新建{{ typeLabel }}</button>
        </template>
      </EmptyState>
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-name="{ row }">
          <div class="mp-cell-main">
            {{ row.name }}
            <StatusTag v-if="row.isDefault" type="success" label="默认" />
          </div>
          <div class="mp-cell-sub">{{ row.version }} · {{ row.applicableNote || '适用全校' }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="statusTone(row.status)" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'ARCHIVED'">
            <span class="gt-readonly">归档只读</span>
          </template>
          <template v-else-if="canWrite">
            <button class="mp-link" :disabled="submitting" @click="openEdit(row)">编辑</button>
            <button v-if="row.status === 'DRAFT' || row.status === 'DISABLED'" class="mp-link" :disabled="submitting" @click="doStatus(row, 'ENABLE')">启用</button>
            <button v-if="row.status === 'ENABLED'" class="mp-link" :disabled="submitting" @click="doStatus(row, 'DISABLE')">停用</button>
            <button v-if="row.status === 'ENABLED' && !row.isDefault" class="mp-link" :disabled="submitting" @click="doDefault(row)">设默认</button>
            <button v-if="row.status === 'DRAFT' || row.status === 'DISABLED'" class="mp-link mp-link--danger" :disabled="submitting" @click="doStatus(row, 'ARCHIVE')">归档</button>
          </template>
          <span v-else class="gt-readonly">只读</span>
        </template>
      </DataTable>
    </div>

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
/** 毕设模板中心（/admin/graduation/templates?type=MATERIAL|TASKBOOK|PROPOSAL&status=&page=）。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { graduationTemplateApi } from '@/modules/graduation/api/graduation-template.api'
import { toast } from '@/utils/toast'

const TYPE_LABEL = { MATERIAL: '材料模板', TASKBOOK: '任务书模板', PROPOSAL: '开题模板' }
const TYPE_TABS = [
  { value: 'MATERIAL', label: '材料模板', hint: '统一归档材料格式' },
  { value: 'TASKBOOK', label: '任务书模板', hint: '导师下达任务时套用' },
  { value: 'PROPOSAL', label: '开题模板', hint: '学生撰写开题时下载' }
]
const STATUS_TABS = [
  { value: '', label: '全部' },
  { value: 'ENABLED', label: '启用中' },
  { value: 'DRAFT', label: '草稿' },
  { value: 'DISABLED', label: '已停用' },
  { value: 'ARCHIVED', label: '已归档' }
]
const STATUS_LABEL = Object.fromEntries(STATUS_TABS.map((item) => [item.value, item.label]))
const TYPE_EMPTY_DESC = {
  MATERIAL: '材料模板是学生交材料时下载的格式范本。不建模板，学生提交格式会不统一，归档时需要逐份返工。',
  TASKBOOK: '任务书模板是导师给学生下达任务时套用的范本。建好后导师可直接套用，不必为每名学生从头编写。',
  PROPOSAL: '开题模板是学生写开题报告时下载的范本。统一模板后，学生提交与教师批阅都有明确结构。'
}

export default {
  name: 'GraduationTemplateView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      activeType: 'MATERIAL',
      loading: true,
      error: '',
      rows: [],
      submitting: false,
      routeReady: false,
      loadToken: 0,
      commandSnapshot: null,
      filters: { status: '' },
      pagination: { page: 1, pageSize: 10, total: 0 },
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确定', action: '', row: null },
      typeTabs: TYPE_TABS,
      tabs: STATUS_TABS,
      columns: [
        { key: 'name', title: '模板' },
        { key: 'status', title: '状态' },
        { key: 'updateTime', title: '更新时间' },
        { key: 'actions', title: '操作', width: '280px' }
      ]
    }
  },
  computed: {
    templateType() { return this.activeType },
    typeLabel() { return TYPE_LABEL[this.activeType] || TYPE_LABEL.MATERIAL },
    currentStatusLabel() { return STATUS_LABEL[this.filters.status] || '全部' },
    emptyDesc() { return TYPE_EMPTY_DESC[this.activeType] || TYPE_EMPTY_DESC.MATERIAL },
    canWrite() { return this.ctx.writeEnabled !== false },
    toolbarActions() {
      return [{
        key: 'create',
        label: `＋ 新建${this.typeLabel}`,
        variant: 'primary',
        disabled: !this.canWrite || this.submitting,
        disabledReason: !this.canWrite ? '写操作已禁用' : (this.submitting ? '模板命令提交中' : '')
      }]
    },
    enabledOnPage() { return this.rows.filter((row) => row.status === 'ENABLED').length },
    archivedOnPage() { return this.rows.filter((row) => row.status === 'ARCHIVED').length }
  },
  watch: {
    '$route.query': {
      deep: true,
      handler(query) {
        if (!this.routeReady) return
        if (this.submitting) {
          this.restoreCommandRoute()
          return
        }
        if (this.applyRouteState(query)) this.load()
      }
    }
  },
  created() {
    this.applyRouteState(this.$route.query)
    this.routeReady = true
    if (!this.$route.query.type) this.syncUrl()
    this.load()
  },
  beforeUnmount() {
    ++this.loadToken
  },
  beforeRouteLeave(to, from, next) {
    if (this.submitting) {
      toast.info('模板操作正在提交，请等待服务器回执后再离开')
      next(false)
      return
    }
    next()
  },
  methods: {
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    routePage(value) {
      const page = Number.parseInt(this.routeText(value), 10)
      return Number.isFinite(page) && page > 0 ? page : 1
    },
    applyRouteState(query = {}) {
      const nextType = TYPE_LABEL[this.routeText(query.type)] ? this.routeText(query.type) : 'MATERIAL'
      const rawStatus = this.routeText(query.status)
      const nextStatus = STATUS_TABS.some((item) => item.value === rawStatus) ? rawStatus : ''
      const nextPage = this.routePage(query.page)
      const changed = nextType !== this.activeType || nextStatus !== this.filters.status || nextPage !== this.pagination.page
      this.activeType = nextType
      this.filters.status = nextStatus
      this.pagination.page = nextPage
      return changed
    },
    buildRouteQuery(overrides = {}) {
      const query = {
        ...this.$route.query,
        type: this.activeType,
        status: this.filters.status || undefined,
        page: this.pagination.page > 1 ? String(this.pagination.page) : undefined,
        ...overrides
      }
      Object.keys(query).forEach((key) => {
        if (query[key] == null || query[key] === '') delete query[key]
      })
      return query
    },
    syncUrl(overrides = {}) {
      return this.$router.replace({ query: this.buildRouteQuery(overrides) }).catch(() => {})
    },
    restoreCommandRoute() {
      const query = this.commandSnapshot?.routeQuery
      if (!query) return
      this.$router.replace({ path: '/admin/graduation/templates', query }).catch(() => {})
    },
    statusTone(status) {
      return { ENABLED: 'success', DRAFT: 'warning', DISABLED: 'default', ARCHIVED: 'info' }[status] || 'default'
    },
    switchType(type) {
      if (this.submitting || !TYPE_LABEL[type] || type === this.activeType) return
      this.activeType = type
      this.filters.status = ''
      this.pagination.page = 1
      void this.syncUrl({ type, status: undefined, page: undefined })
      this.load()
    },
    switchTab(status) {
      if (this.submitting || !STATUS_TABS.some((item) => item.value === status)) return
      this.filters.status = status
      this.pagination.page = 1
      void this.syncUrl({ status: status || undefined, page: undefined })
      this.load()
    },
    onPageChange(page) {
      if (this.submitting) return
      this.pagination.page = page
      void this.syncUrl({ page: page > 1 ? String(page) : undefined })
      this.load()
    },
    onToolbar(key) {
      if (key === 'create') this.openCreate()
    },
    openCreate() {
      if (!this.canWrite || this.submitting) return
      this.$router.push({
        path: '/admin/graduation/templates/create',
        query: {
          type: this.activeType,
          status: this.filters.status || undefined,
          page: this.pagination.page > 1 ? String(this.pagination.page) : undefined
        }
      })
    },
    openEdit(row) {
      if (!this.canWrite || this.submitting || !row || row.status === 'ARCHIVED') return
      this.$router.push({
        path: `/admin/graduation/templates/${row.id}/edit`,
        query: {
          type: this.activeType,
          status: this.filters.status || undefined,
          page: this.pagination.page > 1 ? String(this.pagination.page) : undefined
        }
      })
    },
    doStatus(row, action) {
      if (!this.canWrite || this.submitting || !row || row.status === 'ARCHIVED') return
      const map = {
        ENABLE: { title: '启用模板', message: `启用「${row.name}」？`, type: 'primary', confirmText: '启用' },
        DISABLE: { title: '停用模板', message: `停用「${row.name}」？停用后不可被新业务引用。`, type: 'warning', confirmText: '停用' },
        ARCHIVE: { title: '归档模板', message: `归档「${row.name}」？归档后永久只读，但历史引用继续保留。`, type: 'danger', confirmText: '归档' }
      }
      const config = map[action]
      if (!config) return
      this.confirm = { visible: true, ...config, action, row }
    },
    doDefault(row) {
      if (!this.canWrite || this.submitting || !row || row.status !== 'ENABLED') return
      this.confirm = {
        visible: true,
        title: '设为默认',
        message: `将「${row.name}」设为${this.typeLabel}默认模板？原默认由服务端自动取消。`,
        type: 'primary',
        confirmText: '设默认',
        action: 'DEFAULT',
        row
      }
    },
    async onConfirm() {
      const row = this.confirm.row
      const action = this.confirm.action
      if (!this.canWrite || this.submitting || !row || row.status === 'ARCHIVED') return
      const snapshot = {
        type: this.activeType,
        status: this.filters.status,
        page: this.pagination.page,
        rowId: row.id,
        rowStatus: row.status,
        action,
        routeQuery: this.buildRouteQuery()
      }
      this.commandSnapshot = snapshot
      this.submitting = true
      try {
        const res = action === 'DEFAULT'
          ? await graduationTemplateApi.setDefault(snapshot.rowId)
          : await graduationTemplateApi.setStatus(snapshot.rowId, snapshot.action)
        if (res.code === 0) {
          toast.success('操作成功，已回读模板台账')
          this.confirm.visible = false
          await this.load()
        } else {
          toast.error(res.message || '操作失败')
        }
      } catch (error) {
        toast.error(error?.message || '模板操作失败')
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
    },
    async load() {
      const token = ++this.loadToken
      const snapshot = {
        type: this.activeType,
        status: this.filters.status,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      }
      this.loading = true
      this.error = ''
      try {
        const res = await graduationTemplateApi.getTemplates({
          templateType: snapshot.type,
          status: snapshot.status,
          page: snapshot.page,
          pageSize: snapshot.pageSize
        })
        if (
          token !== this.loadToken
          || snapshot.type !== this.activeType
          || snapshot.status !== this.filters.status
          || snapshot.page !== this.pagination.page
        ) return false
        if (res.code === 0) {
          this.rows = Array.isArray(res.data?.list) ? res.data.list : []
          this.pagination.total = Number(res.data?.total) || 0
          return true
        }
        this.rows = []
        this.pagination.total = 0
        this.error = res.message || '模板台账加载失败'
      } catch (error) {
        if (token === this.loadToken) {
          this.rows = []
          this.pagination.total = 0
          this.error = error?.message || '模板台账加载失败'
        }
      } finally {
        if (token === this.loadToken) this.loading = false
      }
      return false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gt-command { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--space-4); align-items: center; margin-bottom: var(--space-3); padding: 12px 14px; border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-lg, 12px); background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--card, #fff) 75%); }
.gt-command > div:first-child { display: grid; min-width: 0; gap: 2px; }
.gt-command > div:first-child > span { color: var(--primary-600, #2563eb); font-size: var(--font-size-xs, 12px); font-weight: 700; letter-spacing: .05em; }
.gt-command strong { color: var(--text-primary, #0f172a); font-size: var(--font-size-md, 14px); }
.gt-command small { color: var(--text-tertiary, #64748b); font-size: var(--font-size-xs, 12px); }
.gt-command__facts { display: flex; align-items: stretch; }
.gt-command__facts span { display: grid; min-width: 76px; gap: 1px; padding: 2px 12px; border-left: 1px solid var(--primary-100, #dbeafe); color: var(--text-tertiary, #64748b); font-size: var(--font-size-xs, 12px); }
.gt-command__facts b { color: var(--text-primary, #0f172a); font-size: var(--font-size-lg, 16px); }
.gt-types { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-2); }
.gt-types button { display: grid; min-width: 0; gap: 2px; padding: 10px 12px; border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); color: inherit; text-align: left; cursor: pointer; }
.gt-types button:hover:not(:disabled) { border-color: var(--primary-200, #bfdbfe); background: var(--primary-50, #eff6ff); }
.gt-types button.is-active { border-color: var(--primary-500, #3b82f6); background: var(--primary-50, #eff6ff); box-shadow: inset 3px 0 0 var(--primary-600, #2563eb); }
.gt-types button:disabled { cursor: not-allowed; opacity: .55; }
.gt-types span { color: var(--text-primary, #0f172a); font-size: var(--font-size-sm, 13px); font-weight: 600; }
.gt-types small { overflow: hidden; color: var(--text-tertiary, #64748b); font-size: var(--font-size-xs, 12px); text-overflow: ellipsis; white-space: nowrap; }
.gt-readonly { color: var(--text-tertiary, #64748b); font-size: var(--font-size-xs, 12px); }
.mp-link { margin-right: var(--space-2); }
.mp-link:disabled { cursor: not-allowed; opacity: .5; }
.mp-link--danger { color: var(--danger-600, #dc2626); }
@media (max-width: 820px) { .gt-command { grid-template-columns: 1fr; } .gt-command__facts span:first-child { border-left: 0; padding-left: 0; } }
@media (max-width: 640px) { .gt-types { grid-template-columns: 1fr; } .gt-command__facts { overflow-x: auto; } }
</style>
