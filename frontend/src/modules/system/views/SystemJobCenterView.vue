<template>
  <ModulePageShell
    title="批处理与后台任务"
    subtitle="查看各业务模块的后台任务进度、失败原因与授权依据"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'refresh', label: '刷新' }]" @action="load" />
    </template>

    <div class="mp-stack">
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">首屏结论</span></header>
          <div class="mp-card__body jc-summary">
            <div class="jc-stat"><span class="jc-stat__num">{{ overview.running || 0 }}</span><span class="jc-stat__label">运行中</span></div>
            <div class="jc-stat" :class="{ 'jc-stat--warn': overview.failed }"><span class="jc-stat__num">{{ overview.failed || 0 }}</span><span class="jc-stat__label">失败</span></div>
            <div class="jc-stat"><span class="jc-stat__num">{{ overview.backlog || 0 }}</span><span class="jc-stat__label">积压</span></div>
          </div>
          <div class="mp-card__body jc-per-kind">
            <span v-for="k in overview.perKind || []" :key="k.kind" class="jc-kind-chip">
              {{ kindLabel(k.kind) }}：共{{ k.total }} · 运行{{ k.running }} · 失败{{ k.failed }} · 积压{{ k.backlog }}
            </span>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">任务列表</span>
            <span class="mp-note">统一查看各业务模块任务；可执行的操作以当前任务状态为准</span>
          </header>
          <div class="mp-card__body jc-filters">
            <select v-model="filterKind" class="jc-input" @change="search">
              <option value="">全部类型</option>
              <option v-for="k in jobTypes" :key="k.kind" :value="k.kind">{{ kindLabel(k.kind) }}</option>
            </select>
            <select v-model="filterStatus" class="jc-input" @change="search">
              <option value="">全部状态</option>
              <option v-for="option in statusOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
            <button class="mp-link" @click="search">查询</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!jobs.length" title="当前筛选没有任务" description="可调整任务类型或状态重新查询" />
            <DataTable v-else :columns="jobColumns" :rows="jobs" row-key="jobId" :pagination="pagination" @page-change="changePage">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ kindLabel(row.kind) }} · 任务编号 {{ taskNumber(row) }}</div>
                <div class="mp-cell-sub">来源：{{ moduleLabel(row.ownerModule) }} · 发起：{{ row.initiator ? '业务经办人' : '未记录发起人' }} · {{ formatTime(row) }}</div>
              </template>
              <template #cell-status="{ row }">
                <StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="viewEvidence(row)">授权证据</button>
                <button v-if="row.availableActions?.retry?.allowed" class="mp-link" :disabled="busy" @click="prepareAction('retry', row)">重试</button>
                <button v-if="row.availableActions?.cancel?.allowed" class="mp-link" :disabled="busy" @click="prepareAction('cancel', row)">取消</button>
                <span v-if="!row.availableActions?.retry?.allowed && !row.availableActions?.cancel?.allowed" class="mp-note">当前仅可查看</span>
              </template>
            </DataTable>
          </div>
        </section>

        <section v-if="evidence" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">当前操作授权核对</span></header>
          <div class="mp-card__body jc-evidence">
            <p>以下核对当前身份现在能否办理，不替代任务创建时的历史审计。</p>
            <p>执行身份：<strong>{{ authorizationActorLabel(evidence) }}</strong></p>
            <p>授权方式：<strong>{{ authorizationPolicyLabel(evidence.currentActorAuthorization?.policyType) }}</strong></p>
            <p>作用范围：<strong>{{ scopeSummary(evidence.scopeSnapshot) }}</strong></p>
            <p>有效期：<strong>{{ evidence.currentActorAuthorization?.delegationExpiresAt || '未记录固定到期时间，执行时重新鉴权' }}</strong>
              <span v-if="evidence.currentActorAuthorization?.delegatedSubject">
                （临时授权）
              </span>
            </p>
          </div>
        </section>
      </template>
    </div>
    <WorkspaceConfirmDialog :visible="!!pending" :title="pending?.type === 'retry' ? '核对任务重试' : '核对任务取消'"
      :confirm-text="pending?.type === 'retry' ? '确认重试任务' : '确认取消任务'" require-reason reason-label="操作原因"
      :submitting="busy" :confirm-disabled="actionNeedsReview" @update:visible="closeAction" @confirm="performAction">
      <p v-if="pending">{{ kindLabel(pending.row.kind) }} · 任务编号 {{ taskNumber(pending.row) }} · 当前状态：{{ statusLabel(pending.row.status) }} · 版本 {{ pending.row.version }}</p>
      <p>只办理当前选中的任务；执行前再次检查权限、状态和版本。</p>
      <p v-if="actionError" role="alert">{{ actionError }}</p>
    </WorkspaceConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'
import { safeEnumLabel } from '@/utils/presentationSafety'
import { formatDateTime } from '@/utils/dateUtils'
import WorkspaceConfirmDialog from '@/modules/system/components/workspace/WorkspaceConfirmDialog.vue'
import { contextFingerprint } from '@/modules/system/utils/workspaceContract'

const KIND_LABEL = { IMPORT: '业务数据导入', EXPORT: '业务数据导出', FILE_JOB: '文件安全处理', EXCEL_IMPORT: '表格数据导入', AFFAIRS_BATCH: '学工批量处理' }
const MODULE_LABEL = { dataExchange: '数据交换中心', fileStorage: '文件中心', studentAffairs: '学工中心', systemAdmin: '系统管理', academicAffairs: '教务中心', graduationDesign: '毕业设计中心', internship: '岗位实习中心' }
const STATUS_LABEL = {
  CREATED: '待开始', PENDING: '等待处理', UPLOADED: '文件已上传', VALIDATED: '校验完成',
  RUNNING: '运行中', PROCESSING: '处理中', VALIDATING: '校验中', CONFIRMING: '确认中',
  SUCCEEDED: '已完成', SUCCESS: '已完成', IMPORTED: '已导入', CONFIRMED: '已确认',
  FAILED: '失败', DEAD: '处理终止', TIMEOUT: '处理超时', CANCELLED: '已取消',
  SCANNING: '安全扫描中', PARSING: '预检查中', VALIDATION_FAILED: '预检未通过', EXPIRED: '已过期', REVOKED: '已撤销'
}
const POLICY_LABEL = { USER_DELEGATED: '临时职责授权', SERVICE_POLICY: '后台服务授权', TENANT_SYSTEM_TASK: '本校岗位授权' }

export default {
  name: 'SystemJobCenterView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag, WorkspaceConfirmDialog,
    LoadingState, ErrorState, EmptyState
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      busy: false,
      pending: null, actionError: '', actionNeedsReview: false, loadVersion: 0, disposed: false,
      error: '',
      overview: {},
      jobTypes: [],
      jobs: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      filterKind: '',
      filterStatus: '',
      evidence: null,
      statusOptions: Object.entries(STATUS_LABEL).map(([value, label]) => ({ value, label })),
      jobColumns: [
        { key: 'scope', title: '任务' },
        { key: 'status', title: '状态' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  created() { this.load() },
  beforeUnmount() { this.disposed = true; this.loadVersion += 1 },
  methods: {
    search() { this.pagination.page = 1; this.load() },
    changePage(page) { this.pagination.page = page; this.load() },
    taskNumber(row) { return String(row.jobId || '').split(':')[1] || '未记录' },
    formatTime(row) { return formatDateTime(row.createdAt, '未记录时间', row.timeZone) },
    kindLabel(value) { return safeEnumLabel({ value, dictionary: KIND_LABEL, unknownLabel: '其他业务任务' }) },
    moduleLabel(value) { return safeEnumLabel({ value, dictionary: MODULE_LABEL, unknownLabel: '来源待核对' }) },
    statusLabel(value) { return safeEnumLabel({ value, dictionary: STATUS_LABEL, unknownLabel: '状态待确认' }) },
    authorizationPolicyLabel(value) { return safeEnumLabel({ value, dictionary: POLICY_LABEL, unknownLabel: value ? '授权方式待确认' : '当前无可用授权' }) },
    authorizationActorLabel(evidence) { return evidence?.currentActorAuthorization?.policyType === 'SERVICE_POLICY' ? '后台服务身份' : '当前经办人' },
    scopeSummary(scope) {
      if (!scope || typeof scope !== 'object') return '未记录任务范围'
      const label = scope.scopeName || scope.orgName || scope.collegeName || scope.className
      return label || (Array.isArray(scope.actionPrefixAllowlist) ? `创建时保存的 ${scope.actionPrefixAllowlist.length} 个动作范围` : '未记录可解释的范围摘要')
    },
    statusTone(s) {
      if (['FAILED', 'DEAD', 'TIMEOUT'].includes(s)) return 'danger'
      if (['RUNNING', 'PROCESSING', 'VALIDATING', 'CONFIRMING'].includes(s)) return 'warning'
      if (['SUCCEEDED', 'SUCCESS', 'IMPORTED', 'CONFIRMED'].includes(s)) return 'success'
      return 'default'
    },
    async viewEvidence(row) {
      const res = await systemApi.getJobAuthorizationEvidence(row.jobId)
      if (res.code === 0) this.evidence = res.data
      else toast.error(res.message)
    },
    prepareAction(type, row) {
      if (this.busy || !['retry', 'cancel'].includes(type) || row.availableActions?.[type]?.allowed !== true) return
      this.pending = { type, row: { ...row }, context: contextFingerprint(this.ctx) }
      this.actionError = ''; this.actionNeedsReview = false
    },
    closeAction() { if (!this.busy) this.pending = null },
    async performAction({ reason }) {
      if (this.busy || !this.pending || this.actionNeedsReview) return
      const command = this.pending
      if (command.context !== contextFingerprint(this.ctx)) {
        this.actionError = '身份已变化，请返回任务列表重新核对'; this.actionNeedsReview = true; return
      }
      if (!Number.isInteger(command.row.version) || typeof reason !== 'string' || reason.trim().length < 5) {
        this.actionError = '请核对任务版本并填写至少5个字的具体原因'; return
      }
      this.busy = true
      try {
        const method = command.type === 'retry' ? 'retryJob' : 'cancelJob'
        const res = await systemApi[method](command.row.jobId, { reason: reason.trim(), expectedVersion: command.row.version })
        if (this.disposed || command.context !== contextFingerprint(this.ctx)) return
        if (res.code === 0) { this.pending = null; toast.success(command.type === 'retry' ? '已重新排队' : '已取消') }
        else { this.actionError = `${res.message}。请关闭核对框并根据重新读取的任务状态重新选择。`; this.actionNeedsReview = true }
        await this.load()
      } finally { this.busy = false }
    },
    async load() {
      const version = ++this.loadVersion
      this.loading = true
      this.error = ''
      const [overview, jobTypes, jobs] = await Promise.all([
        systemApi.getJobOverview(),
        systemApi.getJobTypes(),
        systemApi.listJobs({ kind: this.filterKind, status: this.filterStatus, page: this.pagination.page, pageSize: this.pagination.pageSize })
      ])
      if (version !== this.loadVersion || this.disposed) return
      if (jobs.code === 0 && jobs.data.total > 0 && !jobs.data.items.length && this.pagination.page > 1) {
        this.pagination.page = 1; await this.load(); return
      }
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (jobTypes.code === 0) this.jobTypes = jobTypes.data.kinds || []
      if (jobs.code === 0) { this.jobs = jobs.data.items || []; this.pagination.total = jobs.data.total }
      else if (!this.error) this.error = jobs.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.jc-summary { display: flex; flex-wrap: wrap; gap: var(--space-4); }
.jc-stat {
  min-width: 130px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
}
.jc-stat--warn { border-color: var(--color-danger); }
.jc-stat__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.jc-stat__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.jc-per-kind { display: flex; flex-wrap: wrap; gap: var(--space-2); color: var(--text-secondary); font-size: var(--font-size-sm); }
.jc-kind-chip { padding: 2px 8px; border: 1px solid var(--border-light); border-radius: var(--radius-sm); }
.jc-filters { display: flex; gap: var(--space-2); align-items: center; }
.jc-input { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 160px; }
.jc-evidence p { margin: 4px 0; font-size: var(--font-size-sm); }
</style>
