<template>
  <ModulePageShell
    class="aa-registration-batches"
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton v-if="canManage" variant="primary" :disabled="createBlocked" @click="toggleCreate">创建{{ typeLabel ? typeLabel + '批次' : '注册批次' }}</AppButton>
    </template>

    <div class="mp-stack">
      <section class="aa-batch-flow" aria-label="注册办理顺序">
        <AppStepBar :steps="registrationSteps" :current="-1" />
        <p class="aa-batch-flow__note">办理顺序参考；不同批次分别推进，当前状态以列表中的正式记录为准。</p>
      </section>
      <section v-if="!loading && !error" class="aa-batch-metrics" aria-label="当前页注册批次概况">
        <article v-for="item in summaryCards" :key="item.label" :class="['aa-batch-metric', `is-${item.tone}`]">
          <span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.note }}</small>
        </article>
      </section>
      <AppInlineAlert v-if="createWrite.pending && !creating" type="warning">新建注册批次的结果尚未确认，已暂停重复创建。现有接口没有按本次命令查询结果的能力，不能根据同名或相似名称认定已经创建或未创建。</AppInlineAlert>
      <AppInlineAlert v-if="createWriteVisible && createWrite.error" type="danger">{{ createWrite.error }}</AppInlineAlert>
      <AppInlineAlert v-if="createWriteVisible && createWrite.receipt" type="success">已创建批次 {{ createWrite.receipt.batchId }}「{{ createWrite.receipt.batchName }}」：{{ typeLabelOf(createWrite.receipt.registerType) }}，本次回执状态为{{ statusLabel(createWrite.receipt.status) }}。注册窗口起止未在正式回执中返回，本页未核对其落库值。</AppInlineAlert>
      <AppInlineAlert v-if="batchWrite.pending && !busyId" type="warning">有关闭/归档请求尚未取得可核对的正式回执，已暂停重复提交。请在原身份和原批次核对当前正式状态；当前状态不能证明本次命令是否成功。</AppInlineAlert>
      <AppInlineAlert v-if="batchWriteVisible && batchWrite.error" type="danger">{{ batchWrite.error }}</AppInlineAlert>
      <AppInlineAlert v-if="batchWriteVisible && batchWrite.receipt" type="success">批次 {{ batchWrite.receipt.batchId }}：本次正式回执为{{ statusLabel(batchWrite.receipt.status) }}，后续状态以重新读取的批次记录为准。</AppInlineAlert>
      <AppSectionCard v-if="batchWriteVisible && batchWrite.pending" title="核对原批次正式状态">
        <p>批次 ID：{{ batchWrite.target.row.batchId }} · 本次操作：{{ batchWrite.target.kind === 'close' ? '关闭' : '归档' }}</p>
        <AppButton :disabled="!!busyId || batchWrite.checking || !canReadBatchOutcome" @click="readBatchOutcome">{{ batchWrite.checking ? '正在读取…' : '只读核对原批次' }}</AppButton>
        <p v-if="!canReadBatchOutcome" class="mp-note">当前身份缺少注册批次查看权限，无法读取正式批次状态。</p>
        <p v-if="batchWrite.readRow" class="mp-note">当前正式状态：{{ statusLabel(batchWrite.readRow.status) }}。这是当前记录状态，本次命令结果仍未知，重复关闭/归档继续暂停。</p>
        <AppInlineAlert v-if="batchWrite.readError" type="warning">{{ batchWrite.readError }}</AppInlineAlert>
      </AppSectionCard>
      <AppSectionCard v-if="showCreate && canManage" :title="'新建' + (typeLabel || '注册批次')">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称
            <input v-model.trim="draft.batchName" class="aa-input" :disabled="createBlocked" placeholder="如 2026级新生入学注册" maxlength="50" />
          </label>
          <label class="aa-cal-form__item">
            类型
            <AppSelect v-model="draft.registerType" :options="registerTypeOptions" :disabled="!!fixedType || createBlocked" />
          </label>
          <label class="aa-cal-form__item">
            注册窗口
            <AppDateRangePicker v-model="windowRange" mode="form" :disabled="createBlocked" />
          </label>
          <label class="aa-cal-form__item aa-cal-form__check">
            <input v-model="draft.open" type="checkbox" :disabled="createBlocked" /> 创建后立即开放
          </label>
          <AppButton variant="primary" :disabled="createBlocked || !draft.batchName.trim()" :loading="creating" @click="createBatch">
            创建
          </AppButton>
        </div>
      </AppSectionCard>

      <AppSectionCard :title="`${typeLabel || '注册'}批次 · 批次列表`" class="aa-batch-list" no-padding>
        <form class="aa-batch-filters" @submit.prevent="applyFilters">
          <label class="aa-batch-filters__search">
            <span class="aa-batch-label">批次名称 / ID</span>
            <input v-model="filters.keyword" class="aa-input" type="search" maxlength="200" :disabled="creating || !!busyId" placeholder="搜索本页批次名称或 ID" @keydown.enter.prevent="applyFilters" />
          </label>
          <label class="aa-batch-filters__status">
            <span class="aa-batch-label">正式状态</span>
            <AppSelect v-model="filters.status" :options="statusOptions" :disabled="creating || !!busyId" />
          </label>
          <AppButton :disabled="creating || !!busyId" @click="applyFilters">查询</AppButton>
          <AppButton variant="ghost" :disabled="creating || !!busyId" @click="clearFilters">清空</AppButton>
          <p v-if="!loading && !error" class="aa-batch-filters__count">共 {{ pagination.total }} 个批次 · 第 {{ pagination.page }} 页<br />名称 / ID 仅检索本页 {{ rows.length }} 条记录</p>
        </form>
        <p class="aa-batch-data-note">{{ missingFieldsNote }}请进入原批次核对具体学生；人数未提供不表示 0 人。</p>
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <template v-else-if="!rows.length">
          <EmptyState :title="appliedStatus ? '当前状态下没有批次' : '当前页暂无注册批次'" description="可清空筛选查看；具有创建权限时，可在右上方建立批次。" />
          <div v-if="pagination.page > 1" class="aa-batch-empty-return"><AppButton @click="onPageChange(1)">返回第一页</AppButton></div>
        </template>
        <template v-else>
          <AppInlineAlert v-if="appliedKeyword && !visibleRows.length" type="info" class="aa-batch-search-empty">本页未找到匹配批次。其他页尚未搜索，可清空检索或继续翻页。</AppInlineAlert>
          <DataTable :columns="columns" :rows="visibleRows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
            <template #cell-batchName="{ row }">
              <button class="mp-link aa-batch-name" :disabled="creating || !!busyId" @click="goDetail(row)">{{ row.batchName || '批次名称未提供' }}</button>
              <span class="aa-batch-id">ID {{ row.batchId }} · {{ typeLabelOf(row.registerType) }}</span>
            </template>
            <template #cell-type="{ row }">{{ typeLabelOf(row.registerType) }}</template>
            <template v-for="column in unavailableColumns" :key="column.key" #[`cell-${column.key}`]>
              <span class="aa-batch-unavailable">待核对</span>
              <span class="aa-batch-id">批次列表未提供</span>
            </template>
            <template #cell-status="{ row }">
              <AppStatusTag :status="row.status" dot>{{ statusLabel(row.status) }}</AppStatusTag>
              <span class="aa-batch-id">{{ batchStateHint(row.status) }}</span>
            </template>
            <template #cell-actions="{ row }">
              <div class="aa-batch-actions">
                <button class="mp-link" :disabled="creating || !!busyId" @click="goDetail(row)">注册名单</button>
                <button v-if="canArchive && row.status === 'OPEN'" class="mp-link" :disabled="batchActionsBlocked" @click="askClose(row)">关闭</button>
                <button v-if="canArchive && row.status === 'CLOSED'" class="mp-link" :disabled="batchActionsBlocked" @click="askArchive(row)">归档</button>
              </div>
            </template>
          </DataTable>
        </template>
      </AppSectionCard>
    </div>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :submitting="!!busyId"
      :confirm-disabled="batchActionsBlocked"
      @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 注册批次列表（/admin/academic-affairs/registration）：GET/POST /academic-affairs/registration-batches。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppDateRangePicker, AppSelect, AppInlineAlert, AppStepBar } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { matchPermission } from '@/config/navPlan'

const STATUS_LABEL = { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已关闭', ARCHIVED: '已归档' }
const TYPE_LABEL = { ENROLL: '入学注册', ANNUAL: '学年注册', SEMESTER: '学期注册' }

export default {
  name: 'AaRegistrationBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppDateRangePicker, AppSelect, AppInlineAlert, AppStepBar },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      loading: true, requestVersion: 0, disposed: false, scopeVersion: 0,
      error: '',
      rows: [],
      filters: { keyword: '', status: '' }, appliedKeyword: '', appliedStatus: '',
      showCreate: false,
      creating: false,
      createForm: null,
      createWrite: { target: null, pending: null, receipt: null, error: '', deniedIdentity: '' },
      busyId: '',
      batchWrite: { target: null, pending: null, receipt: null, error: '', checking: false, readRow: null, readError: '', deniedIdentity: '' },
      draft: { batchName: '', registerType: 'ENROLL', windowStart: '', windowEnd: '', open: false },
      pagination: { page: 1, pageSize: 20, total: 0 },
      confirm: { visible: false, title: '', message: '', type: 'primary' },
      pendingAction: null
    }
  },
  computed: {
    registrationSteps() {
      return [
        { title: '创建批次', description: '注册管理岗建立来源' },
        { title: '圈定候选', description: '进入原批次核对学生' },
        { title: '资格核验', description: '按学生逐项核验证据' },
        { title: '正式注册', description: '以正式命令回执为准' },
        { title: '关闭归档', description: '核对批次关闭与归档状态' }
      ].map(step => ({ ...step, status: 'wait' }))
    },
    unavailableColumns() {
      if (this.fixedType === 'ENROLL') return [{ key: 'grade', title: '招生年级' }, { key: 'term', title: '学期' }, { key: 'candidateCount', title: '候选学生' }]
      if (this.fixedType === 'ANNUAL') return [{ key: 'year', title: '学年' }, { key: 'studentScope', title: '学生范围' }, { key: 'registeredCount', title: '已注册人数' }]
      if (this.fixedType === 'SEMESTER') return [{ key: 'term', title: '学期' }, { key: 'studentScope', title: '学生范围' }, { key: 'registeredCount', title: '已注册人数' }]
      return [{ key: 'studentScope', title: '学生范围' }, { key: 'registeredCount', title: '已注册人数' }]
    },
    columns() {
      return [{ key: 'batchName', title: '批次名称', width: '27%' },
        ...(!this.fixedType ? [{ key: 'type', title: '类型' }] : []), ...this.unavailableColumns,
        { key: 'status', title: '状态', width: '160px' }, { key: 'actions', title: '办理入口', width: '150px' }]
    },
    missingFieldsNote() { return `当前批次列表未提供${this.unavailableColumns.map(column => column.title).join('、')}。` },
    statusOptions() { return [{ value: '', label: '全部状态' }, ...Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label }))] },
    visibleRows() {
      const keyword = this.appliedKeyword.toLocaleLowerCase()
      return keyword ? this.rows.filter(row => String(row.batchName || '').toLocaleLowerCase().includes(keyword) || String(row.batchId).includes(keyword)) : this.rows
    },
    canManage() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.manage') },
    createBlocked() { return !this.canManage || this.creating || !!this.busyId || !!this.createWrite.pending || this.createWrite.deniedIdentity === this.batchActionIdentity() },
    createWriteVisible() { return !!this.createWrite.target && this.createWrite.target.identity === this.batchActionIdentity() && this.createWrite.target.context === this.contextKey },
    canArchive() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.archive.manage') },
    batchActionsBlocked() { return !!this.busyId || !!this.batchWrite.pending || this.batchWrite.checking || this.batchWrite.deniedIdentity === this.batchActionIdentity() },
    batchWriteVisible() {
      const target = this.batchWrite.target
      return !!target && target.identity === this.batchActionIdentity() && (!this.fixedType || target.row.registerType === this.fixedType)
    },
    canReadBatchOutcome() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.registration.view') },
    contextKey() { return JSON.stringify([this.scopeVersion, this.ctx, this.fixedType]) },
    registerTypeOptions() {
      return Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))
    },
    /** ?type=ENROLL/ANNUAL/SEMESTER 收窄为对应三级叶子视图；无 type 为原「注册批次」通栏视图。 */
    fixedType() {
      const t = this.$route && this.$route.query && this.$route.query.type
      return t === 'ENROLL' || t === 'ANNUAL' || t === 'SEMESTER' ? t : ''
    },
    typeLabel() {
      return TYPE_LABEL[this.fixedType] || ''
    },
    pageTitle() {
      return this.typeLabel || '注册批次'
    },
    pageSubtitle() {
      if (this.fixedType === 'ENROLL') return '新生入学注册批次：核身份/专业/班级，报到缴费材料齐全后完成注册'
      if (this.fixedType === 'ANNUAL') return '在籍学生学年注册批次：核对上学年状态/缴费后完成续注册'
      if (this.fixedType === 'SEMESTER') return '在籍学生按学期开的续注册批次：核对本学期在籍/缴费状态后完成注册'
      return '按入学 / 学年 / 学期建立注册批次；批次开放后逐个学生注册（经学籍单一入口写主档）'
    },
    summaryCards() {
      const count = (...states) => this.rows.filter(row => states.includes(row.status)).length
      return [
        { label: '本页批次', value: this.rows.length, note: `正式总数 ${this.pagination.total}`, tone: 'primary' },
        { label: '待启动', value: count('DRAFT'), note: '等待开放候选范围', tone: 'neutral' },
        { label: '进行中', value: count('OPEN'), note: '资格核验与正式注册', tone: 'primary' },
        { label: '已关闭 / 归档', value: count('CLOSED', 'ARCHIVED'), note: '可回查正式回执', tone: 'success' }
      ]
    },
    /** AppDateRangePicker（mode=form）v-model 代理：对内仍是 draft.windowStart/windowEnd 两个字段，创建提交逻辑不用改。 */
    windowRange: {
      get() { return { start: this.draft.windowStart, end: this.draft.windowEnd } },
      set(v) { if (this.createBlocked) return; this.draft.windowStart = (v && v.start) || ''; this.draft.windowEnd = (v && v.end) || '' }
    }
  },
  watch: {
    ctx: { deep: true, handler() { this.scopeVersion++; this.confirm.visible = false; this.pendingAction = null; this.showCreate = false; this.createForm = null; this.clearCreateDraft(); this.load() } },
    '$route.query': { deep: true, handler() { if (this.restoreListQuery()) this.load() } },
    '$route.query.type'() {
      this.draft.registerType = this.fixedType || 'ENROLL'
      this.showCreate = false; this.createForm = null
      this.restoreListQuery()
      this.confirm.visible = false; this.pendingAction = null
      this.load()
    }
  },
  created() {
    this.restoreListQuery()
    if (this.fixedType) this.draft.registerType = this.fixedType
    this.load()
  },
  beforeRouteUpdate(to, from, next) { next(!this.creating && !this.busyId) },
  beforeUnmount() { this.disposed = true; this.requestVersion++ },
  methods: {
    restoreListQuery() {
      const query = this.$route.query || {}, rawPage = Number(query.page), rawSize = Number(query.pageSize)
      const page = Number.isSafeInteger(rawPage) && rawPage > 0 ? rawPage : 1
      const pageSize = [10, 20, 50, 100].includes(rawSize) ? rawSize : 20
      const keyword = typeof query.keyword === 'string' ? query.keyword.trim().slice(0, 200) : ''
      const status = typeof query.status === 'string' && Object.hasOwn(STATUS_LABEL, query.status) ? query.status : ''
      const changed = page !== this.pagination.page || pageSize !== this.pagination.pageSize || status !== this.appliedStatus
      const selectionChanged = changed || keyword !== this.appliedKeyword
      this.pagination.page = page; this.pagination.pageSize = pageSize
      this.filters = { keyword, status }; this.appliedKeyword = keyword; this.appliedStatus = status
      if (selectionChanged) { this.confirm.visible = false; this.pendingAction = null }
      return changed
    },
    syncListQuery() {
      this.$router.replace({ query: { ...this.$route.query, page: String(this.pagination.page), pageSize: String(this.pagination.pageSize),
        keyword: this.appliedKeyword || undefined, status: this.appliedStatus || undefined } })
    },
    applyFilters() {
      if (this.creating || this.busyId || this.disposed) return
      const status = Object.hasOwn(STATUS_LABEL, this.filters.status) ? this.filters.status : ''
      const statusChanged = status !== this.appliedStatus
      this.appliedStatus = status; this.appliedKeyword = this.filters.keyword.trim().slice(0, 200)
      this.filters = { keyword: this.appliedKeyword, status }
      this.confirm.visible = false; this.pendingAction = null
      if (statusChanged) this.pagination.page = 1
      this.syncListQuery()
      if (statusChanged) this.load()
    },
    clearFilters() {
      if (this.creating || this.busyId || this.disposed) return
      this.filters = { keyword: '', status: '' }; this.applyFilters()
    },
    batchStateHint(status) {
      return { DRAFT: '尚未开放注册', OPEN: '可进入名单核对资格', CLOSED: '本批次不再接受注册', ARCHIVED: '已进入注册归档' }[status] || '暂停状态相关操作'
    },
    statusLabel(s) {
      return STATUS_LABEL[s] || (s ? '状态待确认' : '')
    },
    typeLabelOf(t) {
      return TYPE_LABEL[t] || (t ? '类型待确认' : '')
    },
    goDetail(row) {
      if (this.busyId || this.creating) return
      this.$router.push({ path: `/admin/academic-affairs/registration/${row.batchId}`, query: { returnToken: this.academicFlow?.captureReturn() } })
    },
    onPageChange(page) {
      if (this.creating || this.busyId || this.disposed) return
      this.pagination.page = page
      this.confirm.visible = false; this.pendingAction = null
      this.syncListQuery()
      this.load()
    },
    askClose(row) {
      if (!this.canArchive || this.batchActionsBlocked || row.status !== 'OPEN') return
      this.confirm = { visible: true, title: '关闭注册批次',
        message: `确认关闭「${row.batchName}」？关闭后不可再为学生办理本批次注册。`, type: 'warning' }
      this.pendingAction = { kind: 'close', row: { ...row, batchId: String(row.batchId) }, context: this.contextKey, identity: this.batchActionIdentity() }
    },
    askArchive(row) {
      if (!this.canArchive || this.batchActionsBlocked || row.status !== 'CLOSED') return
      this.confirm = { visible: true, title: '归档注册批次',
        message: `确认归档「${row.batchName}」？批次将进入「注册归档」供查阅与导出。暂缓与异常记录尚未统一封存，此操作不代表关联台账全部只读。`, type: 'primary' }
      this.pendingAction = { kind: 'archive', row: { ...row, batchId: String(row.batchId) }, context: this.contextKey, identity: this.batchActionIdentity() }
    },
    batchActionIdentity() { return this.academicFlow?.identity?.() || JSON.stringify(this.ctx) },
    clearDeniedBatchData(target, message) {
      if (this.disposed || target.identity !== this.batchActionIdentity()) return
      this.requestVersion++; this.rows = []; this.pagination.total = 0; this.loading = false
      this.confirm.visible = false; this.pendingAction = null; this.showCreate = false
      this.batchWrite.receipt = null; this.batchWrite.readRow = null; this.batchWrite.deniedIdentity = target.identity
      this.error = message || '当前身份无法操作此批次，请重新核对权限'
    },
    async onConfirm() {
      if (!this.canArchive || this.batchActionsBlocked) return
      const a = this.pendingAction
      this.confirm.visible = false
      this.pendingAction = null
      if (!a || this.disposed || a.context !== this.contextKey || a.identity !== this.batchActionIdentity()) return
      this.busyId = a.row.batchId
      this.batchWrite.target = a; this.batchWrite.pending = a; this.batchWrite.receipt = null
      this.batchWrite.error = ''; this.batchWrite.readRow = null; this.batchWrite.readError = ''
      let res
      try {
        res = a.kind === 'close'
          ? await academicAffairsApi.closeRegistrationBatch(a.row.batchId)
          : await academicAffairsApi.archiveRegistrationBatch(a.row.batchId)
      } catch { res = null }
      this.busyId = ''
      const current = !this.disposed && a.context === this.contextKey && a.identity === this.batchActionIdentity()
      if (res?.code === 0 && String(res.data?.batchId) === a.row.batchId && res.data?.status === (a.kind === 'close' ? 'CLOSED' : 'ARCHIVED')) {
        this.batchWrite.pending = null
        if (current) { this.batchWrite.receipt = { ...res.data }; this.load() }
        return
      }
      const code = Number(res?.code)
      const denied = String(code).startsWith('403') || ['NO_PERMISSION', 'NO_DATA_SCOPE'].includes(res?.bizCode)
      const conflict = String(code).startsWith('409') || res?.bizCode === 'DATA_CONFLICT'
      const rejected = denied || conflict || ['VALIDATION_ERROR', 'DATA_NOT_FOUND'].includes(res?.bizCode) ||
        (code >= 400 && code < 500) || (code >= 400000 && code < 500000)
      if (rejected) {
        this.batchWrite.pending = null
        if (current) {
          this.batchWrite.error = res?.message || '操作未完成，请重新核对批次'
          if (denied) this.clearDeniedBatchData(a, this.batchWrite.error)
          else if (conflict) this.load()
        }
      } else if (current) {
        this.batchWrite.error = '未取得对象和状态一致的正式回执，本次结果未知；请先只读核对原批次，暂停重复提交。'
      }
    },
    async readBatchOutcome() {
      const target = this.batchWrite.pending
      if (!target || this.disposed || this.busyId || this.batchWrite.checking || !this.canReadBatchOutcome || target.identity !== this.batchActionIdentity()) return
      const context = this.contextKey
      const current = () => !this.disposed && context === this.contextKey && target.identity === this.batchActionIdentity() && this.batchWrite.pending === target
      this.batchWrite.checking = true; this.batchWrite.readError = ''; this.batchWrite.readRow = null
      try {
        for (let page = 1; page <= 5; page++) {
          const res = await academicAffairsApi.getRegistrationBatches({ page, pageSize: 100 })
          if (!current()) return
          if (String(res?.code).startsWith('403') || ['NO_PERMISSION', 'NO_DATA_SCOPE'].includes(res?.bizCode)) {
            this.clearDeniedBatchData(target, res?.message); this.batchWrite.readError = res?.message || '无法读取原批次'; return
          }
          if (res?.code !== 0 || !Array.isArray(res.data?.list) || !Number.isSafeInteger(res.data?.total) || res.data.total < 0) throw new Error(res?.message || '批次列表回执不完整')
          const row = res.data.list.find(item => String(item.batchId) === target.row.batchId)
          if (row) {
            if (!Object.hasOwn(STATUS_LABEL, row.status) || (target.row.registerType && row.registerType !== target.row.registerType)) throw new Error('原批次类型或状态无法核对')
            this.batchWrite.readRow = { ...row }; return
          }
          if (page * 100 >= res.data.total) break
        }
        if (current()) this.batchWrite.readError = '在本次最多 500 条批次记录中未定位原 ID，不能据此认定操作未执行；本次写结果仍未知。'
      } catch (error) {
        if (current()) this.batchWrite.readError = error?.message || '正式批次状态读取失败，本次写结果仍未知'
      } finally { this.batchWrite.checking = false }
    },
    toggleCreate() {
      if (this.createBlocked || this.disposed) return
      this.showCreate = !this.showCreate
      this.createForm = this.showCreate ? { identity: this.batchActionIdentity(), context: this.contextKey } : null
    },
    clearCreateDraft() {
      this.draft = { batchName: '', registerType: this.fixedType || 'ENROLL', windowStart: '', windowEnd: '', open: false }
    },
    createDraftBody() {
      return { batchName: this.draft.batchName.trim(), registerType: this.fixedType || this.draft.registerType,
        windowStart: this.draft.windowStart || undefined, windowEnd: this.draft.windowEnd || undefined, open: this.draft.open }
    },
    createTargetCurrent(target) {
      return !!target && !this.disposed && target.identity === this.batchActionIdentity() && target.context === this.contextKey &&
        target.form === this.createForm && target.draft === this.draft && JSON.stringify(target.body) === JSON.stringify(this.createDraftBody())
    },
    async createBatch() {
      if (this.createBlocked || this.disposed || !this.showCreate || !this.draft.batchName.trim() ||
        this.createForm?.identity !== this.batchActionIdentity() || this.createForm?.context !== this.contextKey) return
      const target = { identity: this.batchActionIdentity(), context: this.contextKey, form: this.createForm, draft: this.draft,
        body: Object.freeze(this.createDraftBody()) }
      if (!Object.hasOwn(TYPE_LABEL, target.body.registerType)) return
      this.creating = true
      this.createWrite.target = target; this.createWrite.pending = target; this.createWrite.receipt = null; this.createWrite.error = ''
      let res
      try { res = await academicAffairsApi.createRegistrationBatch(target.body) } catch { res = null }
      this.creating = false
      const data = res?.data
      const valid = res?.code === 0 && typeof data?.batchId === 'string' && /^[1-9]\d*$/.test(data.batchId) &&
        data.batchName === target.body.batchName && data.registerType === target.body.registerType && data.status === (target.body.open ? 'OPEN' : 'DRAFT')
      if (valid) {
        this.createWrite.pending = null
        if (this.createTargetCurrent(target)) {
          this.createWrite.receipt = { ...data }; this.showCreate = false; this.createForm = null; this.clearCreateDraft(); this.load()
        }
        return
      }
      const code = Number(res?.code)
      const denied = String(code).startsWith('403') || ['NO_PERMISSION', 'NO_DATA_SCOPE'].includes(res?.bizCode)
      const rejected = denied || ['DATA_CONFLICT', 'DATA_NOT_FOUND', 'VALIDATION_ERROR'].includes(res?.bizCode) ||
        (code >= 400 && code < 500) || (code >= 400000 && code < 500000)
      if (rejected) {
        this.createWrite.pending = null
        if (this.createTargetCurrent(target)) {
          this.createWrite.error = res?.message || '创建未完成，请核对输入和权限'
          if (denied) {
            this.createWrite.deniedIdentity = target.identity; this.showCreate = false; this.createForm = null; this.clearCreateDraft()
            this.createWrite.target = { identity: target.identity, context: target.context }
          }
        }
      } else if (this.createTargetCurrent(target)) {
        this.createWrite.error = '未取得对象、名称、类型和状态一致的创建回执，本次结果未知，已暂停重复创建。'
      }
    },
    async load() {
      const version = ++this.requestVersion, context = this.contextKey
      this.loading = true
      this.rows = []
      this.error = ''
      const params = { page: this.pagination.page, pageSize: this.pagination.pageSize }
      if (this.fixedType) params.registerType = this.fixedType
      if (this.appliedStatus) params.status = this.appliedStatus
      try {
        const res = await academicAffairsApi.getRegistrationBatches(params)
        if (this.disposed || version !== this.requestVersion || context !== this.contextKey) return
        if (res?.code === 0 && Array.isArray(res.data?.list) && Number.isSafeInteger(res.data.total) && res.data.total >= 0) {
          this.rows = res.data.list
          this.pagination.total = res.data.total
        } else this.error = res?.message || '注册批次列表读取失败，请重试'
      } catch {
        if (!this.disposed && version === this.requestVersion && context === this.contextKey) this.error = '注册批次列表读取失败，请重试'
      } finally {
        if (!this.disposed && version === this.requestVersion && context === this.contextKey) {
          this.loading = false
          this.academicFlow?.restorePosition()
        }
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-registration-batches { min-width: 0; }
.aa-batch-flow { padding: 17px 18px 12px; border: 1px solid var(--card-b, #dce5ef); border-radius: 12px; background: var(--bg-card, #fff); overflow-x: auto; }
.aa-batch-flow :deep(.app-step-bar) { min-width: 650px; gap: 12px; }
.aa-batch-flow :deep(.app-step-bar__title) { font-size: 13px; font-weight: 600; }
.aa-batch-flow :deep(.app-step-bar__desc) { font-size: 11px; line-height: 1.6; }
.aa-batch-flow :deep(.app-step-bar__line) { display: none; }
.aa-batch-flow__note { margin: 12px 0 0; font-size: 12px; color: var(--t3, #65778b); }
.aa-batch-list { overflow: hidden; }
.aa-batch-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.aa-batch-metric { display: grid; gap: 7px; min-height: 92px; padding: 15px 16px; border: 1px solid var(--card-b, #dce5ef); border-radius: 12px; background: var(--bg-card, #fff); }
.aa-batch-metric span, .aa-batch-metric small { color: var(--t3, #65778b); font-size: 12px; }
.aa-batch-metric strong { color: var(--t1, #18304f); font-size: 25px; line-height: 1; }
.aa-batch-metric.is-success { border-color: #cfe6d7; }
.aa-batch-filters { display: flex; align-items: flex-end; gap: 9px; flex-wrap: wrap; padding: 14px 16px 10px; }
.aa-batch-label { display: block; margin-bottom: 6px; font-size: 12px; color: var(--t2, #4e6075); }
.aa-batch-filters__search { flex: 0 1 270px; min-width: 200px; }
.aa-batch-filters__search .aa-input { width: 100%; }
.aa-batch-filters__status { width: 140px; }
.aa-batch-filters__count { margin: 0 0 1px auto; color: var(--t3, #65778b); font-size: 12px; line-height: 1.6; text-align: right; }
.aa-batch-data-note { margin: 0; padding: 0 16px 12px; color: var(--t3, #65778b); font-size: 12px; line-height: 1.7; }
.aa-batch-list :deep(.dt) { border: 0; border-radius: 0; box-shadow: none; }
.aa-batch-list :deep(.dt__table) { min-width: 800px; }
.aa-batch-list :deep(.dt__th) { background: var(--pri-bg, #edf3fc); padding: 12px 14px; font-size: 12px; }
.aa-batch-list :deep(.dt__td) { padding: 14px; font-size: 13px; vertical-align: middle; }
.aa-batch-name { display: inline-block; padding: 0; text-align: left; font-size: 13px; font-weight: 600; overflow-wrap: anywhere; line-height: 1.6; }
.aa-batch-id { display: block; margin-top: 4px; color: var(--t3, #65778b); font-size: 11px; line-height: 1.6; overflow-wrap: anywhere; }
.aa-batch-unavailable { color: var(--t2, #4e6075); }
.aa-batch-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.aa-batch-search-empty { margin: 0 16px 12px; }
.aa-batch-empty-return { padding: 0 16px 18px; text-align: center; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-cal-form__check { flex-direction: row; align-items: center; gap: 6px; }
.aa-input, .aa-select {
  height: 34px; padding: 0 10px;
  border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px;
  background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box;
}
@media (max-width: 760px) {
  .aa-batch-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .aa-batch-filters__search { flex-grow: 1; }
  .aa-batch-filters__count { width: 100%; margin-left: 0; text-align: left; }
}
</style>
