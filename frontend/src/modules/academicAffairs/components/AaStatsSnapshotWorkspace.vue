<template>
  <section class="assw" aria-label="统计快照工作区">
    <div class="assw-head">
      <div>
        <div class="assw-title">统计快照</div>
        <p>把当前教务总览冻结为可追溯历史证据；后续实时源数据变化不会回写已冻结快照。</p>
      </div>
      <AppButton v-if="canCreate" variant="primary" :disabled="loading || saving" @click="openCreate">冻结当前统计</AppButton>
    </div>

    <AppInlineAlert
      type="info"
      description="快照保存当时的统计结果，便于期末留档和历史对照；后续数据更新不会改变已保存的快照。"
    />

    <div v-if="canView" class="assw-filter">
      <label>
        <span>学期</span>
        <AppTermEntityPicker v-model="listFilters.termId" placeholder="全部学期" :disabled="loading" />
      </label>
      <label>
        <span>快照类型</span>
        <select v-model="listFilters.snapshotType" :disabled="loading">
          <option value="">全部类型</option>
          <option value="OVERVIEW">教务总览</option>
        </select>
      </label>
      <div class="assw-filter__actions">
        <AppButton :loading="loading" @click="search">查询</AppButton>
        <AppButton variant="ghost" :disabled="loading" @click="resetSearch">清空</AppButton>
      </div>
    </div>

    <AppInlineAlert
      v-if="!canView"
      type="warning"
      description="当前身份没有查看统计快照的权限，请联系学校管理员。"
    />
    <ErrorState v-else-if="error" title="统计快照加载失败" :description="error" @retry="load" />
    <LoadingState v-else-if="loading && !loadedOnce" />
    <EmptyState v-else-if="!rows.length" title="暂无统计快照" description="有创建权限的教务管理员可冻结当前教务总览作为历史证据" />
    <DataTable
      v-else
      :columns="columns"
      :rows="rows"
      row-key="snapshotId"
      :pagination="pagination"
      @page-change="onPageChange"
    >
      <template #cell-type="{ row }">{{ snapshotTypeLabel(row.snapshotType) }}</template>
      <template #cell-scope="{ row }">
        <div>{{ scopeLabel(row) }}</div>
        <div class="mp-cell-sub">{{ filterLabel(row) }}</div>
      </template>
      <template #cell-generated="{ row }">
        <div>{{ formatTime(row.generatedAt) }}</div>
        <div class="mp-cell-sub">源数据截至 {{ formatTime(row.sourceAsOf) }}</div>
      </template>
      <template #cell-operator="{ row }"><span class="assw-mono">{{ row.generatedBy || '—' }}</span></template>
      <template #cell-hash="{ row }"><span class="assw-hash" :title="row.payloadHash">{{ shortHash(row.payloadHash) }}</span></template>
      <template #cell-status="{ row }"><StatusTag type="success" :label="academicStatusLabel(row.status)" dot /></template>
      <template #cell-integrity="{ row }">
        <StatusTag
          :type="verified[row.snapshotId] ? 'success' : 'default'"
          :label="verified[row.snapshotId] ? '服务端校验通过' : '待本次复核'"
          dot
        />
      </template>
      <template #cell-actions="{ row }"><AppButton size="small" variant="ghost" @click="openDetail(row)">详情 / 校验</AppButton></template>
    </DataTable>

    <AppDrawer :visible="createVisible" title="冻结当前教务统计" mode="modal" size="large" @close="closeCreate">
      <div class="assw-form">
        <AppInlineAlert
          type="warning"
          description="冻结的是当前时点统计证据。后续源数据变化不会回写该历史快照。"
        />
        <label>
          <span>快照类型</span>
          <select v-model="createForm.snapshotType" :disabled="saving">
            <option value="OVERVIEW">教务总览</option>
          </select>
        </label>
        <label>
          <span>学期</span>
          <AppTermEntityPicker v-model="createForm.termId" placeholder="全部学期" :disabled="saving" />
        </label>
        <label>
          <span>学院</span>
          <AppCollegePicker v-model="createForm.collegeId" placeholder="全校 / 当前授权学院" :disabled="saving" @change="createForm.majorId = ''" />
        </label>
        <label>
          <span>专业</span>
          <AppMajorPicker v-model="createForm.majorId" :query="{ collegeId: createForm.collegeId || undefined }" placeholder="全部专业" :disabled="saving" />
        </label>
        <label>
          <span>冻结原因（至少 5 个字）</span>
          <textarea v-model.trim="createForm.reason" rows="4" maxlength="500" :disabled="saving" placeholder="如：学期末正式统计留档" />
        </label>
        <AppInlineAlert v-if="createError" type="danger" :description="createError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="closeCreate">取消</AppButton>
        <AppButton variant="primary" :disabled="saving || createForm.reason.length < 5" @click="confirmCreate">确认冻结</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirmVisible"
      title="确认冻结统计快照"
      :message="confirmationMessage"
      type="warning"
      confirm-text="确认冻结"
      :submitting="saving"
      @confirm="submitCreate"
    />

    <AppDrawer :visible="detailVisible" title="统计快照详情" mode="modal" size="large" @close="closeDetail">
      <LoadingState v-if="detailLoading" />
      <ErrorState v-else-if="detailError" title="快照详情读取失败" :description="detailError" @retry="reloadDetail" />
      <template v-else-if="detail">
        <div class="assw-detail-head">
          <div>
            <strong>快照 #{{ detail.snapshotId }} · {{ snapshotTypeLabel(detail.snapshotType) }}</strong>
            <div class="mp-cell-sub">冻结于 {{ formatTime(detail.generatedAt) }} · 源数据截至 {{ formatTime(detail.sourceAsOf) }}</div>
          </div>
          <StatusTag type="success" label="不可变" dot />
        </div>

        <div class="assw-kv">
          <div><span>筛选范围</span><strong>{{ scopeLabel(detail) }} · {{ filterLabel(detail) }}</strong></div>
          <div><span>操作人标识</span><strong class="assw-mono">{{ detail.generatedBy || '—' }}</strong></div>
          <div><span>冻结原因</span><strong>{{ detail.reason || '历史记录未回填原因' }}</strong></div>
          <div><span>状态</span><strong>{{ academicStatusLabel(detail.status) }}</strong></div>
        </div>

        <div class="assw-section">
          <div class="assw-section__title">payloadHash</div>
          <code class="assw-code">{{ detail.payloadHash || '—' }}</code>
        </div>
        <div class="assw-section">
          <div class="assw-section__title">冻结 payload</div>
          <pre class="assw-json">{{ prettyPayload }}</pre>
        </div>
        <AppInlineAlert
          v-if="verified[detail.snapshotId]"
          type="success"
          description="后端已重新计算并确认 payload 与持久化 payloadHash 一致；本次复核未修改快照。"
        />
      </template>
      <template #footer>
        <AppButton variant="ghost" :disabled="verifying" @click="closeDetail">关闭</AppButton>
        <AppButton v-if="canManage && detail" variant="primary" :loading="verifying" @click="verifyDetail">重新校验完整性</AppButton>
      </template>
    </AppDrawer>
  </section>
</template>

<script>
import { AppConfirmDialog, AppInlineAlert, AppTermEntityPicker, AppCollegePicker, AppMajorPicker } from '@/components/common'
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable, EmptyState, ErrorState, LoadingState, StatusTag } from '@/components/business'
import { matchPermission } from '@/config/navPlan.js'
import { getPermissionPatterns } from '@/security/permissionGate.js'
import { academicStatsSnapshotApi } from '@/modules/academicAffairs/api/academic-stats-snapshot.api.js'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants.js'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { academicIdentity } from '../academicFlowContext'

export default {
  name: 'AaStatsSnapshotWorkspace',
  components: {
    AppConfirmDialog, AppInlineAlert, AppTermEntityPicker, AppCollegePicker, AppMajorPicker,
    AppButton, AppDrawer, DataTable, EmptyState, ErrorState, LoadingState, StatusTag
  },
  props: {
    ctx: { type: Object, default: () => ({}) },
    contextFilters: { type: Object, default: () => ({}) }
  },
  data() {
    return {
      disposed: false, listRequestId: 0, detailRequestId: 0, commandRequestId: 0,
      selectedSnapshotId: '', confirmedCreate: null,
      loading: false,
      loadedOnce: false,
      error: '',
      rows: [],
      listFilters: { termId: '', snapshotType: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      createVisible: false,
      confirmVisible: false,
      saving: false,
      createError: '',
      createForm: { snapshotType: 'OVERVIEW', termId: '', collegeId: '', majorId: '', reason: '' },
      detailVisible: false,
      detailLoading: false,
      detailError: '',
      detail: null,
      verifying: false,
      verified: {},
      columns: [
        { key: 'snapshotId', title: '快照 ID' },
        { key: 'type', title: '类型' },
        { key: 'scope', title: '范围' },
        { key: 'generated', title: '冻结时间' },
        { key: 'operator', title: '操作人' },
        { key: 'hash', title: 'payloadHash' },
        { key: 'status', title: '状态' },
        { key: 'integrity', title: '完整性' },
        { key: 'actions', title: '操作' }
      ]
    }
  },
  computed: {
    contextSignature() { return JSON.stringify([this.ctx.ctxKey, this.ctx.permissionPatterns, this.ctx.dataScope, this.ctx.permissionVersion, this.ctx.dataScopeVersion]) },
    confirmationMessage() {
      const body = this.confirmedCreate?.body
      return body ? `${this.scopeLabel(body)} · ${this.filterLabel(body)}。冻结原因：${body.reason}。确认后保存当前统计，后续源数据变化不会回写。` : '请先选择并确认冻结范围。'
    },
    permissionPatterns() { return getPermissionPatterns() || [] },
    canView() { return matchPermission(this.permissionPatterns, 'academicAffairs.stats.snapshot.view') },
    canCreate() { return matchPermission(this.permissionPatterns, 'academicAffairs.stats.snapshot.create') },
    canManage() { return matchPermission(this.permissionPatterns, 'academicAffairs.stats.snapshot.manage') },
    prettyPayload() { return JSON.stringify(this.detail?.payload || {}, null, 2) }
  },
  created() {
    this.listFilters.termId = this.contextFilters?.termId || ''
    if (this.canView) this.load()
  },
  beforeUnmount() { this.disposed = true; this.invalidate() },
  watch: {
    contextSignature() {
      this.invalidate(); this.rows = []; this.detail = null; this.verified = {}; this.selectedSnapshotId = ''
      this.detailVisible = false; this.createVisible = false; this.confirmVisible = false; this.confirmedCreate = null
      this.createError = ''; this.error = ''; this.pagination.total = 0
      if (this.canView) this.load()
    }
  },
  methods: {
    academicStatusLabel,
    identity() { return academicIdentity(currentUserFromToken(), this.ctx) },
    current(id, identity, key) { return !this.disposed && id === this[key] && identity === this.identity() },
    invalidate() { this.listRequestId++; this.detailRequestId++; this.commandRequestId++; this.loading = false; this.detailLoading = false; this.saving = false; this.verifying = false },
    snapshotTypeLabel(value) { return String(value || '').toUpperCase() === 'OVERVIEW' ? '教务总览' : (value || '—') },
    formatTime(value) {
      if (!value) return '—'
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false })
    },
    shortHash(value) {
      const text = String(value || '')
      return text ? `${text.slice(0, 10)}…${text.slice(-8)}` : '—'
    },
    scopeLabel(row) {
      if (row.collegeId) return `学院 #${row.collegeId}`
      return '全校 / 当前服务端授权范围'
    },
    filterLabel(row) {
      const parts = []
      if (row.termId) parts.push(`学期 #${row.termId}`)
      if (row.majorId) parts.push(`专业 #${row.majorId}`)
      return parts.length ? parts.join(' · ') : '无额外筛选'
    },
    async load() {
      if (!this.canView) return
      const id = ++this.listRequestId, identity = this.identity()
      this.loading = true
      this.error = ''
      this.rows = []; this.pagination.total = 0
      try {
        const res = await academicStatsSnapshotApi.list({
          termId: this.listFilters.termId || undefined,
          snapshotType: this.listFilters.snapshotType || undefined,
          page: this.pagination.page,
          pageSize: this.pagination.pageSize
        })
        if (!this.current(id, identity, 'listRequestId')) return
        if (!Array.isArray(res?.list) || !Number.isSafeInteger(res.total) || res.total < 0) throw new Error('统计快照列表回执不完整，请重新读取')
        this.rows = res.list
        this.pagination.total = res.total
      } catch (error) {
        if (!this.current(id, identity, 'listRequestId')) return
        this.rows = []
        this.pagination.total = 0
        this.error = error?.message || '统计快照加载失败'
      } finally {
        if (this.current(id, identity, 'listRequestId')) { this.loading = false; this.loadedOnce = true }
      }
    },
    search() { this.pagination.page = 1; this.load() },
    resetSearch() {
      this.listFilters = { termId: '', snapshotType: '' }
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) { this.pagination.page = Number(page || 1); this.load() },
    openCreate() {
      if (!this.canCreate || this.saving) return
      this.confirmedCreate = null
      this.createForm = {
        snapshotType: 'OVERVIEW',
        termId: this.contextFilters?.termId || this.listFilters.termId || '',
        collegeId: this.contextFilters?.collegeId || '',
        majorId: this.contextFilters?.majorId || '',
        reason: ''
      }
      this.createError = ''
      this.createVisible = true
    },
    closeCreate() {
      if (this.saving) return
      this.createVisible = false
      this.confirmVisible = false
      this.confirmedCreate = null
      this.createError = ''
    },
    confirmCreate() {
      if (!this.canCreate || this.saving) return
      if (this.createForm.reason.trim().length < 5) {
        this.createError = '冻结原因至少 5 个字'
        return
      }
      this.confirmedCreate = { identity: this.identity(), body: { ...this.createForm, reason: this.createForm.reason.trim() } }
      this.confirmVisible = true
    },
    async submitCreate() {
      const confirmed = this.confirmedCreate
      if (this.saving || !this.confirmVisible || !confirmed) return
      if (!this.canCreate || confirmed.identity !== this.identity()) { this.confirmVisible = false; this.confirmedCreate = null; this.createError = '身份或权限已变化，请重新确认冻结范围'; return }
      const id = ++this.commandRequestId, identity = this.identity(), body = { ...confirmed.body }
      this.saving = true
      this.createError = ''
      try {
        const snapshot = await academicStatsSnapshotApi.create(body)
        if (!this.current(id, identity, 'commandRequestId')) return
        if (!snapshot?.snapshotId) throw new Error('冻结结果尚未确认，请先查询快照列表，避免重复冻结')
        this.confirmVisible = false
        this.createVisible = false
        this.confirmedCreate = null
        toast.success('统计快照已冻结')
        this.listFilters.termId = body.termId || ''
        this.pagination.page = 1
        await this.load()
        if (!this.current(id, identity, 'commandRequestId')) return
        if (snapshot?.snapshotId) await this.openDetail(snapshot)
      } catch (error) {
        if (!this.current(id, identity, 'commandRequestId')) return
        this.confirmVisible = false
        this.confirmedCreate = null
        this.createError = `${error?.message || '未收到冻结回执'}；重试前请先查询快照列表核对是否已生成。`
      } finally {
        if (this.current(id, identity, 'commandRequestId')) this.saving = false
      }
    },
    async openDetail(row) {
      if (!this.canView || !row?.snapshotId) return
      const snapshotId = String(row.snapshotId), id = ++this.detailRequestId, identity = this.identity()
      this.selectedSnapshotId = snapshotId
      this.verifying = false
      this.detailVisible = true
      this.detailLoading = true
      this.detailError = ''
      this.detail = null
      try {
        const res = await academicStatsSnapshotApi.detail(snapshotId)
        if (!this.current(id, identity, 'detailRequestId')) return
        if (String(res?.snapshotId) !== snapshotId) throw new Error('返回快照与所选对象不一致，请重新读取')
        this.detail = res
        // The detail endpoint verifies the persisted hash before returning this exact object.
        this.verified = { ...this.verified, [snapshotId]: true }
      } catch (error) {
        if (!this.current(id, identity, 'detailRequestId')) return
        this.verified = { ...this.verified, [snapshotId]: false }
        this.detailError = error?.message || '统计快照详情读取失败'
      } finally {
        if (this.current(id, identity, 'detailRequestId')) this.detailLoading = false
      }
    },
    reloadDetail() {
      const id = this.selectedSnapshotId
      if (id) this.openDetail({ snapshotId: id })
    },
    closeDetail() {
      this.detailRequestId++; this.detailLoading = false; this.verifying = false
      this.detailVisible = false
      this.detail = null
      this.detailError = ''
    },
    async verifyDetail() {
      if (!this.canManage || !this.detail || this.verifying) return
      const snapshotId = String(this.detail.snapshotId), id = ++this.detailRequestId, identity = this.identity()
      this.verifying = true
      try {
        const res = await academicStatsSnapshotApi.verify(snapshotId)
        if (!this.current(id, identity, 'detailRequestId')) return
        if (res?.integrityValid !== true || res?.immutable !== true) throw new Error('后端未返回有效的不可变完整性结论')
        this.verified = { ...this.verified, [snapshotId]: true }
        toast.success('统计快照完整性校验通过')
      } catch (error) {
        if (!this.current(id, identity, 'detailRequestId')) return
        this.verified = { ...this.verified, [snapshotId]: false }
        this.detailError = error?.message || '完整性校验失败'
      } finally {
        if (this.current(id, identity, 'detailRequestId')) this.verifying = false
      }
    }
  }
}
</script>

<style scoped>
.assw { min-width: 0; }
.assw-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; margin-bottom: 12px; }
.assw-title { font-size: 18px; font-weight: 700; color: var(--t1); }
.assw-head p { margin: 5px 0 0; color: var(--t3); font-size: 13px; line-height: 1.6; }
.assw-filter { display: grid; grid-template-columns: minmax(220px, 1fr) 180px auto; gap: 10px; align-items: end; margin: 14px 0; }
.assw-filter label, .assw-form label { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.assw-filter label > span, .assw-form label > span { color: var(--t3); font-size: 12px; }
.assw-filter select, .assw-form select, .assw-form textarea { width: 100%; box-sizing: border-box; border: 1px solid var(--card-b); border-radius: 9px; background: var(--bg-card); color: var(--t1); padding: 8px 10px; font: inherit; }
.assw-filter select, .assw-form select { min-height: 36px; }
.assw-filter__actions { display: flex; gap: 6px; }
.assw-form { display: grid; gap: 14px; }
.assw-detail-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.assw-kv { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.assw-kv > div { background: var(--bg-section); border-radius: 10px; padding: 12px; min-width: 0; }
.assw-kv span { display: block; color: var(--t3); font-size: 12px; margin-bottom: 5px; }
.assw-kv strong { overflow-wrap: anywhere; }
.assw-section { margin-top: 16px; }
.assw-section__title { font-weight: 650; margin-bottom: 8px; }
.assw-code, .assw-hash, .assw-mono { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
.assw-code { display: block; padding: 10px; background: var(--bg-section); border-radius: 8px; overflow-wrap: anywhere; }
.assw-json { max-height: 380px; overflow: auto; margin: 0; padding: 12px; border-radius: 9px; background: var(--bg-section); font-size: 12px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 900px) {
  .assw-filter { grid-template-columns: 1fr 1fr; }
  .assw-filter__actions { grid-column: 1 / -1; }
}
@media (max-width: 600px) {
  .assw-head { flex-direction: column; }
  .assw-filter, .assw-kv { grid-template-columns: 1fr; }
}
</style>
