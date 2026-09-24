<template>
  <ModulePageShell
    title="题目调整申请"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <section class="tc-command" aria-label="题目调整工作结论">
      <div>
        <span>当前工作区</span>
        <strong>{{ batchStore.selectedBatchName || '请先选择毕设批次' }} · {{ currentStatusLabel }}</strong>
        <small>共 {{ total }} 条申请；通过后由服务端迁移真实选题关系，驳回必须保留理由。</small>
      </div>
      <div class="tc-command__next">
        <span>下一步</span>
        <strong>{{ nextActionText }}</strong>
      </div>
    </section>

    <aside v-if="actionReceipt" class="tc-receipt" role="status">
      <div>
        <strong>{{ actionReceipt.title }}</strong>
        <span>{{ actionReceipt.result }}</span>
        <small>{{ actionReceipt.next }}</small>
      </div>
      <button type="button" :disabled="submitting" @click="actionReceipt = null">关闭</button>
    </aside>

    <EmptyState
      v-if="!hasBatch"
      title="请先选择或创建毕设批次"
      description="顶部批次条选择当前工作批次后，再审核本批次的题目调整申请。"
    />
    <div v-else class="mp-stack" :class="{ 'is-command-locked': submitting }" :aria-busy="submitting">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="当前视图暂无变更申请" description="学生获批题目后如需换题，须发起课题信息变更申请；审核通过后才由服务端迁移真实选题关系。" />
      <DataTable
        v-else
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="{ page, pageSize, total }"
        @page-change="turnPage"
      >
        <template #cell-student="{ row }">
          <div class="mp-cell-main">{{ row.studentName }}</div>
          <div class="mp-cell-sub">{{ row.studentNo }}</div>
        </template>
        <template #cell-change="{ row }">
          <div class="mp-cell-main">{{ row.oldTopicTitle }} → {{ row.newTopicTitle }}</div>
          <div class="mp-cell-sub">{{ row.reason }}</div>
        </template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" :disabled="submitting" @click="openDetail(row)">详情</button>
          <template v-if="canTopicReview && row.status === 'PENDING'">
            <button class="mp-link" :disabled="submitting" @click="askApprove(row)">通过</button>
            <button class="mp-link mp-link--danger" :disabled="submitting" @click="askReject(row)">驳回</button>
          </template>
        </template>
      </DataTable>
    </div>

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
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { gdTopicChangeApi } from '@/modules/graduation/api/graduation-topic-change.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { matchPermission } from '@/config/navPlan'
import { toast } from '@/utils/toast'

const STATUS_OPTS = [
  { value: 'PENDING', label: '待审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'CANCELLED', label: '已撤销' }
]
const STATUS_LABEL = { '': '全部状态', ...Object.fromEntries(STATUS_OPTS.map((item) => [item.value, item.label])) }
const EMPTY_FILTERS = () => ({ status: '' })

export default {
  name: 'TopicChangeRequestListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      loading: true,
      error: '',
      submitting: false,
      routeReady: false,
      loadToken: 0,
      rows: [],
      total: 0,
      page: 1,
      pageSize: 10,
      filters: EMPTY_FILTERS(),
      commandSnapshot: null,
      actionReceipt: null,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '理由', action: null, row: null }
    }
  },
  computed: {
    permissionPatterns() { return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : [] },
    canTopicView() { return matchPermission(this.permissionPatterns, 'graduationDesign.topic.view') },
    canTopicReview() { return matchPermission(this.permissionPatterns, 'graduationDesign.topic.review') && this.ctx.writeEnabled !== false },
    hasBatch() { return Boolean(this.batchStore.selectedBatchId) },
    currentStatusLabel() { return STATUS_LABEL[this.filters.status] || '全部状态' },
    filterFields() { return [{ key: 'status', label: '状态', type: 'select', options: STATUS_OPTS }] },
    toolbarActions() {
      return [{
        key: 'refresh',
        label: '刷新',
        disabled: this.submitting || !this.hasBatch,
        disabledReason: this.submitting ? '审核命令提交中' : (!this.hasBatch ? '请先选择批次' : '')
      }]
    },
    columns() {
      return [
        { key: 'student', title: '学生' },
        { key: 'change', title: '变更（原题目 → 目标题目）' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '200px' }
      ]
    },
    pageSubtitle() {
      if (!this.hasBatch) return '请先选择毕业设计批次'
      return `${this.batchStore.selectedBatchName || this.batchStore.selectedBatchId} · 通过后迁移真实选题关系，驳回须说明理由`
    },
    nextActionText() {
      if (!this.hasBatch) return '选择批次'
      if (this.filters.status === 'PENDING' && this.total > 0) return '逐条核对原题目、目标题目与申请理由'
      if (this.filters.status) return '查看详情或切换至待审核队列'
      return this.total > 0 ? '优先筛选待审核申请' : '当前无需处理'
    }
  },
  created() {
    this.applyRouteState(this.$route.query)
    this.routeReady = true
    this.syncUrl()
    this.load()
  },
  beforeUnmount() {
    ++this.loadToken
  },
  beforeRouteLeave(to, from, next) {
    if (this.submitting) {
      toast.info('题目调整审核正在提交，请等待服务器回执后再离开')
      next(false)
      return
    }
    next()
  },
  watch: {
    '$route.query': {
      deep: true,
      handler(query) {
        if (!this.routeReady) return
        if (this.submitting) {
          this.restoreCommandContext()
          return
        }
        if (this.applyRouteState(query)) this.load()
      }
    },
    'batchStore.selectedBatchId'(batchId) {
      ++this.loadToken
      if (this.submitting && this.commandSnapshot) {
        if (String(batchId || '') !== String(this.commandSnapshot.batchId || '')) {
          this.batchStore.selectBatch(this.commandSnapshot.batchId)
        }
        this.restoreCommandContext()
        return
      }
      this.page = 1
      this.actionReceipt = null
      void this.syncUrl({ batchId: batchId ? String(batchId) : undefined, page: undefined })
      this.load()
    }
  },
  methods: {
    routeText(value) { return Array.isArray(value) ? String(value[0] || '') : String(value || '') },
    routePage(value) {
      const page = Number.parseInt(this.routeText(value), 10)
      return Number.isFinite(page) && page > 0 ? page : 1
    },
    applyRouteState(query = {}) {
      const rawStatus = this.routeText(query.status)
      const nextStatus = STATUS_OPTS.some((item) => item.value === rawStatus) ? rawStatus : ''
      const nextPage = this.routePage(query.page)
      const changed = nextStatus !== this.filters.status || nextPage !== this.page
      this.filters = { status: nextStatus }
      this.page = nextPage
      return changed
    },
    buildRouteQuery(overrides = {}) {
      const query = {
        ...this.$route.query,
        batchId: this.batchStore.selectedBatchId ? String(this.batchStore.selectedBatchId) : undefined,
        status: this.filters.status || undefined,
        page: this.page > 1 ? String(this.page) : undefined,
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
    currentReturnTo() {
      return this.$router.resolve({ path: '/admin/graduation/topic-changes', query: this.buildRouteQuery() }).fullPath
    },
    restoreCommandContext() {
      const snapshot = this.commandSnapshot
      if (!snapshot) return
      this.$router.replace({ path: '/admin/graduation/topic-changes', query: snapshot.routeQuery }).catch(() => {})
    },
    async load() {
      const batchId = this.batchStore.selectedBatchId
      const token = ++this.loadToken
      if (!this.canTopicView || !batchId) {
        this.loading = false
        this.error = ''
        this.rows = []
        this.total = 0
        return false
      }
      const snapshot = { batchId: String(batchId), status: this.filters.status, page: this.page }
      this.loading = true
      this.error = ''
      try {
        const res = await gdTopicChangeApi.getChangeRequests({
          batchId: snapshot.batchId,
          status: snapshot.status || undefined,
          page: snapshot.page,
          pageSize: this.pageSize
        })
        if (
          token !== this.loadToken
          || snapshot.batchId !== String(this.batchStore.selectedBatchId || '')
          || snapshot.status !== this.filters.status
          || snapshot.page !== this.page
        ) return false
        if (res.code === 0) {
          this.rows = Array.isArray(res.data?.list) ? res.data.list : []
          this.total = Number(res.data?.total) || 0
          return true
        }
        this.rows = []
        this.total = 0
        this.error = res.message || '题目调整申请加载失败'
      } catch (error) {
        if (token === this.loadToken) {
          this.rows = []
          this.total = 0
          this.error = error?.message || '题目调整申请加载失败'
        }
      } finally {
        if (token === this.loadToken) this.loading = false
      }
      return false
    },
    search() {
      if (this.submitting) return
      this.page = 1
      void this.syncUrl({ status: this.filters.status || undefined, page: undefined })
      this.load()
    },
    reset() {
      if (this.submitting) return
      this.filters = EMPTY_FILTERS()
      this.page = 1
      void this.syncUrl({ status: undefined, page: undefined })
      this.load()
    },
    turnPage(page) {
      if (this.submitting) return
      this.page = page
      void this.syncUrl({ page: page > 1 ? String(page) : undefined })
      this.load()
    },
    onToolbar(key) {
      if (key === 'refresh' && !this.submitting) this.load()
    },
    openDetail(row) {
      if (!this.canTopicView || this.submitting || !row) return
      this.$router.push({
        path: `/admin/graduation/topic-changes/${row.id}`,
        query: {
          batchId: this.batchStore.selectedBatchId,
          status: this.filters.status || undefined,
          page: this.page > 1 ? String(this.page) : undefined,
          returnTo: this.currentReturnTo()
        }
      })
    },
    askApprove(row) {
      if (!this.canTopicReview || this.submitting || !row || row.status !== 'PENDING') return
      this.confirm = {
        visible: true,
        title: '通过变更申请',
        message: `确认通过「${row.studentName}」由「${row.oldTopicTitle}」变更至「${row.newTopicTitle}」？服务端将迁移真实选题关系并写入审计。`,
        type: 'primary',
        confirmText: '通过',
        requireReason: false,
        reasonLabel: '审核说明',
        action: 'APPROVE',
        row: { ...row }
      }
    },
    askReject(row) {
      if (!this.canTopicReview || this.submitting || !row || row.status !== 'PENDING') return
      this.confirm = {
        visible: true,
        title: '驳回变更申请',
        message: `驳回「${row.studentName}」的变更申请？驳回后原选题关系保持不变。`,
        type: 'danger',
        confirmText: '驳回',
        requireReason: true,
        reasonLabel: '驳回理由',
        action: 'REJECT',
        row: { ...row }
      }
    },
    async onConfirm({ reason } = {}) {
      if (!this.canTopicReview || this.submitting) {
        this.confirm.visible = false
        return
      }
      const action = this.confirm.action
      const row = this.confirm.row
      if (!row || row.status !== 'PENDING' || !['APPROVE', 'REJECT'].includes(action)) return
      const snapshot = {
        action,
        rowId: row.id,
        studentName: row.studentName,
        oldTopicTitle: row.oldTopicTitle,
        newTopicTitle: row.newTopicTitle,
        batchId: String(this.batchStore.selectedBatchId || ''),
        reason: reason || '',
        routeQuery: this.buildRouteQuery()
      }
      this.commandSnapshot = snapshot
      this.submitting = true
      try {
        const res = await gdTopicChangeApi.reviewChangeRequest(snapshot.rowId, { action: snapshot.action, comment: snapshot.reason })
        if (res.code !== 0) {
          toast.error(res.message || '题目调整审核失败')
          return
        }
        const detailRes = await gdTopicChangeApi.getChangeRequestDetail(snapshot.rowId)
        await this.load()
        const detail = detailRes.code === 0 ? (detailRes.data || {}) : {}
        const statusLabel = detail.statusLabel || (snapshot.action === 'APPROVE' ? '已通过' : '已驳回')
        this.actionReceipt = {
          title: `${snapshot.studentName} · ${statusLabel}`,
          result: snapshot.action === 'APPROVE'
            ? `服务器已重新读取申请状态；选题由「${snapshot.oldTopicTitle}」迁移至「${snapshot.newTopicTitle}」的结果以服务端真实关系为准。`
            : `服务器已保留原选题关系；驳回理由：${snapshot.reason}`,
          next: snapshot.action === 'APPROVE' ? '下一步可进入题目库或学生档案核对最新选题关系。' : '下一步由学生按驳回原因调整后重新申请。'
        }
        this.confirm.visible = false
        toast.success('已处理并完成服务器回读')
      } catch (error) {
        toast.error(error?.message || '题目调整审核失败')
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.tc-command { display: grid; grid-template-columns: minmax(0, 1fr) minmax(220px, .38fr); gap: var(--space-4); align-items: center; margin-bottom: var(--space-3); padding: 12px 14px; border: 1px solid var(--primary-100, #dbeafe); border-radius: var(--radius-lg, 12px); background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--card, #fff) 78%); }
.tc-command > div { display: grid; min-width: 0; gap: 2px; }
.tc-command span { color: var(--primary-600, #2563eb); font-size: var(--font-size-xs, 12px); font-weight: 700; }
.tc-command strong { overflow: hidden; color: var(--text-primary, #0f172a); font-size: var(--font-size-sm, 13px); text-overflow: ellipsis; white-space: nowrap; }
.tc-command small { color: var(--text-tertiary, #64748b); font-size: var(--font-size-xs, 12px); line-height: 1.5; }
.tc-command__next { padding-left: var(--space-4); border-left: 1px solid var(--primary-100, #dbeafe); }
.tc-receipt { display: flex; align-items: center; gap: var(--space-4); margin-bottom: var(--space-3); padding: 11px 12px; border: 1px solid var(--success-200, #bbf7d0); border-radius: var(--radius-md, 8px); background: var(--success-50, #f0fdf4); }
.tc-receipt > div { display: grid; flex: 1; gap: 2px; }
.tc-receipt strong { color: var(--success-700, #15803d); }
.tc-receipt span, .tc-receipt small { color: var(--text-secondary, #475569); font-size: var(--font-size-xs, 12px); }
.tc-receipt button { border: 0; background: transparent; color: var(--primary-600, #2563eb); cursor: pointer; }
.is-command-locked { pointer-events: none; opacity: .72; }
.mp-link { margin-left: var(--space-2); }
.mp-link:first-child { margin-left: 0; }
.mp-link:disabled { cursor: not-allowed; opacity: .5; }
.mp-link--danger { color: var(--danger-600, #dc2626); }
@media (max-width: 760px) { .tc-command { grid-template-columns: 1fr; } .tc-command__next { padding-left: 0; padding-top: var(--space-3); border-left: 0; border-top: 1px solid var(--primary-100, #dbeafe); } }
</style>
