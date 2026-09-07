<template>
  <div class="top">
    <LoadingState v-if="loading" text="正在加载退租与销毁权威状态…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" @back="$emit('changed')" />

    <template v-else>
      <div v-if="uncertain" class="top__danger-box" role="alert">
        <b>上次操作结果尚未确认，请勿重复提交</b>
        <p>先重新读取当前学校与任务状态；读取成功不代表上次操作一定成功，也不会重放命令。</p>
        <AppButton :disabled="busy" @click="load">只读取当前状态</AppButton>
        <AppButton v-if="inspected" :disabled="busy" @click="uncertain = false; inspected = false">已核对，结束本次记录</AppButton>
      </div>
      <AppCard class="top__panel top__panel--summary">
        <div class="top__header">
          <div>
            <div class="top__eyebrow">租户退出服务</div>
            <h3>退租与数据销毁</h3>
            <p>从影响预演、冻结只读、最终导出、保留期到永久销毁。所有危险动作都以后端状态机和安全门禁为准。</p>
          </div>
          <StatusTag :type="jobStatusType" :label="jobStatusLabel" />
        </div>

        <div class="top__metrics">
          <div><span>学生</span><b>{{ preview?.counts?.studentCount ?? '—' }}</b></div>
          <div><span>账号</span><b>{{ preview?.counts?.userCount ?? '—' }}</b></div>
          <div><span>文件</span><b>{{ preview?.counts?.fileCount ?? '—' }}</b></div>
          <div><span>文件容量</span><b>{{ formatBytes(preview?.counts?.fileBytes) }}</b></div>
          <div><span>司法保全文件</span><b :class="{ 'top__danger': Number(preview?.counts?.legalHoldFileCount || 0) > 0 }">{{ preview?.counts?.legalHoldFileCount ?? '—' }}</b></div>
          <div><span>运行中文件任务</span><b :class="{ 'top__danger': Number(preview?.counts?.activeFileJobCount || 0) > 0 }">{{ preview?.counts?.activeFileJobCount ?? '—' }}</b></div>
        </div>

        <div class="top__registry" :class="preview?.registry?.complete ? 'is-ok' : 'is-bad'">
          <b>销毁登记表：{{ preview?.registry?.complete ? '完整' : '存在未分类表，禁止销毁' }}</b>
          <span>版本 {{ preview?.registry?.registryVersion || '—' }} · 可销毁表 {{ preview?.registry?.purgeTableCount ?? '—' }} · 保留证据表 {{ preview?.registry?.retainTableCount ?? '—' }}</span>
        </div>

        <ul v-if="preview?.blockers?.length" class="top__blockers">
          <li v-for="item in preview.blockers" :key="item.code">{{ item.message || '存在尚未处理的销毁阻断项' }}</li>
        </ul>
      </AppCard>

      <AppCard v-if="canStartNew" class="top__panel">
        <AppSectionHeader title="1 · 发起退租并冻结业务写入" />
        <p class="top__note">提交后租户会立即进入只读状态，普通交互式登录和业务写入将被拒绝。生产租户保留期至少 1 天。</p>
        <div class="top__form-grid">
          <label class="top__field top__field--wide">
            <span>退租原因（至少 10 个字符）</span>
            <textarea v-model.trim="requestForm.reason" class="top__textarea" rows="3" placeholder="例如：合同到期且学校确认终止服务，按协议进入数据交付与销毁流程" />
          </label>
          <label class="top__field">
            <span>数据保留期（天）</span>
            <input v-model.number="requestForm.retentionDays" class="top__input" type="number" min="0" max="3650" />
          </label>
        </div>
        <div class="top__ops">
          <AppButton variant="danger" :loading="working" :disabled="busy || uncertain || expectedTenantVersion === null || requestForm.reason.length < 10" @click="requestOffboarding">发起退租并冻结只读</AppButton>
          <span class="top__hint">当前状态版本：{{ expectedTenantVersion }}</span>
        </div>
      </AppCard>

      <template v-if="job && !canStartNew">
        <AppCard class="top__panel">
          <AppSectionHeader title="2 · 当前退租任务" />
          <div class="top__job-grid">
            <div><span>任务号</span><b>#{{ job.jobId }}</b></div>
            <div><span>状态</span><b>{{ stateLabel(job.state) }}</b></div>
            <div><span>租户状态版本</span><b>{{ job.tenantVersion ?? '—' }}</b></div>
            <div><span>保留期截止</span><b>{{ fmt(job.retentionUntil) || '—' }}</b></div>
            <div><span>最终导出</span><b>{{ job.finalExportSha256 ? '已确认' : '未确认' }}</b></div>
            <div><span>销毁证据</span><b>{{ job.purgeEvidenceSha256 ? '已生成' : '未生成' }}</b></div>
          </div>
          <div class="top__reason"><span>退租原因</span><b>{{ job.reason }}</b></div>

          <div class="top__steps">
            <div v-for="step in job.steps || []" :key="step.stepCode" class="top__step">
              <span class="top__step-dot" :class="`is-${String(step.status || '').toLowerCase()}`"></span>
              <div>
                <b>{{ stepLabel(step.stepCode) }}</b>
                <small>{{ platformStatusLabel(step.status) }} · 尝试 {{ step.attempts }} 次<span v-if="step.lastError"> · {{ step.lastError }}</span></small>
              </div>
            </div>
          </div>
        </AppCard>

        <AppCard v-if="['FROZEN_READONLY', 'FINAL_EXPORT_READY'].includes(job.state)" class="top__panel">
          <AppSectionHeader title="3 · 确认最终数据导出 SHA-256" />
          <p class="top__note">完成最终数据交付后，把导出物的 64 位 SHA-256 摘要填入。后端确认后租户进入保留期并进一步收紧登录。</p>
          <div class="top__inline">
            <input v-model.trim="finalExportSha" class="top__input top__input--hash" maxlength="64" placeholder="64 位 SHA-256" />
            <AppButton variant="primary" :loading="working" :disabled="busy || uncertain || !validSha" @click="confirmFinalExport">确认最终导出</AppButton>
          </div>
        </AppCard>

        <AppCard v-if="job.cancellable" class="top__panel">
          <AppSectionHeader title="取消退租" />
          <p class="top__note">仅在不可逆边界前允许取消，系统会恢复冻结前的租户状态。</p>
          <div class="top__inline">
            <input v-model.trim="cancelReason" class="top__input top__input--grow" placeholder="取消原因（至少 5 个字符）" />
            <AppButton variant="warning" :loading="working" :disabled="busy || uncertain || cancelReason.length < 5" @click="cancelOffboarding">取消退租</AppButton>
          </div>
        </AppCard>

        <AppCard v-if="purgeStageVisible" class="top__panel top__panel--danger">
          <AppSectionHeader title="4 · 永久销毁前最终门禁" />
          <div class="top__gates">
            <div :class="job.finalExportSha256 ? 'is-ok' : 'is-bad'"><b>最终导出</b><span>{{ job.finalExportSha256 ? '已确认 SHA-256' : '未确认' }}</span></div>
            <div :class="retentionExpired ? 'is-ok' : 'is-warn'"><b>保留期</b><span>{{ retentionExpired ? '已结束' : `截止 ${fmt(job.retentionUntil)}` }}</span></div>
            <div :class="legalHoldClear ? 'is-ok' : 'is-bad'"><b>司法保全</b><span>{{ legalHoldClear ? '无阻断' : '存在保全或证据未取得，禁止销毁' }}</span></div>
            <div :class="preview?.registry?.complete ? 'is-ok' : 'is-bad'"><b>销毁登记表</b><span>{{ preview?.registry?.complete ? '完整' : '不完整' }}</span></div>
            <div :class="mfaStatus.enabled ? 'is-ok' : 'is-bad'"><b>平台主管二次认证</b><span>{{ mfaStatus.enabled ? '动态口令已启用' : '尚未绑定' }}</span></div>
          </div>

          <div v-if="!mfaStatus.enabled" class="top__mfa-missing">
            <span>永久销毁必须使用真实的二次认证。</span>
            <AppButton variant="primary" @click="$router.push('/admin/platform/security')">前往安全策略绑定二次认证</AppButton>
          </div>

          <template v-else-if="job.state !== 'PURGED'">
            <div class="top__danger-box">
              <b>不可逆操作</b>
              <p>销毁会删除该租户的业务数据和受治理文件字节，仅保留合规控制面证据与删除凭证。失败后只能按同一任务继续执行。</p>
            </div>

            <div class="top__mfa-row">
              <label class="top__field">
                <span>认证器 6 位动态码</span>
                <input v-model.trim="mfaCode" inputmode="numeric" maxlength="6" class="top__input top__input--code" placeholder="000000" @keyup.enter="stepUpMfa" />
              </label>
              <AppButton variant="primary" :loading="mfaWorking" :disabled="busy || uncertain || mfaCode.length !== 6" @click="stepUpMfa">完成二次认证</AppButton>
              <StatusTag v-if="mfaGrantValid" type="success" label="二次认证已通过 · 本页临时授权" />
            </div>

            <label class="top__field top__confirm-field">
              <span>输入精确确认文案：<b>永久销毁租户数据</b></span>
              <input v-model="confirmText" class="top__input" autocomplete="off" placeholder="永久销毁租户数据" />
            </label>

            <div class="top__ops">
              <AppButton variant="danger" :loading="working" :disabled="!canExecutePurge" @click="approvePurge">永久销毁租户数据</AppButton>
              <span class="top__hint">二次认证临时凭证不会写入浏览器持久存储，到期或提交销毁后会立即从页面内存清除。</span>
            </div>
          </template>

          <div v-else class="top__purged">
            <b>租户数据已完成物理销毁</b>
            <span>销毁证据 SHA-256：{{ job.purgeEvidenceSha256 }}</span>
          </div>
        </AppCard>
      </template>
    </template>
  </div>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { ErrorState, LoadingState, StatusTag } from '@/components/business'
import { platformSecurityOpsApi } from '@/modules/platform/api/platformSecurityOps.api'
import { platformStatusLabel } from '@/modules/platform/constants/platform-display.constants'
import { toast } from '@/utils/toast'
import { wholeNumber } from '@/modules/platform/utils/tenantWorkspace.mjs'

const STATE_LABELS = {
  REQUESTED: '已发起', PRECHECK: '预检查', FROZEN_READONLY: '已冻结只读', FINAL_EXPORT_READY: '待确认最终导出',
  RETENTION: '数据保留期', PURGE_READY: '可销毁', PURGING: '销毁中', BLOCKED: '销毁阻断', FAILED: '销毁失败待续跑',
  PURGED: '已永久销毁', CANCELLED: '已取消'
}
const STEP_LABELS = {
  PRECHECK: '影响预检查', FREEZE: '冻结业务写入', FINAL_EXPORT: '最终数据导出', RETENTION: '数据保留期',
  PURGE_PRECHECK: '销毁前检查', PURGE: '物理销毁', CANCEL: '取消退租'
}

export default {
  name: 'TenantOffboardingPanel',
  components: { AppButton, AppCard, AppSectionHeader, ErrorState, LoadingState, StatusTag },
  props: {
    tenantId: { type: [String, Number], required: true },
    tenant: { type: Object, default: () => ({}) },
    tenant360: { type: Object, default: () => ({}) }
  },
  emits: ['changed'],
  data() {
    return {
      loading: true, ready: false, epoch: 0, uncertain: false, inspected: false,
      working: false,
      mfaWorking: false,
      error: '',
      preview: null,
      job: null,
      mfaStatus: { enabled: false, status: 'NONE' },
      requestForm: { reason: '', retentionDays: 30 },
      finalExportSha: '',
      cancelReason: '',
      mfaCode: '',
      mfaGrant: null,
      mfaExpiryTimer: null,
      confirmText: ''
    }
  },
  computed: {
    busy() { return this.loading || this.working || this.mfaWorking },
    legalHoldClear() { return wholeNumber(this.preview?.counts?.legalHoldFileCount) === 0 },
    protectNavigation() { return this.working || this.mfaWorking || this.uncertain || Boolean(this.requestForm.reason || this.cancelReason || this.mfaGrant) },
    canStartNew() {
      return this.ready && (!this.job || this.job.state === 'CANCELLED')
    },
    expectedTenantVersion() {
      return wholeNumber(this.preview?.effectiveState?.version)
    },
    validSha() {
      return /^[0-9a-fA-F]{64}$/.test(this.finalExportSha)
    },
    retentionExpired() {
      if (!this.job?.retentionUntil) return false
      return this.serverUtcEpoch(this.job.retentionUntil) <= Date.now()
    },
    purgeStageVisible() {
      return !!this.job && ['RETENTION', 'PURGE_READY', 'BLOCKED', 'FAILED', 'PURGING', 'PURGED'].includes(this.job.state)
    },
    purgePrechecksPass() {
      return !!(
        this.ready && this.expectedTenantVersion !== null &&
        /^[0-9a-fA-F]{64}$/.test(this.job?.finalExportSha256 || '') &&
        this.retentionExpired && this.legalHoldClear &&
        wholeNumber(this.preview?.counts?.activeFileJobCount) === 0 &&
        Array.isArray(this.preview?.blockers) && this.preview.blockers.length === 0 &&
        this.preview?.registry?.complete === true &&
        ['RETENTION', 'PURGE_READY', 'BLOCKED', 'FAILED', 'PURGING'].includes(this.job.state)
      )
    },
    mfaGrantValid() {
      return !!(this.mfaGrant?.accessToken && Number(this.mfaGrant.expiresAt || 0) > Date.now())
    },
    canExecutePurge() {
      return !this.busy && !this.uncertain && this.purgePrechecksPass && this.mfaStatus.enabled === true && this.mfaGrantValid && this.confirmText === '永久销毁租户数据'
    },
    jobStatusLabel() {
      return this.job ? this.stateLabel(this.job.state) : '尚未发起退租'
    },
    jobStatusType() {
      if (!this.job) return 'default'
      if (this.job.state === 'PURGED') return 'success'
      if (['BLOCKED', 'FAILED'].includes(this.job.state)) return 'danger'
      if (['RETENTION', 'FROZEN_READONLY', 'FINAL_EXPORT_READY', 'PURGE_READY', 'PURGING'].includes(this.job.state)) return 'warning'
      return 'default'
    }
  },
  watch: {
    tenantId() {
      this.epoch++; this.working = false; this.mfaWorking = false; this.uncertain = false; this.inspected = false
      this.requestForm = { reason: '', retentionDays: 30 }; this.cancelReason = ''; this.confirmText = ''; this.finalExportSha = ''
      this.load()
    }
  },
  created() {
    this.load()
  },
  beforeUnmount() {
    this.epoch++
    this.clearMfaGrant()
  },
  methods: {
    platformStatusLabel,
    stateLabel(state) {
      return STATE_LABELS[state] || '未知状态'
    },
    stepLabel(code) {
      return STEP_LABELS[code] || '其他处理步骤'
    },
    serverUtcEpoch(value) {
      if (!value) return NaN
      const raw = String(value)
      const normalized = /(Z|[+-]\d{2}:\d{2})$/i.test(raw) ? raw : `${raw}Z`
      return new Date(normalized).getTime()
    },
    fmt(value) {
      const epoch = this.serverUtcEpoch(value)
      if (!Number.isFinite(epoch)) return ''
      return new Date(epoch).toLocaleString('zh-CN', { hour12: false }).replace(/\//g, '-')
    },
    formatBytes(value) {
      if (value === null || value === undefined) return '—'
      const bytes = Number(value || 0)
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} 千字节`
      if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} 兆字节`
      return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} 吉字节`
    },
    clearMfaGrant() {
      if (this.mfaExpiryTimer) clearTimeout(this.mfaExpiryTimer)
      this.mfaExpiryTimer = null
      this.mfaGrant = null
      this.mfaCode = ''
    },
    current(epoch, id) { return this.epoch === epoch && String(this.tenantId) === id },
    canMutate() { return this.ready && !this.busy && !this.error && !this.uncertain && this.expectedTenantVersion !== null },
    async load() {
      if (this.working || this.mfaWorking) return
      const id = String(this.tenantId), epoch = ++this.epoch
      this.loading = true; this.ready = false; this.preview = null; this.job = null; this.finalExportSha = ''; this.inspected = false
      this.error = ''; this.mfaStatus = { enabled: false, status: 'NONE' }
      this.clearMfaGrant()
      try {
        const [preview, job, mfa] = await Promise.all([
          platformSecurityOpsApi.previewTenantOffboarding(this.tenantId),
          platformSecurityOpsApi.getTenantOffboarding(this.tenantId),
          platformSecurityOpsApi.getMfaStatus()
        ])
        if (!this.current(epoch, id)) return
        if (!/^[1-9]\d*$/.test(id) || typeof preview?.tenantId !== 'string' || preview.tenantId !== id || wholeNumber(preview?.effectiveState?.version) === null) throw new Error('未取得当前学校的身份或可信版本')
        if (job !== null && (!job || job.tenantId !== id || typeof job.jobId !== 'string' || !/^[1-9]\d*$/.test(job.jobId) || typeof job.state !== 'string')) throw new Error('退租任务与当前学校不一致')
        this.preview = preview; this.job = job
        this.mfaStatus = mfa && typeof mfa.enabled === 'boolean' ? mfa : { enabled: false, status: 'NONE' }
        this.finalExportSha = job?.finalExportSha256 || ''; this.ready = true; this.inspected = this.uncertain
      } catch (error) {
        if (this.current(epoch, id)) this.error = error.message || '退租与销毁状态加载失败'
      } finally { if (this.current(epoch, id)) this.loading = false }
    },
    async refreshAfterChange(message) {
      if (message) toast.success(message)
      // A keyed parent remount fetches current facts after this completed command.
      this.$emit('changed')
    },
    async requestOffboarding() {
      if (!this.canMutate() || !this.canStartNew) return
      if (wholeNumber(this.requestForm.retentionDays) === null) return toast.error('保留期必须是非负整数')
      if (this.requestForm.reason.length < 10) return toast.error('退租原因至少 10 个字符')
      if (!window.confirm('发起后该学校将立即冻结为只读，普通登录与业务写入会被拒绝。确认继续？')) return
      const id = String(this.tenantId), epoch = ++this.epoch
      this.working = true
      try {
        await platformSecurityOpsApi.requestTenantOffboarding(this.tenantId, {
          reason: this.requestForm.reason,
          retentionDays: Number(this.requestForm.retentionDays || 0),
          expectedVersion: this.expectedTenantVersion
        })
        if (!this.current(epoch, id)) return
        this.requestForm.reason = ''
        await this.refreshAfterChange('退租任务已创建，租户已冻结为只读')
      } catch (error) {
        if (!this.current(epoch, id)) return
        this.uncertain = true
        toast.error(error.message || '退租发起失败')
      } finally {
        if (this.current(epoch, id)) this.working = false
      }
    },
    async confirmFinalExport() {
      if (!this.canMutate() || !['FROZEN_READONLY', 'FINAL_EXPORT_READY'].includes(this.job?.state)) return
      if (!this.validSha) return toast.error('请输入 64 位 SHA-256')
      if (!window.confirm('确认该 SHA-256 对应已经交付并封存的最终数据导出物？确认后进入数据保留期。')) return
      const id = String(this.tenantId), epoch = ++this.epoch
      this.working = true
      try {
        await platformSecurityOpsApi.confirmTenantFinalExport(this.job.jobId, this.finalExportSha.toLowerCase())
        if (!this.current(epoch, id)) return
        await this.refreshAfterChange('最终导出已确认，租户已进入数据保留期')
      } catch (error) {
        if (!this.current(epoch, id)) return
        this.uncertain = true
        toast.error(error.message || '最终导出确认失败')
      } finally {
        if (this.current(epoch, id)) this.working = false
      }
    },
    async cancelOffboarding() {
      if (!this.canMutate() || this.job?.cancellable !== true) return
      if (this.cancelReason.length < 5) return toast.error('取消原因至少 5 个字符')
      if (!window.confirm('确认取消当前退租任务并恢复冻结前租户状态？')) return
      const id = String(this.tenantId), epoch = ++this.epoch
      this.working = true
      try {
        await platformSecurityOpsApi.cancelTenantOffboarding(this.job.jobId, this.cancelReason)
        if (!this.current(epoch, id)) return
        this.cancelReason = ''
        await this.refreshAfterChange('退租任务已取消')
      } catch (error) {
        if (!this.current(epoch, id)) return
        this.uncertain = true
        toast.error(error.message || '取消退租失败')
      } finally {
        if (this.current(epoch, id)) this.working = false
      }
    },
    async stepUpMfa() {
      if (!this.canMutate() || this.mfaStatus.enabled !== true) return
      if (!/^\d{6}$/.test(this.mfaCode)) return toast.error('请输入 6 位动态码')
      const code = this.mfaCode
      const id = String(this.tenantId), epoch = ++this.epoch
      this.mfaWorking = true
      this.clearMfaGrant()
      try {
        const grant = await platformSecurityOpsApi.stepUpMfa(code)
        if (!this.current(epoch, id)) return
        const ttlSeconds = Number(grant.expiresIn || 600)
        this.mfaGrant = {
          accessToken: grant.accessToken,
          expiresAt: Date.now() + ttlSeconds * 1000
        }
        this.mfaExpiryTimer = setTimeout(() => {
          this.mfaGrant = null
          this.mfaExpiryTimer = null
        }, ttlSeconds * 1000)
        toast.success('二次认证通过；临时授权只保存在本页内存中')
      } catch (error) {
        if (!this.current(epoch, id)) return
        toast.error(error.message || '二次认证失败')
      } finally {
        if (this.current(epoch, id)) this.mfaWorking = false
      }
    },
    async approvePurge() {
      if (!this.canMutate()) return
      if (!this.canExecutePurge) return toast.error('销毁门禁尚未全部满足')
      if (!window.confirm(`最后确认：将永久销毁“${this.preview?.tenantName || this.tenant?.tenantName || this.tenantId}”的数据。该操作不可撤销。`)) return
      const id = String(this.tenantId), epoch = ++this.epoch
      this.working = true
      const token = this.mfaGrant.accessToken
      try {
        await platformSecurityOpsApi.approveTenantPurge(this.job.jobId, {
          expectedVersion: Number(this.job.tenantVersion ?? this.expectedTenantVersion),
          confirmText: this.confirmText
        }, token)
        if (!this.current(epoch, id)) return
        this.confirmText = ''
        await this.refreshAfterChange('租户数据物理销毁完成，销毁证据已生成')
      } catch (error) {
        if (!this.current(epoch, id)) return
        this.uncertain = true
        toast.error(error.message || '永久销毁执行失败')
        // Keep the unconfirmed outcome visible; readback is an explicit action.
      } finally {
        if (this.current(epoch, id)) this.clearMfaGrant()
        if (this.current(epoch, id)) this.working = false
      }
    }
  }
}
</script>

<style scoped>
.top { display: flex; flex-direction: column; gap: var(--space-3); }
.top__panel { padding: var(--space-4); }
.top__panel--summary { border-top: 3px solid var(--glow, #2563eb); }
.top__panel--danger { border-color: rgba(180, 35, 24, .28); }
.top__header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.top__header h3 { margin: 2px 0 4px; color: var(--t1); font-size: 20px; }
.top__header p, .top__note { margin: 0; color: var(--text-tertiary); font-size: 12px; line-height: 1.65; }
.top__eyebrow { color: var(--glow, #2563eb); font-size: 11px; font-weight: 700; letter-spacing: .08em; }
.top__metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
.top__metrics > div, .top__job-grid > div { display: flex; flex-direction: column; gap: 3px; padding: var(--space-2) var(--space-3); border: 1px solid var(--card-b); border-radius: 9px; background: rgba(255,255,255,.58); }
.top__metrics span, .top__job-grid span, .top__reason span { color: var(--text-tertiary); font-size: 11px; }
.top__metrics b, .top__job-grid b { color: var(--t1); font-size: 14px; }
.top__registry { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); margin-top: var(--space-3); padding: var(--space-2) var(--space-3); border-radius: 9px; font-size: 12px; }
.top__registry.is-ok { background: rgba(22, 163, 74, .08); color: #166534; }
.top__registry.is-bad { background: rgba(220, 38, 38, .08); color: #991b1b; }
.top__blockers { margin: var(--space-2) 0 0; padding-left: 18px; color: #991b1b; font-size: 12px; line-height: 1.6; }
.top__form-grid { display: grid; grid-template-columns: minmax(0, 1fr) 180px; gap: var(--space-3); margin-top: var(--space-3); align-items: end; }
.top__field { display: flex; flex-direction: column; gap: var(--space-1); font-size: 12px; color: var(--text-secondary); }
.top__field--wide { min-width: 0; }
.top__input, .top__textarea { border: 1px solid var(--card-b); border-radius: 9px; background: rgba(255,255,255,.88); color: var(--t1); font: inherit; }
.top__input { height: 36px; padding: 0 10px; }
.top__textarea { padding: 9px 10px; resize: vertical; }
.top__input:focus, .top__textarea:focus { outline: none; border-color: var(--glow); }
.top__input--grow { flex: 1 1 320px; }
.top__input--hash { flex: 1 1 520px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.top__input--code { width: 150px; letter-spacing: .18em; font-variant-numeric: tabular-nums; }
.top__ops, .top__inline, .top__mfa-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-top: var(--space-3); }
.top__hint { color: var(--text-tertiary); font-size: 11px; line-height: 1.5; }
.top__job-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
.top__reason { display: flex; flex-direction: column; gap: 3px; margin-top: var(--space-2); padding: var(--space-2) 0; }
.top__reason b { color: var(--t1); font-size: 13px; }
.top__steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
.top__step { display: flex; gap: var(--space-2); align-items: flex-start; padding: var(--space-2); border-radius: 9px; background: rgba(255,255,255,.55); }
.top__step-dot { width: 10px; height: 10px; margin-top: 4px; border-radius: 50%; background: #94a3b8; flex: none; }
.top__step-dot.is-succeeded { background: #16a34a; }
.top__step-dot.is-running { background: #2563eb; }
.top__step-dot.is-failed, .top__step-dot.is-blocked { background: #dc2626; }
.top__step b { display: block; color: var(--t1); font-size: 12px; }
.top__step small { display: block; margin-top: 2px; color: var(--text-tertiary); font-size: 11px; line-height: 1.4; }
.top__gates { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--space-2); margin-top: var(--space-3); }
.top__gates > div { display: flex; flex-direction: column; gap: 3px; padding: var(--space-2) var(--space-3); border-radius: 9px; border: 1px solid transparent; font-size: 11px; }
.top__gates b { font-size: 12px; }
.top__gates .is-ok { background: rgba(22, 163, 74, .08); color: #166534; }
.top__gates .is-warn { background: rgba(217, 119, 6, .09); color: #92400e; }
.top__gates .is-bad { background: rgba(220, 38, 38, .08); color: #991b1b; }
.top__mfa-missing, .top__purged { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-3); padding: var(--space-3); border-radius: 9px; background: rgba(217,119,6,.09); color: #92400e; font-size: 12px; }
.top__danger-box { margin-top: var(--space-3); padding: var(--space-3); border-radius: 9px; background: rgba(220,38,38,.07); color: #991b1b; }
.top__danger-box p { margin: 4px 0 0; font-size: 12px; line-height: 1.6; }
.top__confirm-field { margin-top: var(--space-3); max-width: 560px; }
.top__danger { color: #b42318 !important; }
.top__purged { flex-direction: column; align-items: flex-start; background: rgba(22,163,74,.08); color: #166534; }
@media (max-width: 760px) {
  .top__header, .top__registry, .top__mfa-missing { flex-direction: column; align-items: flex-start; }
  .top__form-grid { grid-template-columns: 1fr; }
}
</style>
