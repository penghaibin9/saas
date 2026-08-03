<template>
  <ModulePageShell
    title="批处理与后台任务"
    subtitle="运行中 · 失败 · 积压 · 授权证据（USER_DELEGATED / SERVICE_POLICY / TENANT_SYSTEM_TASK）"
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
              {{ k.kind }}：共{{ k.total }} · 运行{{ k.running }} · 失败{{ k.failed }} · 积压{{ k.backlog }}
            </span>
          </div>
        </section>

        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">任务列表</span>
            <span class="mp-note">跨5张既有任务表只读聚合；重试/取消仅在注册表登记为安全的范围内开放</span>
          </header>
          <div class="mp-card__body jc-filters">
            <select v-model="filterKind" class="jc-input" @change="load">
              <option value="">全部类型</option>
              <option v-for="k in jobTypes" :key="k.kind" :value="k.kind">{{ k.kind }}</option>
            </select>
            <input v-model.trim="filterStatus" class="jc-input" placeholder="状态过滤，如 FAILED" @keyup.enter="load" />
            <button class="mp-link" @click="load">查询</button>
          </div>
          <div class="mp-card__body">
            <EmptyState v-if="!jobs.length" title="暂无任务" description="" />
            <DataTable v-else :columns="jobColumns" :rows="jobs" row-key="jobId">
              <template #cell-scope="{ row }">
                <div class="mp-cell-main">{{ row.jobId }}</div>
                <div class="mp-cell-sub">{{ row.kind }} · {{ row.ownerModule }} · initiator {{ row.initiator || '—' }}</div>
              </template>
              <template #cell-status="{ row }">
                <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
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
          <header class="mp-card__head"><span class="mp-card__title">授权证据：{{ evidence.jobId }}</span></header>
          <div class="mp-card__body jc-evidence">
            <p>scopeSnapshot：{{ evidence.scopeSnapshot ? JSON.stringify(evidence.scopeSnapshot) : '（该类型无范围快照字段）' }}</p>
            <p>revision：{{ evidence.revision || '—' }}</p>
            <p>idempotency：{{ evidence.idempotency || '—' }}</p>
            <p>若由当前登录用户操作该任务，将走：
              <strong>{{ evidence.currentActorAuthorization?.policyType || '无权限' }}</strong>
              <span v-if="evidence.currentActorAuthorization?.delegatedSubject">
                （临时授权 {{ evidence.currentActorAuthorization.delegatedSubject }}，到期 {{ evidence.currentActorAuthorization.delegationExpiresAt }}）
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
      jobColumns: [
        { key: 'scope', title: '任务' },
        { key: 'status', title: '状态' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  created() { this.load() },
  methods: {
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
