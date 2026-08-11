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
            <select v-model="filterKind" class="jc-input" @change="load">
              <option value="">全部类型</option>
              <option v-for="k in jobTypes" :key="k.kind" :value="k.kind">{{ kindLabel(k.kind) }}</option>
            </select>
            <select v-model="filterStatus" class="jc-input" @change="load">
              <option value="">全部状态</option>
              <option v-for="option in statusOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
            <button class="mp-link" @click="load">查询</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!jobs.length" title="暂无任务" description="" />
            <DataTable v-else :columns="jobColumns" :rows="jobs" row-key="jobId">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ kindLabel(row.kind) }}</div>
                <div class="mp-cell-sub">来源：{{ moduleLabel(row.ownerModule) }} · 发起：{{ row.initiator ? '业务经办人' : '系统任务' }} · {{ row.createdAt || '时间待同步' }}</div>
              </template>
              <template #cell-status="{ row }">
                <StatusTag :type="statusTone(row.status)" :label="statusLabel(row.status)" dot />
              </template>
              <template #cell-ops="{ row }">
                <button class="mp-link" @click="viewEvidence(row)">授权证据</button>
                <button class="mp-link" @click="retry(row)">重试</button>
                <button class="mp-link" @click="cancel(row)">取消</button>
              </template>
            </DataTable>
          </div>
        </section>

        <section v-if="evidence" class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">授权依据摘要</span></header>
          <div class="mp-card__body jc-evidence">
            <p>执行身份：<strong>{{ authorizationActorLabel(evidence) }}</strong></p>
            <p>授权方式：<strong>{{ authorizationPolicyLabel(evidence.currentActorAuthorization?.policyType) }}</strong></p>
            <p>作用范围：<strong>{{ scopeSummary(evidence.scopeSnapshot) }}</strong></p>
            <p>有效期：<strong>{{ evidence.currentActorAuthorization?.delegationExpiresAt || '仅限本次任务' }}</strong>
              <span v-if="evidence.currentActorAuthorization?.delegatedSubject">
                （临时授权）
              </span>
            </p>
          </div>
        </section>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'
import { safeEnumLabel } from '@/utils/presentationSafety'

const KIND_LABEL = { IMPORT: '业务数据导入', EXPORT: '业务数据导出', FILE_JOB: '文件安全处理', EXCEL_IMPORT: '表格数据导入', AFFAIRS_BATCH: '学工批量处理' }
const MODULE_LABEL = { dataExchange: '数据交换中心', fileStorage: '文件中心', studentAffairs: '学工中心' }
const STATUS_LABEL = {
  CREATED: '待开始', PENDING: '等待处理', UPLOADED: '文件已上传', VALIDATED: '校验完成',
  RUNNING: '运行中', PROCESSING: '处理中', VALIDATING: '校验中', CONFIRMING: '确认中',
  SUCCEEDED: '已完成', SUCCESS: '已完成', IMPORTED: '已导入', CONFIRMED: '已确认',
  FAILED: '失败', DEAD: '处理终止', TIMEOUT: '处理超时', CANCELLED: '已取消'
}
const POLICY_LABEL = { USER_DELEGATED: '本人职责授权', SERVICE_POLICY: '系统服务授权', TENANT_SYSTEM_TASK: '学校系统任务授权' }

export default {
  name: 'SystemJobCenterView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      jobTypes: [],
      jobs: [],
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
  methods: {
    kindLabel(value) { return safeEnumLabel({ value, dictionary: KIND_LABEL, unknownLabel: '其他业务任务' }) },
    moduleLabel(value) { return safeEnumLabel({ value, dictionary: MODULE_LABEL, unknownLabel: '相关业务中心' }) },
    statusLabel(value) { return safeEnumLabel({ value, dictionary: STATUS_LABEL, unknownLabel: '状态待确认' }) },
    authorizationPolicyLabel(value) { return safeEnumLabel({ value, dictionary: POLICY_LABEL, unknownLabel: value ? '授权方式待确认' : '当前无可用授权' }) },
    authorizationActorLabel(evidence) { return evidence?.currentActorAuthorization?.policyType === 'TENANT_SYSTEM_TASK' ? '学校系统任务' : '当前用户' },
    scopeSummary(scope) {
      if (!scope || typeof scope !== 'object') return '当前学校可管理范围'
      const label = scope.scopeName || scope.orgName || scope.collegeName || scope.className
      return label || '当前账号可管理范围'
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
    async retry(row) {
      const res = await systemApi.retryJob(row.jobId)
      if (res.code === 0) { toast.success('已重新排队'); await this.load() }
      else toast.error(res.message)
    },
    async cancel(row) {
      const res = await systemApi.cancelJob(row.jobId, { reason: '管理员在批处理面板取消' })
      if (res.code === 0) { toast.success('已取消'); await this.load() }
      else toast.error(res.message)
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, jobTypes, jobs] = await Promise.all([
        systemApi.getJobOverview(),
        systemApi.getJobTypes(),
        systemApi.listJobs({ kind: this.filterKind, status: this.filterStatus, pageSize: 20 })
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (jobTypes.code === 0) this.jobTypes = jobTypes.data.kinds || []
      if (jobs.code === 0) this.jobs = jobs.data.items || []
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
