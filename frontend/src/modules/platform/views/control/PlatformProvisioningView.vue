<template>
  <ModulePageShell title="租户自动开通、初始化与上线验收" subtitle="运行中 · 失败 · 待补偿 · 待学校输入 · 成功率"
                   role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <ModuleToolbar :actions="[{ key: 'create', label: '＋ 新建开通任务' }, { key: 'refresh', label: '刷新' }]"
                    @action="onToolbarAction" />
    </template>

    <LoadingState v-if="loading" text="正在加载开通任务…" />
    <ErrorState v-else-if="error" :text="error" @retry="load" />
    <template v-else>
      <div class="pcp__grid">
        <AppCard class="pcp__stat"><div class="pcp__stat-num">{{ overview.running }}</div><div class="pcp__stat-label">运行中</div></AppCard>
        <AppCard class="pcp__stat" :class="{ 'pcp__stat--warn': overview.failed }"><div class="pcp__stat-num">{{ overview.failed }}</div><div class="pcp__stat-label">失败</div></AppCard>
        <AppCard class="pcp__stat" :class="{ 'pcp__stat--warn': overview.manualReviewCount }"><div class="pcp__stat-num">{{ overview.manualReviewCount }}</div><div class="pcp__stat-label">待人工介入</div></AppCard>
        <AppCard class="pcp__stat"><div class="pcp__stat-num">{{ overview.waitingInput }}</div><div class="pcp__stat-label">待学校输入</div></AppCard>
        <AppCard class="pcp__stat"><div class="pcp__stat-num">{{ overview.successRate != null ? overview.successRate + '%' : '—' }}</div><div class="pcp__stat-label">成功率</div></AppCard>
      </div>

      <AppCard v-if="showCreate" class="psc__panel">
        <AppSectionHeader title="新建开通任务" />
        <div class="pcp__form">
          <input v-model.trim="form.idempotencyKey" class="pcp__input" placeholder="幂等键（同一次开通请求保持不变）" />
          <input v-model.trim="form.tenantCode" class="pcp__input" placeholder="租户代码 tenantCode" />
          <input v-model.trim="form.tenantName" class="pcp__input" placeholder="学校名称" />
          <select v-model="form.packageCode" class="pcp__input">
            <option value="trial">试用版</option><option value="basic">基础版</option>
            <option value="standard">标准版</option><option value="professional">专业版</option>
          </select>
          <input v-model.trim="form.adminLoginName" class="pcp__input" placeholder="首位管理员账号" />
          <input v-model.trim="form.adminRealName" class="pcp__input" placeholder="首位管理员姓名" />
          <button class="mp-link" @click="submitCreate">提交开通</button>
        </div>
      </AppCard>

      <AppCard v-if="revealedPassword" class="psc__panel pcp__reveal">
        <AppSectionHeader title="首位管理员临时密码（仅显示一次，请立即转告学校）" />
        <p class="pcp__reveal-text">{{ revealedPassword }}</p>
      </AppCard>

      <AppCard class="psc__panel">
        <AppSectionHeader title="开通任务列表" />
        <DataTable :columns="jobColumns" :rows="jobs" row-key="jobId" row-clickable @row-click="selectJob">
          <template #cell-scope="{ row }">
            <div class="psc__cell-main">{{ row.tenantCode }}</div>
            <div class="psc__cell-sub">{{ row.jobId }} · 当前步骤 {{ row.currentStep || '—' }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
          </template>
        </DataTable>
      </AppCard>

      <AppCard v-if="selected" class="psc__panel">
        <AppSectionHeader :title="`任务详情：${selected.tenantCode}（${selected.jobId}）`" />
        <p v-if="selected.lastError" class="pcp__error">最近错误：{{ selected.lastError }}</p>
        <DataTable :columns="stepColumns" :rows="selected.steps" row-key="stepCode">
          <template #cell-status="{ row }">
            <StatusTag :type="stepStatusTone(row.status)" :label="row.status" dot />
          </template>
          <template #cell-ops="{ row }">
            <button v-if="row.status === 'FAILED'" class="mp-link" @click="retryStep(row)">重试</button>
            <button v-if="row.status === 'FAILED'" class="mp-link" @click="compensateStep(row)">补偿</button>
            <button v-if="row.status === 'FAILED' || row.status === 'COMPENSATED'" class="mp-link" @click="flagManual(row)">转人工</button>
          </template>
        </DataTable>
        <div class="pcp__form">
          <button v-if="selected.status !== 'SUCCEEDED' && selected.status !== 'CANCELLED'" class="mp-link" @click="resumeJob">续跑</button>
          <button v-if="selected.status !== 'SUCCEEDED' && selected.status !== 'CANCELLED'" class="mp-link" @click="cancelJob">取消任务</button>
        </div>
      </AppCard>
    </template>
  </ModulePageShell>
</template>

<script>
import { AppCard, AppSectionHeader } from '@/components/ui'
import { DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformProvisioningView',
  components: { AppCard, AppSectionHeader, DataTable, ErrorState, LoadingState, ModulePageShell, ModuleToolbar, StatusTag },
  data() {
    return {
      loading: true,
      error: '',
      overview: {},
      jobs: [],
      selected: null,
      showCreate: false,
      revealedPassword: '',
      form: { idempotencyKey: '', tenantCode: '', tenantName: '', packageCode: 'trial', adminLoginName: '', adminRealName: '' },
      jobColumns: [
        { key: 'scope', title: '任务' },
        { key: 'status', title: '状态' }
      ],
      stepColumns: [
        { key: 'stepCode', title: '步骤' },
        { key: 'status', title: '状态' },
        { key: 'attemptCount', title: '尝试次数' },
        { key: 'error', title: '错误' },
        { key: 'ops', title: '操作' }
      ]
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { RUNNING: 'warning', SUCCEEDED: 'success', FAILED: 'danger', COMPENSATING: 'warning', CANCELLED: 'default', PENDING: 'default', WAITING_INPUT: 'warning' }[s] || 'default'
    },
    stepStatusTone(s) {
      return { SUCCEEDED: 'success', FAILED: 'danger', RUNNING: 'warning', NEEDS_MANUAL_REVIEW: 'danger', COMPENSATED: 'default', PENDING: 'default' }[s] || 'default'
    },
    onToolbarAction(action) {
      if (action === 'create') this.showCreate = !this.showCreate
      if (action === 'refresh') this.load()
    },
    async submitCreate() {
      if (!this.form.idempotencyKey || !this.form.tenantCode || !this.form.tenantName) {
        return toast.error('幂等键、租户代码、学校名称必填')
      }
      const res = await platformControlApi.startProvisioningJob({ ...this.form })
      if (res.code === 0) {
        toast.success('开通任务已受理：' + res.data.status)
        this.revealedPassword = res.data.revealOnce?.FIRST_ADMIN?.initialPassword || ''
        this.showCreate = false
        await this.load()
        this.selected = res.data
      } else toast.error(res.message)
    },
    async selectJob(row) {
      const res = await platformControlApi.getProvisioningJob(row.jobId)
      if (res.code === 0) this.selected = res.data
      else toast.error(res.message)
    },
    async resumeJob() {
      const res = await platformControlApi.resumeProvisioningJob(this.selected.jobId)
      if (res.code === 0) { toast.success('已续跑：' + res.data.status); this.selected = res.data; await this.load() }
      else toast.error(res.message)
    },
    async retryStep(row) {
      const res = await platformControlApi.retryProvisioningStep(this.selected.jobId, row.stepCode)
      if (res.code === 0) { toast.success('已重试'); this.selected = res.data; await this.load() }
      else toast.error(res.message)
    },
    async compensateStep(row) {
      const reason = window.prompt('补偿原因（至少5字）')
      if (!reason) return
      const res = await platformControlApi.compensateProvisioningStep(this.selected.jobId, row.stepCode, reason)
      if (res.code === 0) { toast.success('补偿已执行'); this.selected = res.data; await this.load() }
      else toast.error(res.message)
    },
    async flagManual(row) {
      const reason = window.prompt('转人工原因（至少5字）')
      if (!reason) return
      const res = await platformControlApi.flagProvisioningManualReview(this.selected.jobId, row.stepCode, reason)
      if (res.code === 0) { toast.success('已转人工队列'); this.selected = res.data; await this.load() }
      else toast.error(res.message)
    },
    async cancelJob() {
      const reason = window.prompt('取消原因（至少5字）')
      if (!reason) return
      const res = await platformControlApi.cancelProvisioningJob(this.selected.jobId, reason)
      if (res.code === 0) { toast.success('已取消'); this.selected = res.data; await this.load() }
      else toast.error(res.message)
    },
    async load() {
      this.loading = true
      this.error = ''
      const [overview, jobs] = await Promise.all([
        platformControlApi.getProvisioningOverview(),
        platformControlApi.listProvisioningJobs()
      ])
      if (overview.code === 0) this.overview = overview.data || {}
      else this.error = overview.message
      if (jobs.code === 0) this.jobs = jobs.data.items || []
      else if (!this.error) this.error = jobs.message
      this.loading = false
    }
  }
}
</script>

<style scoped>
.pcp__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.pcp__stat { padding: var(--space-4); }
.pcp__stat--warn { border-color: var(--color-danger); }
.pcp__stat-num { font-size: 26px; font-weight: var(--font-weight-bold); color: var(--t1); }
.pcp__stat-label { margin-top: 2px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.pcp__form { display: flex; flex-wrap: wrap; gap: var(--space-2); align-items: center; margin-top: var(--space-3); }
.pcp__input { padding: 6px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); min-width: 160px; }
.pcp__error { color: var(--color-danger); font-size: var(--font-size-sm); }
.pcp__reveal { border-color: var(--color-warning, #d97706); }
.pcp__reveal-text { font-family: monospace; font-size: var(--font-size-lg); font-weight: var(--font-weight-bold); }
</style>
