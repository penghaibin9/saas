<template>
  <ModulePageShell
    title="商业授权与模块生命周期"
    subtitle="按学校处理单模块购买、交付、续费、退订、冻结与数据签收；整校退租保持独立"
    role-name="平台商业/交付负责人"
    data-scope-name="全平台商业控制"
  >
    <div class="commerce">
      <section class="hero">
        <div>
          <span class="eyebrow">MODULE COMMERCE</span>
          <h3>{{ conclusion }}</h3>
          <p>单模块退订不会停用整所学校，也不会影响其他已购模块、共享账号与学生主档。</p>
        </div>
        <button class="btn primary" :disabled="loading" @click="loadAll">刷新真实状态</button>
      </section>

      <ModuleSalesWorkspace
        :tenant-id="selectedTenantId"
        :locked="busy"
        @update:tenant-id="changeSalesSchool"
        @order-created="loadPortfolio"
      />

      <ModuleFinanceWorkspace
        :tenant-id="selectedTenantId"
        :locked="busy"
      />

      <section v-if="portfolio" class="module-grid">
        <article
          v-for="mod in portfolio.modules"
          :key="mod.moduleKey"
          class="module-card"
          :class="{ active: selectedModuleKey === mod.moduleKey }"
          @click="selectModule(mod.moduleKey)"
        >
          <header>
            <div>
              <span class="module-name">{{ moduleName(mod.moduleKey) }}</span>
              <small>generation {{ mod.generation || '-' }}</small>
            </div>
            <span class="pill" :class="mod.entitled ? 'ok' : 'muted'">{{ mod.entitled ? '已授权' : '未授权' }}</span>
          </header>
          <div class="metrics">
            <div><strong>{{ dataStateLabel(mod.dataState) }}</strong><span>数据状态</span></div>
            <div><strong>{{ mod.currentSourceCount }}</strong><span>当前来源</span></div>
            <div><strong>{{ bytes(mod.logicalFileBytes) }}</strong><span>逻辑文件</span></div>
            <div><strong>{{ bytes(mod.heldReservationBytes) }}</strong><span>占用预留</span></div>
          </div>
          <footer>
            <span>{{ mod.deliveryAcceptance ? '交付已验收' : (mod.staleDeliveryAcceptance ? '合同来源已变化，需重新验收' : '待交付验收') }}</span>
            <span v-if="mod.offboardingJobId">退出任务 #{{ mod.offboardingJobId }}</span>
          </footer>
        </article>
      </section>

      <template v-if="selectedModule">
        <section class="workspace-head">
          <div>
            <span class="eyebrow">ONE MODULE WORKSPACE</span>
            <h3>{{ moduleName(selectedModule.moduleKey) }} · 一次办完</h3>
            <p>当前授权、来源、交付、停续、退出和数据签收都绑定同一个 tenant + module + generation。</p>
          </div>
          <span class="state-chip">{{ dataStateLabel(selectedModule.dataState) }}</span>
        </section>

        <section class="flow-grid">
          <article class="panel flow-step">
            <span class="step-no">1</span>
            <h4>交付验收</h4>
            <p>只冻结交付证据，不新增授权。必须绑定当前 generation 与订阅来源摘要。</p>
            <div v-if="selectedModule.deliveryAcceptance" class="success-box">
              已验收 · {{ selectedModule.deliveryAcceptance.acceptanceRef }}
            </div>
            <div v-else class="form-grid">
              <div v-if="selectedModule.staleDeliveryAcceptance" class="warning-box">
                合同来源已变化：原验收 {{ selectedModule.staleDeliveryAcceptance.acceptanceRef }} 已保留为历史证据，但不再代表当前合同来源；请重新验收。
              </div>
              <input v-model.trim="deliveryForm.acceptanceRef" placeholder="学校验收编号，如 YS-2026-001">
              <input v-model.trim="deliveryForm.reason" placeholder="验收说明（至少 5 个字符）">
              <button class="btn primary" :disabled="busy || !selectedModule.entitled" @click="acceptDelivery">记录模块交付验收</button>
            </div>
          </article>

          <article class="panel flow-step">
            <span class="step-no">2</span>
            <h4>续费与计划退订</h4>
            <p>“期末停续”不会提前断权；已付服务期结束前仍可正常使用。</p>
            <input v-model.trim="cancelReason" class="full-input" placeholder="停续/恢复原因（至少 5 个字符）">
            <div v-if="selectedModule.sources.length" class="source-list">
              <div v-for="src in selectedModule.sources" :key="src.sourceId" class="source-row">
                <div>
                  <strong>{{ src.sourceType }} · {{ src.sourceRef }}</strong>
                  <small>{{ dateTime(src.startsAt) }} → {{ dateTime(src.endsAt) }}</small>
                </div>
                <div class="source-action">
                  <span class="pill" :class="src.status === 'CANCEL_SCHEDULED' ? 'warn' : 'ok'">{{ sourceStatus(src.status) }}</span>
                  <button v-if="src.status !== 'CANCEL_SCHEDULED' && ['ACTIVE', 'SCHEDULED'].includes(src.status)" class="btn" :disabled="busy" @click="scheduleCancel(src)">期末停续</button>
                  <button v-else-if="src.status === 'CANCEL_SCHEDULED'" class="btn" :disabled="busy" @click="resumeRenewal(src)">撤销停续</button>
                </div>
              </div>
            </div>
            <div v-else class="empty">没有订阅来源</div>
          </article>

          <article class="panel flow-step">
            <span class="step-no">3</span>
            <h4>模块退出与冻结</h4>
            <p>只冻结当前模块代次，不改 Tenant 状态、不踢整校会话、不影响兄弟模块。</p>
            <button class="btn" :disabled="busy" @click="loadOffboardPreview">重新预检</button>

            <div v-if="preview" class="preview-box">
              <div v-if="preview.blockers?.length" class="blockers">
                <strong>当前不能退出</strong>
                <p v-for="blocker in preview.blockers" :key="blocker.code">{{ blocker.message }}</p>
              </div>

              <div v-if="preview.consumerDependencies" class="consumer-evidence">
                <div class="consumer-head">
                  <div>
                    <strong>跨域消费者与正式事实</strong>
                    <small>{{ dispositionLabel(preview.consumerDependencies.disposition) }}</small>
                  </div>
                  <span class="pill" :class="preview.consumerDependencies.objectEvidence?.hasUnsettledSharedObjects ? 'warn' : 'muted'">
                    {{ preview.consumerDependencies.objectEvidence?.hasUnsettledSharedObjects ? '仍有未完成共享对象' : '对象快照已读取' }}
                  </span>
                </div>
                <p>{{ preview.consumerDependencies.message }}</p>
                <div v-if="consumerEvidenceRows(preview.consumerDependencies).length" class="evidence-grid">
                  <div v-for="row in consumerEvidenceRows(preview.consumerDependencies)" :key="row.key" class="evidence-card" :class="row.kind">
                    <strong>{{ row.value }}</strong>
                    <span>{{ row.label }}</span>
                  </div>
                </div>
                <div class="digest-line">
                  <span>对象证据 {{ shortDigest(preview.consumerDependencies.objectEvidence?.objectEvidenceDigest) }}</span>
                  <span>消费者摘要 {{ shortDigest(preview.consumerDependencies.dependencyDigest) }}</span>
                </div>
                <div v-if="preview.purgeBlockers?.length" class="safety-note">
                  当前只允许办理冻结与交付；这些消费者证据仍阻断未来物理清理，不影响本次安全冻结。
                </div>
              </div>

              <div v-if="!preview.blockers?.length && !job" class="form-grid">
                <input v-model.trim="offboardForm.reason" placeholder="退出原因（至少 10 个字符）">
                <div class="two-col">
                  <input v-model.number="offboardForm.retentionDays" type="number" min="1" max="3650" placeholder="保留天数">
                  <input v-model.trim="offboardForm.retentionPolicyVersion" placeholder="保留政策版本">
                </div>
                <label class="check">
                  <input v-model="offboardForm.confirmed" type="checkbox">
                  <span>我确认这是“单模块退出”，不是整校退租；当前不执行物理销毁。</span>
                </label>
                <button class="btn danger" :disabled="busy || !offboardForm.confirmed || !preview.canRequest" @click="requestOffboarding">冻结此模块 generation</button>
              </div>
            </div>

            <div v-if="job" class="job-box">
              <div class="job-title">
                <strong>退出任务 #{{ job.jobId }}</strong>
                <span class="pill warn">{{ job.state }}</span>
              </div>
              <p>scopeHash：<code>{{ job.scopeHash }}</code></p>
              <p>保留政策：{{ job.retentionPolicyVersion }} · {{ job.retentionDays }} 天</p>
              <div v-if="job.consumerDependencies" class="job-consumer-summary">
                <span>{{ dispositionLabel(job.consumerDependencies.disposition) }}</span>
                <span>当前摘要 {{ shortDigest(job.consumerDependencies.dependencyDigest) }}</span>
              </div>
              <button v-if="!job.irreversibleStartedAt && !['CANCELLED', 'RETENTION'].includes(job.state)" class="btn" :disabled="busy" @click="cancelOffboarding">不可逆前撤回退出</button>
            </div>
          </article>

          <article class="panel flow-step">
            <span class="step-no">4</span>
            <h4>最终数据交付与签收</h4>
            <p>不接受手填 SHA 或数据库 ID。只使用服务端核验的 ExportJob + Manifest + FileObject + 实际附件 + 存储对象，并绑定当时的消费者对象快照。</p>
            <div v-if="!job" class="empty">先完成模块退出预检与冻结</div>

            <template v-else>
              <div v-if="job.state === 'FROZEN'" class="form-grid">
                <div v-if="job.exportCandidates?.length" class="source-list">
                  <div v-for="candidate in job.exportCandidates" :key="candidate.exportJobId" class="source-row export-candidate">
                    <div>
                      <strong>{{ candidate.fileName || ('交付包 #' + candidate.exportJobId) }}</strong>
                      <small>服务端已核验 · {{ bytes(candidate.fileSizeBytes) }} · {{ candidate.objectCount }} 个对象 · {{ candidate.attachmentCount }} 个附件</small>
                      <small>{{ dateTime(candidate.finishedAt) }}</small>
                    </div>
                    <button class="btn primary" :disabled="busy" @click="bindExport(candidate)">绑定此交付包并封存消费者快照</button>
                  </div>
                </div>
                <div v-else class="empty">当前没有服务端已核验的最终导出候选。请先在该业务模块完成正式导出/归档；本页不会要求你复制数据库 ID，也不会用手填 SHA 冒充交付。</div>
                <input :value="job.scopeHash" disabled>
              </div>

              <div v-else-if="job.state === 'WAIT_EXPORT_ACCEPT'" class="form-grid">
                <div v-if="job.deliveryAcceptanceReady" class="success-box evidence-ready">
                  <strong>交付包与当前消费者对象快照一致，可以签收</strong>
                  <span>交付证据 {{ shortDigest(job.deliveryEvidenceDigest) }}</span>
                  <span>消费者摘要 {{ shortDigest(job.consumerDependencySnapshot?.dependencyDigest) }}</span>
                </div>
                <div v-else class="warning-box">
                  <strong>当前交付包不能签收</strong>
                  <p v-for="blocker in job.deliveryAcceptanceBlockers || []" :key="blocker.code">{{ blocker.message }}</p>
                  <p>这通常表示绑定交付包后又新增或变化了审批、待办、消息投递、文件绑定或正式业务事实。旧包不会被“重新确认”洗白。</p>
                </div>

                <div v-if="!job.deliveryAcceptanceReady" class="rebind-box">
                  <strong>恢复路径：重新生成正式交付包 → 绑定新的 ExportJob/Manifest</strong>
                  <div v-if="freshExportCandidates.length" class="source-list">
                    <div v-for="candidate in freshExportCandidates" :key="candidate.exportJobId" class="source-row export-candidate">
                      <div>
                        <strong>{{ candidate.fileName || ('新交付包 #' + candidate.exportJobId) }}</strong>
                        <small>{{ bytes(candidate.fileSizeBytes) }} · {{ candidate.objectCount }} 个对象 · {{ candidate.attachmentCount }} 个附件</small>
                        <small>{{ dateTime(candidate.finishedAt) }}</small>
                      </div>
                      <button class="btn primary" :disabled="busy" @click="bindExport(candidate)">重新绑定新交付包</button>
                    </div>
                  </div>
                  <div v-else class="empty">暂时没有新的已核验候选。请回到对应业务模块重新执行正式导出/归档；生成新包后刷新本页即可，不需要复制数据库 ID 或 SHA。</div>
                </div>

                <input v-model.trim="exportForm.acceptanceRef" placeholder="校方接收凭据编号">
                <button class="btn primary" :disabled="busy || !job.deliveryAcceptanceReady" @click="acceptExport">校方确认接收并开始保留期</button>
              </div>

              <div v-else-if="job.state === 'RETENTION'" class="success-box">
                已进入合规保留期，截止 {{ dateTime(job.retentionUntil) }}。M5 到此停止，未开启物理销毁。
              </div>
              <div v-else class="empty">当前任务状态：{{ job.state }}</div>
            </template>
          </article>
        </section>
      </template>

      <section class="panel reconcile-panel">
        <header class="section-title">
          <div>
            <h3>全校商业与存储对账</h3>
            <p>继续保留原有配额/真实消费核对，不与模块逻辑用量混为一谈。</p>
          </div>
        </header>
        <table>
          <thead><tr><th>学校</th><th>套餐</th><th>商业上限</th><th>学校配额</th><th>实际消费</th><th>结论</th></tr></thead>
          <tbody>
            <tr v-for="item in items" :key="item.tenantId">
              <td>{{ item.tenantName }}</td><td>{{ packageLabel(item.packageCode) }}</td><td>{{ bytes(item.commercialStorageLimitBytes) }}</td><td>{{ bytes(item.schoolGovernanceQuotaBytes) }}</td><td>{{ bytes(item.actualConsumptionBytes) }}</td><td><strong :class="item.healthy ? 'ok-text' : 'bad-text'">{{ item.healthy ? '一致' : violationLabels(item.violations) }}</strong></td>
            </tr>
            <tr v-if="!items.length"><td colspan="6">暂无学校对账数据</td></tr>
          </tbody>
        </table>
      </section>

      <div v-if="message" class="toast" :class="messageType">{{ message }}</div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { moduleCommerceApi } from '@/modules/platform/api/moduleCommerce.api'
import ModuleSalesWorkspace from './ModuleSalesWorkspace.vue'
import ModuleFinanceWorkspace from './ModuleFinanceWorkspace.vue'

const MODULE_LABEL = {
  internship: '岗位实习中心',
  graduationDesign: '毕业设计中心',
  studentAffairs: '学工中心',
  academicAffairs: '教务中心'
}

const DISPOSITION_LABEL = {
  SOURCE_BOUND_EVIDENCE_RETAIN_REQUIRED: '正式证据需长期保留',
  SOURCE_PROCESS_UNRESOLVED: '业务过程尚未闭环',
  SHARED_CONSUMER_EVIDENCE_RETAIN_REQUIRED: '共享消费者证据需保留',
  FORMAL_ACADEMIC_FACTS_RETAIN_REQUIRED: '正式教务事实需长期保留',
  FORMAL_ACADEMIC_FACTS_RETAIN_REVIEW_REQUIRED: '教务正式事实待复审',
  MODULE_RESOURCE_REVIEW_REQUIRED: '模块资源待复审',
  NO_SOURCE_CONSUMER_FACTS_FOUND: '未发现来源消费事实'
}

const EVIDENCE_LABEL = {
  workflowInstances: '审批实例', workflowTasks: '审批任务', todos: '统一待办', messages: '个人消息',
  messageCampaigns: '消息发布单', messageOutbox: '消息事件队列', messageDeliveryJobs: '消息批投递',
  messageChannelDeliveries: '外部渠道投递', fileBindings: '文件绑定', distinctBoundFiles: '绑定文件',
  archiveBatches: '学工归档批次', archivedBatches: '已归档批次', archivePackages: '学工档案包',
  archivedPackages: '已归档档案包', generatedPackageFiles: '档案包文件', academicStudents: '教务学生主档',
  formalGrades: '正式成绩', activeGrades: '当前有效成绩', passedActiveGrades: '已通过有效成绩',
  effectiveGradePolicySnapshots: '成绩政策快照', activeGradeCorrections: '成绩更正链',
  runningWorkflowInstances: '未完成·审批实例', pendingWorkflowTasks: '未完成·审批任务', pendingTodos: '未完成·待办',
  unfinishedMessageCampaigns: '未完成·消息发布', unsettledMessageOutbox: '未完成·消息事件',
  unsettledMessageDeliveryJobs: '未完成·批投递', unsettledMessageChannelDeliveries: '未完成·外部渠道投递'
}

export default {
  name: 'PlatformCommercialControlView',
  components: { ModulePageShell, ModuleSalesWorkspace, ModuleFinanceWorkspace },
  data: () => ({
    items: [], selectedTenantId: '', portfolio: null, selectedModuleKey: '', preview: null, job: null,
    loading: false, busy: false, portfolioSeq: 0, moduleSeq: 0, message: '', messageType: 'success', cancelReason: '',
    deliveryForm: { acceptanceRef: '', reason: '' },
    offboardForm: { reason: '', retentionDays: 30, retentionPolicyVersion: 'SCHOOL-CONTRACT', confirmed: false },
    exportForm: { acceptanceRef: '' }
  }),
  computed: {
    selectedModule () {
      return this.portfolio?.modules?.find(item => item.moduleKey === this.selectedModuleKey) || null
    },
    conclusion () {
      const bad = this.items.filter(item => !item.healthy).length
      if (bad) return `发现 ${bad} 所学校存在商业授权或配额待处理项`
      if (this.portfolio) return `${this.portfolio.tenantName} 的四个核心模块可独立查看与办理`
      return '商业授权、模块生命周期与真实消费统一办理'
    },
    freshExportCandidates () {
      const currentExport = String(this.job?.exportJobId || '')
      const currentManifest = String(this.job?.manifestId || '')
      return (this.job?.exportCandidates || []).filter(candidate => (
        String(candidate.exportJobId || '') !== currentExport || String(candidate.manifestId || '') !== currentManifest
      ))
    }
  },
  created () { this.loadAll() },
  methods: {
    changeSalesSchool (id) {
      this.selectedTenantId = id; this.portfolio = null; this.preview = null; this.job = null; this.selectedModuleKey = ''; this.cancelReason = ''
      this.deliveryForm = { acceptanceRef: '', reason: '' }; this.exportForm = { acceptanceRef: '' }; this.loadPortfolio()
    },
    moduleName (key) { return MODULE_LABEL[key] || key },
    bytes (value) {
      if (value == null) return '未配置'
      const n = Number(value); if (!Number.isFinite(n)) return '-'
      if (n < 1024 ** 2) return `${(n / 1024).toFixed(1)} KB`
      if (n < 1024 ** 3) return `${(n / 1024 ** 2).toFixed(1)} MB`
      return `${(n / 1024 ** 3).toFixed(2)} GB`
    },
    dateTime (value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '-' },
    shortDigest (value) { const text = String(value || ''); return text ? `${text.slice(0, 10)}…${text.slice(-6)}` : '-' },
    dispositionLabel (value) { return DISPOSITION_LABEL[value] || value || '待核验' },
    consumerEvidenceRows (dependency) {
      const evidence = dependency?.objectEvidence || {}
      const sections = [
        ['shared', evidence.sharedObjectCounts || {}],
        ['domain', evidence.domainFactCounts || {}],
        ['unsettled', evidence.unsettledSharedObjectCounts || {}]
      ]
      return sections.flatMap(([kind, values]) => Object.entries(values)
        .filter(([, value]) => Number(value || 0) > 0)
        .map(([key, value]) => ({ key: `${kind}:${key}`, kind, value: Number(value), label: EVIDENCE_LABEL[key] || key })))
    },
    dataStateLabel (value) { return ({ NONE: '未建立', AVAILABLE: '可用', FROZEN: '已冻结', RETAINED: '合规保留', PURGING: '清理中', PURGED: '已销毁' })[value] || value || '-' },
    sourceStatus (value) { return ({ ACTIVE: '生效中', SCHEDULED: '待生效', CANCEL_SCHEDULED: '期末停续', CANCELLED: '已取消' })[value] || value },
    packageLabel (value) { return ({ trial: '试用版', basic: '基础版', standard: '标准版', professional: '专业版', private: '私有化版' })[value] || '模块化合同' },
    violationLabels (rows) {
      const labels = { SCHOOL_QUOTA_EXCEEDS_COMMERCIAL: '学校配额超过商业上限', ACTUAL_USAGE_EXCEEDS_COMMERCIAL: '实际用量超过商业上限', UNAUTHORIZED_MODULE_USAGE: '发现未授权模块用量', PAID_ORDER_NOT_PROVISIONED: '已付订单未完成开通', LEGACY_ENTITLEMENT_OVERRIDE: '仍有历史授权覆盖' }
      return (rows || []).map(row => labels[row.code] || row.code || '待处理').join(' / ')
    },
    notify (text, type = 'success') {
      this.message = text; this.messageType = type; window.clearTimeout(this._messageTimer)
      this._messageTimer = window.setTimeout(() => { this.message = '' }, 4000)
    },
    errorText (error) { return error?.message || error?.response?.data?.message || '操作失败，请刷新后重试' },
    async loadAll () {
      this.loading = true
      try {
        const res = await platformControlApi.listReconciliations(); this.items = res?.data?.items || res?.data || []
        if (!this.selectedTenantId && this.items.length) this.selectedTenantId = String(this.items[0].tenantId)
        if (this.selectedTenantId) await this.loadPortfolio()
      } catch (error) { this.notify(this.errorText(error), 'error') } finally { this.loading = false }
    },
    async loadPortfolio () {
      const id = this.selectedTenantId; const seq = ++this.portfolioSeq
      if (!id) { this.portfolio = null; return }
      this.busy = true
      try {
        const portfolio = await moduleCommerceApi.getPortfolio(id)
        if (id !== this.selectedTenantId || seq !== this.portfolioSeq) return
        this.portfolio = portfolio
        if (!this.selectedModuleKey || !this.portfolio.modules.some(item => item.moduleKey === this.selectedModuleKey)) this.selectedModuleKey = this.portfolio.modules[0]?.moduleKey || ''
        await this.afterModuleRefresh()
      } catch (error) {
        if (id === this.selectedTenantId && seq === this.portfolioSeq) { this.portfolio = null; this.notify(this.errorText(error), 'error') }
      } finally { if (seq === this.portfolioSeq) this.busy = false }
    },
    async selectModule (key) { this.selectedModuleKey = key; this.preview = null; this.job = null; await this.afterModuleRefresh() },
    async afterModuleRefresh () {
      const module = this.selectedModule; const id = this.selectedTenantId; const seq = ++this.moduleSeq
      this.job = null; if (!module?.offboardingJobId) return
      try {
        const job = await moduleCommerceApi.getOffboarding(module.offboardingJobId)
        if (seq === this.moduleSeq && id === this.selectedTenantId && module.moduleKey === this.selectedModuleKey) this.job = job
      } catch { if (seq === this.moduleSeq) this.job = null }
    },
    async acceptDelivery () {
      const module = this.selectedModule; if (!module) return
      await this.run(async () => {
        await moduleCommerceApi.acceptDelivery(this.selectedTenantId, module.moduleKey, { acceptanceRef: this.deliveryForm.acceptanceRef, reason: this.deliveryForm.reason, expectedGeneration: module.generation })
        this.notify('模块交付验收已冻结'); await this.loadPortfolio()
      })
    },
    async scheduleCancel (source) {
      await this.run(async () => {
        await moduleCommerceApi.scheduleCancellation(this.selectedTenantId, source.sourceId, { expectedVersion: source.version, reason: this.cancelReason })
        this.notify('已计划期末停续；当前已付服务期不受影响'); await this.loadPortfolio()
      })
    },
    async resumeRenewal (source) {
      await this.run(async () => {
        await moduleCommerceApi.resumeRenewal(this.selectedTenantId, source.sourceId, { expectedPlanVersion: source.cancelPlanVersion, reason: this.cancelReason })
        this.notify('已撤销计划停续'); await this.loadPortfolio()
      })
    },
    async loadOffboardPreview () {
      if (!this.selectedModule) return
      await this.run(async () => {
        this.preview = await moduleCommerceApi.previewOffboarding(this.selectedTenantId, this.selectedModule.moduleKey)
        if (this.preview.blockers?.length) this.notify('预检发现阻断项，请先处理订阅来源或整校退出冲突', 'warning')
      })
    },
    async requestOffboarding () {
      const module = this.selectedModule; if (!module || !this.preview?.canRequest) return
      await this.run(async () => {
        this.job = await moduleCommerceApi.requestOffboarding(this.selectedTenantId, module.moduleKey, { expectedLifecycleVersion: this.preview.lifecycleVersion, reason: this.offboardForm.reason, retentionDays: this.offboardForm.retentionDays, retentionPolicyVersion: this.offboardForm.retentionPolicyVersion })
        this.notify('目标模块 generation 已冻结；其他模块和整校状态未改变'); await this.loadPortfolio()
      })
    },
    async cancelOffboarding () {
      if (!this.job) return
      await this.run(async () => {
        this.job = await moduleCommerceApi.cancelOffboarding(this.job.jobId, { expectedVersion: this.job.version, reason: this.offboardForm.reason || '学校撤回本次模块退出' })
        this.notify('模块退出已撤回；数据状态恢复，不会凭空恢复商业授权'); await this.loadPortfolio()
      })
    },
    async bindExport (candidate) {
      if (!this.job || !candidate) return
      const wasBound = this.job.state === 'WAIT_EXPORT_ACCEPT'
      await this.run(async () => {
        this.job = await moduleCommerceApi.bindExport(this.job.jobId, { exportJobId: candidate.exportJobId, manifestId: candidate.manifestId, scopeHash: this.job.scopeHash, expectedVersion: this.job.version })
        this.notify(wasBound ? '新交付包已重新绑定，并封存当前消费者对象快照' : '服务端已核验的交付包绑定成功，并封存当前消费者对象快照')
      })
    },
    async acceptExport () {
      if (!this.job?.deliveryAcceptanceReady) { this.notify('当前交付包与消费者对象快照不一致，不能签收', 'warning'); return }
      await this.run(async () => {
        this.job = await moduleCommerceApi.acceptExport(this.job.jobId, { acceptanceRef: this.exportForm.acceptanceRef, expectedVersion: this.job.version })
        this.notify('校方签收已记录，保留期从签收时间开始；未启动物理销毁'); await this.loadPortfolio()
      })
    },
    async run (fn) {
      if (this.busy) return
      this.busy = true
      try { await fn() } catch (error) { this.notify(this.errorText(error), 'error') } finally { this.busy = false }
    }
  }
}
</script>

<style scoped>
.commerce{display:grid;gap:18px;position:relative}.hero,.panel,.workspace-head{background:#fff;border:1px solid #e5eaf2;border-radius:16px;padding:20px;box-shadow:0 1px 2px rgba(16,24,40,.03)}.hero,.workspace-head,.section-title{display:flex;align-items:flex-start;justify-content:space-between;gap:18px}.hero h3,.workspace-head h3,.section-title h3{margin:4px 0 7px;font-size:20px;color:#17233d}.hero p,.workspace-head p,.section-title p,.flow-step p{margin:0;color:#667085;line-height:1.6}.eyebrow{font-size:11px;letter-spacing:.12em;color:#356ae6;font-weight:700}.btn{border:1px solid #d0d8e6;background:#fff;border-radius:9px;padding:8px 12px;cursor:pointer;color:#344054}.btn:hover{border-color:#8aa8ef}.btn:disabled{opacity:.45;cursor:not-allowed}.btn.primary{background:#315fda;border-color:#315fda;color:#fff}.btn.danger{background:#b42318;border-color:#b42318;color:#fff}select,input{border:1px solid #d6deea;border-radius:9px;padding:10px 11px;background:#fff;min-height:40px;box-sizing:border-box}select:focus,input:focus{outline:none;border-color:#6f91eb;box-shadow:0 0 0 3px rgba(53,106,230,.1)}.module-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.module-card{background:#fff;border:1px solid #e5eaf2;border-radius:14px;padding:16px;cursor:pointer;transition:.15s ease}.module-card:hover,.module-card.active{border-color:#7f9fee;box-shadow:0 4px 16px rgba(42,89,190,.08)}.module-card.active{background:#f8faff}.module-card header,.source-row,.job-title,.consumer-head{display:flex;align-items:center;justify-content:space-between;gap:12px}.module-name{display:block;font-weight:700;color:#17233d}.module-card small,.source-row small,.consumer-head small{display:block;margin-top:4px;color:#98a2b3}.pill,.state-chip{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:12px;font-weight:600}.pill.ok{background:#ecfdf3;color:#067647}.pill.muted{background:#f2f4f7;color:#667085}.pill.warn,.state-chip{background:#fff6e6;color:#b54708}.metrics{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:16px 0}.metrics div{padding:9px;background:#f8fafc;border-radius:10px}.metrics strong,.metrics span{display:block}.metrics strong{font-size:14px;color:#344054}.metrics span{font-size:11px;color:#98a2b3;margin-top:3px}.module-card footer{display:flex;flex-wrap:wrap;gap:7px;color:#667085;font-size:12px}.flow-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px}.flow-step{position:relative;padding-top:46px}.step-no{position:absolute;top:16px;left:20px;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;background:#315fda;color:#fff;font-size:12px;font-weight:700}.flow-step h4{margin:0 0 7px;color:#17233d}.form-grid{display:grid;gap:9px;margin-top:14px}.two-col{display:grid;grid-template-columns:1fr 1fr;gap:8px}.full-input{width:100%;margin:12px 0 8px}.source-list{display:grid;gap:8px}.source-row{padding:10px;border:1px solid #eaecf0;border-radius:10px}.source-action{display:flex;align-items:center;gap:7px}.preview-box,.job-box,.success-box,.warning-box,.empty,.rebind-box{margin-top:12px;border-radius:10px;padding:12px}.preview-box,.job-box,.rebind-box{background:#f8fafc;border:1px solid #e4e7ec}.success-box{background:#ecfdf3;color:#067647;border:1px solid #abefc6}.warning-box{background:#fff6e6;color:#b54708;border:1px solid #fedf89}.warning-box p{color:#b54708;margin-top:6px}.empty{background:#f8fafc;color:#667085}.blockers{background:#fff4ed;color:#b54708;padding:10px;border-radius:8px}.blockers p{color:#b54708;margin-top:5px}.check{display:flex;gap:8px;align-items:flex-start;color:#475467;font-size:13px}.check input{min-height:auto;margin-top:2px}.export-candidate{align-items:flex-start}.export-candidate .btn{white-space:nowrap}.consumer-evidence{display:grid;gap:10px;margin-top:12px;padding:12px;border:1px solid #dfe7f5;background:#fff;border-radius:10px}.consumer-evidence p{font-size:12px}.evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}.evidence-card{padding:8px 9px;border-radius:8px;background:#f8fafc;border:1px solid #eaecf0}.evidence-card strong,.evidence-card span{display:block}.evidence-card strong{font-size:15px;color:#344054}.evidence-card span{margin-top:2px;font-size:11px;color:#667085}.evidence-card.unsettled{background:#fff8eb;border-color:#fedf89}.evidence-card.unsettled strong,.evidence-card.unsettled span{color:#b54708}.digest-line,.job-consumer-summary{display:flex;flex-wrap:wrap;gap:8px 14px;color:#667085;font-size:11px}.safety-note{padding:8px 10px;border-radius:8px;background:#f2f4f7;color:#475467;font-size:12px;line-height:1.5}.evidence-ready{display:grid;gap:4px}.evidence-ready span{font-size:12px}.rebind-box{display:grid;gap:9px;color:#344054}.rebind-box>.empty{margin-top:0}code{word-break:break-all;font-size:11px;color:#475467}.reconcile-panel{overflow:auto}table{width:100%;border-collapse:collapse;min-width:800px}th,td{padding:11px 10px;border-bottom:1px solid #eaecf0;text-align:left;font-size:13px}th{color:#667085;font-weight:600}.ok-text{color:#067647}.bad-text{color:#b42318}.toast{position:fixed;right:28px;bottom:28px;max-width:420px;padding:12px 16px;border-radius:10px;color:#fff;background:#067647;box-shadow:0 8px 24px rgba(16,24,40,.2);z-index:40}.toast.error{background:#b42318}.toast.warning{background:#b54708}@media(max-width:1200px){.module-grid{grid-template-columns:1fr 1fr}.evidence-grid{grid-template-columns:1fr 1fr}}@media(max-width:860px){.module-grid,.flow-grid,.evidence-grid{grid-template-columns:1fr}.hero,.workspace-head{display:grid}.source-row{align-items:flex-start;display:grid}.source-action{flex-wrap:wrap}}
</style>