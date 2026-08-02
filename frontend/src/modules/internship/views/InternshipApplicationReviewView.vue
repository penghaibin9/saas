<template>
  <ModulePageShell
    title="实习申请审核"
    subtitle="审核校内岗位志愿与自主实习申请；审核结果会落到实习去向并写入审计留痕"
    role-name="指导教师 / 管理员"
    :data-scope-name="scopeHint"
    :watermark="false"
  >
    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无申请数据'" />

    <nav class="iar-types" aria-label="申请类型">
      <button
        v-for="item in typeOptions"
        :key="item.value"
        type="button"
        class="iar-types__item"
        :class="{ 'is-active': applicationType === item.value }"
        @click="setType(item.value)"
      >{{ item.label }}</button>
    </nav>

    <div class="iar-filters">
      <AppSearchBox v-model="keyword" placeholder="按学生、企业或岗位搜索" @search="reload" />
      <AppQuickFilterChips v-model="status" :options="statusOptions" allow-clear @change="reload" />
    </div>

    <div v-if="error" class="iar-state iar-state--error">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
    <DataTable
      v-else
      :columns="columns"
      :rows="rows"
      row-key="id"
      :loading="loading"
      :pagination="pagination"
      @page-change="onPageChange"
    >
      <template #cell-applicationType="{ row }">
        <AppStatusTag :type="row.applicationType === 'SELF_ARRANGED' ? 'warning' : 'info'">{{ row.applicationTypeLabel }}</AppStatusTag>
      </template>
      <template #cell-applicant="{ row }">
        <div class="mp-cell-main">{{ row.studentName }}</div>
        <div class="mp-cell-sub">{{ row.studentNo }}<span v-if="row.advisorName"> · {{ row.advisorName }}</span></div>
      </template>
      <template #cell-destination="{ row }">
        <div class="mp-cell-main">{{ row.companyName || '—' }}</div>
        <div class="mp-cell-sub">{{ row.positionName || '—' }}</div>
      </template>
      <template #cell-status="{ row }"><AppStatusTag :type="statusTone(row.status)">{{ row.statusLabel }}</AppStatusTag></template>
      <template #cell-actions="{ row }">
        <AppButton variant="secondary" size="sm" @click="openDetail(row.id)">{{ row.status === 'PENDING_REVIEW' ? '审核' : '查看' }}</AppButton>
      </template>
    </DataTable>

    <AppDrawer v-model:visible="drawer.visible" :title="drawerTitle" mode="modal" size="large">
      <div v-if="drawer.loading" class="iar-state">加载中…</div>
      <div v-else-if="drawer.error" class="iar-state iar-state--error">{{ drawer.error }} <button type="button" class="mp-link" @click="loadDetail(drawer.id)">重试</button></div>
      <template v-else-if="drawer.data">
        <AppDescriptionList :items="detailItems" :columns="2" />

        <section v-if="drawer.data.applicationNote" class="iar-section">
          <h3>申请说明</h3>
          <p>{{ drawer.data.applicationNote }}</p>
        </section>
        <section v-if="drawer.data.evidenceFileId" class="iar-section">
          <h3>自主实习证明材料</h3>
          <AppFilePreview :files="evidenceFiles" @download="downloadEvidence" />
        </section>
        <section v-if="drawer.data.reviewedAt" class="iar-section">
          <h3>审核结果</h3>
          <AppDescriptionList :items="reviewItems" :columns="2" />
        </section>
        <section class="iar-section">
          <h3>操作留痕</h3>
          <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无操作记录" />
        </section>
      </template>

      <template #footer>
        <div v-if="drawer.data?.status === 'PENDING_REVIEW'" class="iar-drawer-actions">
          <AppPermissionButton code="internship.application.review" :allowed="canBtn('internship.application.review')" variant="ghost" :danger="true" @click="askReview('REJECT')">驳回</AppPermissionButton>
          <AppPermissionButton code="internship.application.review" :allowed="canBtn('internship.application.review')" variant="primary" @click="askReview('APPROVE')">通过并落实去向</AppPermissionButton>
        </div>
      </template>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.title"
      :content="confirm.content"
      :danger="confirm.danger"
      :confirm-text="confirm.confirmText"
      :require-reason="confirm.requireReason"
      :reason-chips="confirm.requireReason ? REJECT_APPLICATION : []"
      reason-label="审核意见"
      :submitting="confirm.submitting"
      @confirm="submitReview"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppDrawer, AppButton } from '@/components/ui'
import {
  AppStatusTag, AppSearchBox, AppQuickFilterChips, AppDescriptionList,
  AppFilePreview, AppAuditTrail, AppPermissionButton, AppConfirmDialog
} from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { downloadAttachment } from '@/modules/internship/api/guidance-visit.api'
import { internshipApplicationApi } from '@/modules/internship/api/internship-application.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { REJECT_APPLICATION } from '@/modules/internship/constants/presetPrompts'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const TYPE_OPTIONS = [
  { value: '', label: '全部申请' },
  { value: 'POSITION', label: '岗位志愿' },
  { value: 'SELF_ARRANGED', label: '自主实习' }
]
const STATUS_OPTIONS = [
  { value: 'ALL', label: '全部状态' },
  { value: 'PENDING_REVIEW', label: '待审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'WITHDRAWN', label: '已撤回' },
  { value: 'CANCELLED', label: '已取消' }
]
const COLUMNS = [
  { key: 'applicationType', title: '申请类型', width: '120px' },
  { key: 'applicant', title: '学生', width: '150px' },
  { key: 'destination', title: '申请去向' },
  { key: 'submittedAt', title: '提交时间', width: '160px' },
  { key: 'status', title: '状态', width: '110px' },
  { key: 'actions', title: '操作', width: '90px' }
]

export default {
  name: 'InternshipApplicationReviewView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: {
    ModulePageShell, DataTable, AppDrawer, AppButton, AppStatusTag, AppSearchBox,
    AppQuickFilterChips, AppDescriptionList, AppFilePreview, AppAuditTrail,
    AppPermissionButton, AppConfirmDialog, ModuleSummaryStrip
  },
  data() {
    return {
      REJECT_APPLICATION,
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      applicationType: '', status: 'PENDING_REVIEW', keyword: '',
      typeOptions: TYPE_OPTIONS, statusOptions: STATUS_OPTIONS, columns: COLUMNS,
      drawer: { visible: false, id: '', loading: false, error: '', data: null },
      confirm: { visible: false, title: '', content: '', danger: false, confirmText: '', requireReason: false, submitting: false, action: '' },
      scopeHint: '指导教师仅可审核本人指导学生；管理员按当前数据范围审核'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    drawerTitle() {
      const data = this.drawer.data
      return data ? `申请审核 · ${data.studentName}` : '申请审核'
    },
    summaryMetrics() {
      if (this.loading || this.error) return []
      const statusLabel = this.statusOptions.find((item) => item.value === this.status)?.label || '全部'
      return [{ label: `实习申请 · ${statusLabel}`, value: this.total, tone: this.status === 'PENDING_REVIEW' && this.total ? 'warn' : undefined }]
    },
    detailItems() {
      const data = this.drawer.data || {}
      return [
        { label: '学生', value: `${data.studentName || '—'}（${data.studentNo || '—'}）` },
        { label: '校内指导教师', value: data.advisorName || '—' },
        { label: '申请类型', value: data.applicationTypeLabel || '—' },
        { label: '志愿顺序', value: data.applicationType === 'POSITION' ? `第 ${data.volunteerNo} 志愿` : '自主实习' },
        { label: '实习单位', value: data.companyName || '—' },
        { label: '实习岗位', value: data.positionName || '—' },
        { label: '工作地点', value: data.workAddress || '—' },
        { label: '单位联系人', value: data.contactName ? `${data.contactName}${data.contactPhone ? ` · ${data.contactPhone}` : ''}` : '—' },
        { label: '提交时间', value: data.submittedAt || '未提交' },
        { label: '当前状态', value: data.statusLabel || '—' }
      ]
    },
    reviewItems() {
      const data = this.drawer.data || {}
      return [
        { label: '审核人', value: data.reviewedBy || '—' },
        { label: '审核时间', value: data.reviewedAt || '—' },
        { label: '审核意见', value: data.reviewComment || '—' }
      ]
    },
    evidenceFiles() {
      const data = this.drawer.data || {}
      return data.evidenceFileId ? [{ id: data.evidenceFileId, name: '自主实习证明材料', sensitive: true }] : []
    },
    auditRecords() {
      return (this.drawer.data?.auditTrail || []).map((item, index) => ({
        id: index, action: item.action, actor: item.operator,
        reason: item.detail?.comment || '', at: item.occurredAt
      }))
    }
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.load()
    },
    '$route.query.type': {
      immediate: true,
      handler(value) {
        const next = value === 'POSITION' || value === 'SELF_ARRANGED' ? value : ''
        if (next === this.applicationType) return
        this.applicationType = next
        this.page = 1
        this.load()
      }
    },
    '$route.query.status': {
      immediate: true,
      handler(value) {
        const next = STATUS_OPTIONS.some((item) => item.value === value) ? value : 'PENDING_REVIEW'
        if (next === this.status) return
        this.status = next
        this.page = 1
        this.load()
      }
    },
    '$route.query.id'(value) {
      if (value) this.openDetail(value)
    }
  },
  created() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    statusTone(value) {
      if (value === 'APPROVED') return 'success'
      if (value === 'REJECTED') return 'danger'
      if (value === 'PENDING_REVIEW') return 'warning'
      return 'default'
    },
    setType(value) {
      if (value === this.applicationType) return
      const query = { ...this.$route.query }
      if (value) query.type = value
      else delete query.type
      delete query.id
      this.$router.replace({ query })
    },
    reload() { this.page = 1; this.load() },
    onPageChange(page) { this.page = page; this.load() },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = '请先选择实习批次'
        this.rows = []
        this.total = 0
        return
      }
      this.loading = true
      this.error = ''
      const params = {
        page: this.page,
        pageSize: this.pageSize,
        keyword: this.keyword,
        batchId: this.batchStore.selectedBatchId
      }
      if (this.applicationType) params.applicationType = this.applicationType
      if (this.status && this.status !== 'ALL') params.status = this.status
      const result = await internshipApplicationApi.getApplications(params)
      this.loading = false
      if (result.code !== 0) {
        this.error = result.message || '加载失败'
        this.rows = []
        this.total = 0
        return
      }
      this.rows = result.data.list
      this.total = result.data.total
    },
    async openDetail(id) {
      const value = String(id)
      if (String(this.$route.query.id || '') !== value) {
        this.$router.replace({ query: { ...this.$route.query, id: value } })
      }
      this.drawer = { visible: true, id: value, loading: true, error: '', data: null }
      await this.loadDetail(value)
    },
    async loadDetail(id) {
      const value = String(id)
      this.drawer.loading = true
      this.drawer.error = ''
      const result = await internshipApplicationApi.getDetail(value)
      if (this.drawer.id !== value) return
      this.drawer.loading = false
      if (result.code !== 0) {
        this.drawer.error = result.message || '申请详情加载失败'
        return
      }
      this.drawer.data = result.data
    },
    async downloadEvidence(file) {
      try {
        await downloadAttachment(file.id, file.name)
      } catch (error) {
        toast.error(error?.message || '下载失败')
      }
    },
    askReview(action) {
      const data = this.drawer.data
      if (!data) return
      const approve = action === 'APPROVE'
      this.confirm = {
        visible: true,
        title: approve ? '通过实习申请' : '驳回实习申请',
        content: approve
          ? `确认通过「${data.studentName}」的申请？系统将立即落实其实习去向，并取消该学生其他进行中的申请。`
          : `确认驳回「${data.studentName}」的申请？请填写可执行的驳回原因。`,
        danger: !approve,
        confirmText: approve ? '通过并落实' : '确认驳回',
        requireReason: !approve,
        submitting: false,
        action
      }
    },
    async submitReview({ reason }) {
      const data = this.drawer.data
      if (!data) return
      this.confirm.submitting = true
      const result = await internshipApplicationApi.review(data.id, {
        action: this.confirm.action,
        comment: reason || '',
        expectedVersion: data.version,
        recordExpectedVersion: data.recordVersion
      })
      this.confirm.submitting = false
      if (result.code !== 0) return toast.error(result.message || '审核失败')
      this.confirm.visible = false
      toast.success(this.confirm.action === 'APPROVE' ? '申请已通过，实习去向已落实' : '申请已驳回')
      await this.load()
      await this.loadDetail(data.id)
    }
  }
}
</script>

<style scoped>
.iar-types { display: flex; gap: 6px; margin-bottom: var(--space-3); padding: 7px; border: 1px solid var(--card-b, #e5e7eb); border-radius: 12px; background: var(--card, #fff); }
.iar-types__item { border: 0; border-radius: 8px; background: transparent; color: var(--t2, #475569); padding: 7px 12px; cursor: pointer; font-size: 13px; }
.iar-types__item:hover { background: var(--pri-bg, #eff6ff); color: var(--pri, #2563eb); }
.iar-types__item.is-active { background: var(--pri, #2563eb); color: #fff; font-weight: 600; }
.iar-filters { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.iar-state { padding: var(--space-6); color: var(--text-tertiary); text-align: center; }
.iar-state--error { color: var(--danger-600, #dc2626); }
.iar-section { margin-top: var(--space-5); padding-top: var(--space-4); border-top: 1px solid var(--card-b, #e5e7eb); }
.iar-section h3 { margin: 0 0 var(--space-3); font-size: 14px; color: var(--text-primary); }
.iar-section p { margin: 0; white-space: pre-wrap; color: var(--text-secondary); font-size: 13px; line-height: 1.7; }
.iar-drawer-actions { display: flex; justify-content: flex-end; gap: var(--space-2); }
@media (max-width: 640px) { .iar-types { overflow-x: auto; } .iar-types__item { flex: 0 0 auto; } }
</style>
