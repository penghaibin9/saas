<template>
  <ModulePageShell title="平台访问治理" subtitle="职责分离、MFA 临时提升、真实工单受控协助与访问复核" role-name="平台负责人 / 安全审计" data-scope-name="平台控制面">
    <div class="access-page">
      <section class="hero">
        <div>
          <h3>平台人员不再共用超级管理员</h3>
          <p>职责、临时提升、受控协助和访问复核统一走后端 Authority；受控协助只能读取会话批准的学校上下文与审计摘要。</p>
        </div>
        <AppButton @click="load">刷新</AppButton>
      </section>

      <section class="metrics">
        <article><strong>{{ assignments.length }}</strong><span>职责分配</span></article>
        <article><strong>{{ activeElevations }}</strong><span>有效临时提升</span></article>
        <article><strong>{{ activeSessions }}</strong><span>有效受控协助</span></article>
        <article><strong>{{ openReviews }}</strong><span>进行中访问复核</span></article>
      </section>

      <section class="forms">
        <form class="panel" @submit.prevent="saveAssignment">
          <h3>分配平台职责</h3>
          <label>平台用户 ID<input v-model.trim="assignmentForm.userId" required /></label>
          <label>职责
            <select v-model="assignmentForm.dutyCode">
              <option v-for="item in dutyOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label>说明<input v-model.trim="assignmentForm.reason" required minlength="5" /></label>
          <p class="hint">requestId 在失败重试时保持不变；成功后才生成新编号。</p>
          <AppButton variant="primary" :loading="saving === 'assignment'" type="submit">保存职责</AppButton>
        </form>

        <form class="panel" @submit.prevent="createElevation">
          <h3>临时权限提升</h3>
          <label>平台用户 ID<input v-model.trim="elevationForm.userId" required /></label>
          <label>具体能力<input v-model.trim="elevationForm.capabilities" required placeholder="operations.manage, incident.manage" /></label>
          <label>有效分钟<input v-model.number="elevationForm.durationMinutes" type="number" min="1" max="240" required /></label>
          <label>原因<input v-model.trim="elevationForm.reason" required minlength="5" /></label>
          <p class="hint">创建临时提升由生产 runtime 强制 recent-auth + MFA。</p>
          <AppButton variant="primary" :loading="saving === 'elevation'" type="submit">创建临时提升</AppButton>
        </form>

        <form class="panel" @submit.prevent="createSupportSession">
          <h3>受控学校协助</h3>
          <label>学校租户 ID<input v-model.trim="supportForm.tenantId" required inputmode="numeric" /></label>
          <label>SupportTicket 数字 ID<input v-model.trim="supportForm.ticketId" required inputmode="numeric" /></label>
          <label>批准范围<input v-model.trim="supportForm.scopes" required placeholder="tenant.context.read, tenant.audit.read" /></label>
          <p class="hint">本工作区当前只消费 tenant.context.read / tenant.audit.read；审计读取额外要求 MFA step-up。</p>
          <label>协助原因<input v-model.trim="supportForm.reason" required minlength="5" /></label>
          <label>有效分钟<input v-model.number="supportForm.durationMinutes" type="number" min="1" max="120" required /></label>
          <AppButton variant="primary" :loading="saving === 'support'" type="submit">创建协助会话</AppButton>
        </form>

        <form class="panel" @submit.prevent="createReview">
          <h3>发起访问复核</h3>
          <label>复核名称<input v-model.trim="reviewForm.name" required minlength="3" /></label>
          <label>截止日期<input v-model="reviewForm.dueAt" type="date" /></label>
          <p class="hint">创建时冻结当前 ACTIVE 职责、临时提升与受控协助快照；关闭时必须逐项决策。</p>
          <AppButton variant="primary" :loading="saving === 'review'" type="submit">创建复核</AppButton>
        </form>
      </section>

      <section v-if="actionTarget" class="panel action-panel">
        <div>
          <h3>{{ actionTitle }}</h3>
          <p class="hint">目标 {{ actionTarget.id }} · version {{ actionTarget.version }}</p>
        </div>
        <label>原因<input v-model.trim="actionReason" minlength="5" placeholder="至少 5 个字符" /></label>
        <div class="actions">
          <AppButton @click="cancelAction">取消</AppButton>
          <AppButton variant="primary" :loading="saving === 'action'" @click="confirmAction">确认执行</AppButton>
        </div>
      </section>

      <section class="panel table-panel">
        <h3>职责分配</h3>
        <table>
          <thead><tr><th>平台用户</th><th>职责</th><th>状态</th><th>到期</th><th>版本</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in assignments" :key="item.id">
              <td>{{ item.userId }}</td><td>{{ item.dutyCode }}</td><td>{{ item.status || 'ACTIVE' }}</td><td>{{ item.expiresAt || '长期' }}</td><td>{{ item.version }}</td>
              <td><AppButton v-if="isActive(item)" @click="beginAction('assignment', item)">撤销</AppButton></td>
            </tr>
            <tr v-if="!assignments.length"><td colspan="6">暂无职责分配</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel table-panel">
        <h3>临时提升与受控协助</h3>
        <table>
          <thead><tr><th>类型</th><th>操作人</th><th>学校 / 能力</th><th>工单 / 原因</th><th>到期</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in elevations" :key="`e-${item.id}`">
              <td>临时提升</td><td>{{ item.userId }}</td><td>{{ (item.capabilities || []).join(' / ') }}</td><td>{{ item.reason }}</td><td>{{ item.expiresAt }}</td><td>{{ item.status }}</td>
              <td><AppButton v-if="isActive(item)" @click="beginAction('elevation', item)">撤销</AppButton></td>
            </tr>
            <tr v-for="item in sessions" :key="`s-${item.id}`">
              <td>受控协助</td><td>{{ item.operatorUserId }}</td><td>{{ item.tenantId }} · {{ (item.scopes || []).join(' / ') }}</td><td>Ticket #{{ item.ticketId }}</td><td>{{ item.expiresAt }}</td><td>{{ isActive(item) ? item.status : 'EXPIRED' }}</td>
              <td class="access-ops">
                <AppButton v-if="canOpenSupport(item)" variant="primary" @click="openSupportWorkspace(item)">进入协助</AppButton>
                <AppButton v-if="isActive(item)" @click="beginAction('support', item)">终止</AppButton>
              </td>
            </tr>
            <tr v-if="!elevations.length && !sessions.length"><td colspan="7">暂无临时提升或受控协助会话</td></tr>
          </tbody>
        </table>
      </section>

      <section v-if="supportWorkspace.session" class="panel support-workspace">
        <div class="review-head">
          <div>
            <h3>受控协助工作区 · Ticket #{{ supportWorkspace.session.ticketId }}</h3>
            <p class="hint">仅展示本次会话批准的只读数据；会话到期或终止后后端立即拒绝访问。</p>
          </div>
          <AppButton @click="closeSupportWorkspace">关闭工作区</AppButton>
        </div>
        <div v-if="supportWorkspace.loading" class="hint">正在读取学校支持上下文…</div>
        <div v-else-if="supportWorkspace.error" class="error">{{ supportWorkspace.error }}</div>
        <template v-else-if="supportWorkspace.context">
          <div class="support-summary">
            <article><span>学校</span><strong>{{ supportWorkspace.context.tenantName }}</strong><small>{{ supportWorkspace.context.tenantCode }}</small></article>
            <article><span>状态</span><strong>{{ supportWorkspace.context.status }}</strong><small>到期 {{ supportWorkspace.context.expireAt || '—' }}</small></article>
            <article><span>学生</span><strong>{{ supportWorkspace.context.studentCount }}</strong><small>只读统计</small></article>
            <article><span>账号</span><strong>{{ supportWorkspace.context.userCount }}</strong><small>只读统计</small></article>
          </div>

          <div v-if="supportHasScope('tenant.audit.read')" class="support-audit">
            <div class="support-audit__head">
              <div><h3>学校审计摘要</h3><p class="hint">属于更敏感的支持数据，必须使用短时 request-scoped MFA Token；令牌只保存在本组件内存并按服务端 TTL 主动清除。</p></div>
              <div v-if="!supportWorkspace.mfaToken" class="support-mfa">
                <input v-model.trim="supportWorkspace.mfaCode" inputmode="numeric" maxlength="6" placeholder="6 位 MFA 动态码" />
                <AppButton variant="primary" :loading="saving === 'support-mfa'" @click="stepUpAndLoadAudit">MFA 验证并读取</AppButton>
              </div>
              <AppButton v-else @click="loadSupportAudit">刷新审计</AppButton>
            </div>
            <table v-if="supportWorkspace.mfaToken">
              <thead><tr><th>时间</th><th>动作</th><th>对象</th><th>操作人</th><th>结果</th></tr></thead>
              <tbody>
                <tr v-for="row in supportWorkspace.audits" :key="row.auditId || row.id">
                  <td>{{ row.occurredAt || row.time || '—' }}</td><td>{{ row.action }}</td><td>{{ row.resource || row.target || '—' }}</td><td>{{ row.operatorName || row.who || '—' }}</td><td>{{ row.result || '—' }}</td>
                </tr>
                <tr v-if="!supportWorkspace.audits.length"><td colspan="5">当前没有审计记录</td></tr>
              </tbody>
            </table>
          </div>
          <p v-else class="hint">本次会话未批准 tenant.audit.read，因此不展示学校审计摘要。</p>
        </template>
      </section>

      <section class="panel table-panel">
        <h3>访问复核</h3>
        <div v-if="selectedReview" class="review-editor">
          <div class="review-head">
            <div><strong>{{ selectedReview.name || selectedReview.id }}</strong><p class="hint">每个冻结项必须明确 KEEP / REVOKE；缺项或多项后端都会拒绝关闭。</p></div>
            <AppButton @click="selectedReview = null">收起</AppButton>
          </div>
          <div v-for="item in selectedReview.items || []" :key="item.itemKey" class="review-item">
            <code>{{ item.itemKey }}</code>
            <select v-model="reviewDecisions[item.itemKey]"><option value="KEEP">KEEP</option><option value="REVOKE">REVOKE</option></select>
          </div>
          <label>关闭原因<input v-model.trim="reviewCloseReason" minlength="5" placeholder="至少 5 个字符" /></label>
          <AppButton variant="primary" :loading="saving === 'close-review'" @click="closeReview">关闭复核并执行决定</AppButton>
        </div>
        <table>
          <thead><tr><th>复核</th><th>状态</th><th>项目数</th><th>到期</th><th>版本</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="item in reviews" :key="item.id">
              <td>{{ item.name || item.id }}</td><td>{{ item.status }}</td><td>{{ item.items?.length || 0 }}</td><td>{{ item.dueAt || '—' }}</td><td>{{ item.version }}</td>
              <td><AppButton v-if="String(item.status).toUpperCase() === 'OPEN'" @click="editReview(item)">逐项复核</AppButton></td>
            </tr>
            <tr v-if="!reviews.length"><td colspan="6">暂无访问复核记录</td></tr>
          </tbody>
        </table>
      </section>

      <div v-if="error" class="error">{{ error }}</div>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell } from '@/components/business'
import { platformPamApi } from '@/modules/platform/api/platformPam.api'
import { platformSecurityOpsApi } from '@/modules/platform/api/platformSecurityOps.api'
import { toast } from '@/utils/toast'

const splitValues = (value) => String(value || '').split(',').map((item) => item.trim()).filter(Boolean)
const requestId = () => globalThis.crypto?.randomUUID?.() || `pam-${Date.now()}-${Math.random().toString(16).slice(2)}`
const newAssignment = () => ({ requestId: requestId(), userId: '', dutyCode: 'PLATFORM_COMMERCIAL', reason: '' })
const newElevation = () => ({ requestId: requestId(), userId: '', capabilities: '', durationMinutes: 60, reason: '' })
const newSupport = () => ({ requestId: requestId(), tenantId: '', ticketId: '', scopes: 'tenant.context.read, tenant.audit.read', reason: '', durationMinutes: 60 })
const newReview = () => ({ requestId: requestId(), name: '季度平台访问复核', dueAt: '' })
const emptyWorkspace = () => ({ session: null, context: null, audits: [], loading: false, error: '', mfaCode: '', mfaToken: '', mfaExpiresAt: 0 })
const serverUtcEpoch = (value) => {
  if (!value) return null
  const raw = String(value).trim()
  const epoch = Date.parse(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw : `${raw}Z`)
  return Number.isFinite(epoch) ? epoch : null
}

export default {
  name: 'PlatformAccessView',
  components: { AppButton, ModulePageShell },
  data() {
    return {
      assignments: [], elevations: [], sessions: [], reviews: [], error: '', saving: '',
      actionType: '', actionTarget: null, actionReason: '', selectedReview: null, reviewDecisions: {}, reviewCloseReason: '',
      supportWorkspace: emptyWorkspace(), mfaExpiryTimer: null,
      dutyOptions: [
        { value: 'PLATFORM_COMMERCIAL', label: '商务' }, { value: 'PLATFORM_DELIVERY', label: '交付' },
        { value: 'PLATFORM_CUSTOMER_SUCCESS', label: '客户成功' }, { value: 'PLATFORM_OPERATIONS', label: '运维' },
        { value: 'PLATFORM_SECURITY_AUDITOR', label: '安全审计' }
      ],
      assignmentForm: newAssignment(), elevationForm: newElevation(), supportForm: newSupport(), reviewForm: newReview()
    }
  },
  computed: {
    activeElevations() { return this.elevations.filter(this.isActive).length },
    activeSessions() { return this.sessions.filter(this.isActive).length },
    openReviews() { return this.reviews.filter((item) => String(item.status).toUpperCase() === 'OPEN').length },
    actionTitle() { return this.actionType === 'support' ? '终止受控协助' : this.actionType === 'elevation' ? '撤销临时提升' : '撤销平台职责' }
  },
  created() { this.load() },
  beforeUnmount() { this.closeSupportWorkspace() },
  methods: {
    isActive(item) {
      if (String(item?.status || 'ACTIVE').toUpperCase() !== 'ACTIVE') return false
      const expiry = serverUtcEpoch(item?.expiresAt)
      return expiry == null || expiry > Date.now()
    },
    canOpenSupport(item) { return this.isActive(item) && (item.scopes || []).includes('tenant.context.read') },
    supportHasScope(scope) { return (this.supportWorkspace.session?.scopes || []).includes(scope) },
    clearSupportMfaGrant() {
      if (this.mfaExpiryTimer) clearTimeout(this.mfaExpiryTimer)
      this.mfaExpiryTimer = null
      this.supportWorkspace.mfaToken = ''
      this.supportWorkspace.mfaExpiresAt = 0
      this.supportWorkspace.mfaCode = ''
      this.supportWorkspace.audits = []
    },
    async load() {
      this.error = ''
      const [a, e, s, r] = await Promise.all([platformPamApi.listAssignments(), platformPamApi.listElevations(), platformPamApi.listSupportSessions(), platformPamApi.listReviews()])
      const failed = [a, e, s, r].find((item) => item.code !== 0)
      if (failed) { this.error = failed.message; return }
      this.assignments = a.data.items || []; this.elevations = e.data.items || []; this.sessions = s.data.items || []; this.reviews = r.data.items || []
      if (this.supportWorkspace.session) {
        const fresh = this.sessions.find((item) => item.id === this.supportWorkspace.session.id)
        if (!fresh || !this.isActive(fresh)) this.closeSupportWorkspace()
        else this.supportWorkspace.session = fresh
      }
    },
    async saveAssignment() {
      this.saving = 'assignment'; const res = await platformPamApi.saveAssignment({ ...this.assignmentForm, status: 'ACTIVE' }); this.saving = ''
      if (res.code !== 0) return toast.error(res.message); this.assignmentForm = newAssignment(); await this.load(); toast.success('平台职责已保存')
    },
    async createElevation() {
      this.saving = 'elevation'; const res = await platformPamApi.createElevation({ ...this.elevationForm, capabilities: splitValues(this.elevationForm.capabilities) }); this.saving = ''
      if (res.code !== 0) return toast.error(res.message); this.elevationForm = newElevation(); await this.load(); toast.success('临时提升已创建')
    },
    async createSupportSession() {
      const tenantId = Number(this.supportForm.tenantId), ticketId = Number(this.supportForm.ticketId)
      if (!Number.isInteger(tenantId) || tenantId <= 0 || !Number.isInteger(ticketId) || ticketId <= 0) return toast.error('请输入有效租户 ID 与 SupportTicket ID')
      this.saving = 'support'; const res = await platformPamApi.createSupportSession({ ...this.supportForm, tenantId, ticketId, scopes: splitValues(this.supportForm.scopes) }); this.saving = ''
      if (res.code !== 0) return toast.error(res.message); this.supportForm = newSupport(); await this.load(); toast.success('受控协助已创建')
    },
    async openSupportWorkspace(item) {
      this.closeSupportWorkspace()
      this.supportWorkspace = { ...emptyWorkspace(), session: item, loading: true }
      const res = await platformPamApi.getSupportTenantContext(item.tenantId)
      this.supportWorkspace.loading = false
      if (res.code !== 0) { this.supportWorkspace.error = res.message; return }
      this.supportWorkspace.context = res.data
    },
    closeSupportWorkspace() {
      this.clearSupportMfaGrant()
      this.supportWorkspace = emptyWorkspace()
    },
    async stepUpAndLoadAudit() {
      if (!/^\d{6}$/.test(this.supportWorkspace.mfaCode)) return toast.error('请输入 6 位 MFA 动态码')
      const code = this.supportWorkspace.mfaCode
      this.clearSupportMfaGrant()
      this.saving = 'support-mfa'
      try {
        const token = await platformSecurityOpsApi.stepUpMfa(code)
        const ttl = Math.max(1, Number(token.expiresIn || 600))
        this.supportWorkspace.mfaToken = token.accessToken || ''
        this.supportWorkspace.mfaExpiresAt = Date.now() + ttl * 1000
        if (!this.supportWorkspace.mfaToken) return toast.error('MFA step-up 未返回访问令牌')
        this.mfaExpiryTimer = setTimeout(() => this.clearSupportMfaGrant(), ttl * 1000)
        await this.loadSupportAudit()
      } catch (error) {
        this.clearSupportMfaGrant()
        toast.error(error.message || 'MFA 二次认证失败')
      } finally {
        this.saving = ''
      }
    },
    async loadSupportAudit() {
      const session = this.supportWorkspace.session
      if (!session || !this.supportWorkspace.mfaToken) return
      if (this.supportWorkspace.mfaExpiresAt && this.supportWorkspace.mfaExpiresAt <= Date.now()) {
        this.clearSupportMfaGrant()
        return toast.error('MFA 临时授权已过期，请重新验证')
      }
      const res = await platformPamApi.getSupportTenantAudit(session.tenantId, { page: 1, pageSize: 20 }, this.supportWorkspace.mfaToken)
      if (res.code !== 0) {
        if (/AUTH|TOKEN|MFA/i.test(String(res.bizCode || ''))) this.clearSupportMfaGrant()
        return toast.error(res.message)
      }
      this.supportWorkspace.audits = res.data.list || res.data.items || []
    },
    async createReview() {
      this.saving = 'review'; const res = await platformPamApi.createReview({ ...this.reviewForm, dueAt: this.reviewForm.dueAt || undefined }); this.saving = ''
      if (res.code !== 0) return toast.error(res.message); this.reviewForm = newReview(); await this.load(); toast.success('访问复核已创建')
    },
    beginAction(type, item) { this.actionType = type; this.actionTarget = item; this.actionReason = '' },
    cancelAction() { this.actionType = ''; this.actionTarget = null; this.actionReason = '' },
    async confirmAction() {
      if (this.actionReason.length < 5) return toast.error('请填写至少 5 个字符的原因')
      const item = this.actionTarget; this.saving = 'action'
      const res = this.actionType === 'assignment'
        ? await platformPamApi.revokeAssignment(item.id, item.version, this.actionReason)
        : this.actionType === 'elevation'
          ? await platformPamApi.revokeElevation(item.id, item.version, this.actionReason)
          : await platformPamApi.terminateSupportSession(item.id, Number(item.tenantId), item.version, this.actionReason)
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      if (this.actionType === 'support' && this.supportWorkspace.session?.id === item.id) this.closeSupportWorkspace()
      this.cancelAction(); await this.load(); toast.success('访问治理动作已执行')
    },
    editReview(review) {
      this.selectedReview = review; this.reviewCloseReason = ''; this.reviewDecisions = {}
      for (const item of review.items || []) this.reviewDecisions[item.itemKey] = item.decision === 'REVOKE' ? 'REVOKE' : 'KEEP'
    },
    async closeReview() {
      if (!this.selectedReview || this.reviewCloseReason.length < 5) return toast.error('请填写至少 5 个字符的关闭原因')
      const decisions = (this.selectedReview.items || []).map((item) => ({ itemKey: item.itemKey, decision: this.reviewDecisions[item.itemKey] }))
      if (decisions.some((item) => !['KEEP', 'REVOKE'].includes(item.decision))) return toast.error('每个复核项都必须明确 KEEP 或 REVOKE')
      this.saving = 'close-review'
      const res = await platformPamApi.closeReview(this.selectedReview.id, this.selectedReview.version, this.reviewCloseReason, decisions)
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      this.selectedReview = null; await this.load(); toast.success('访问复核已关闭并原子执行决定')
    }
  }
}
</script>

<style scoped>
.access-page { display: grid; gap: 16px; }
.hero, .panel, .metrics article { background: var(--surface,#fff); border: 1px solid var(--card-b,#e5e6eb); border-radius: 12px; padding: 18px; }
.hero, .review-head, .actions, .support-audit__head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.hero h3, .panel h3 { margin: 0 0 6px; }.hero p, .hint { margin: 0; color: var(--text-secondary,#646a73); }.hint { font-size: 12px; line-height: 1.6; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 12px; }.metrics article { display: grid; gap: 4px; }.metrics strong { font-size: 26px; }
.forms { display: grid; grid-template-columns: repeat(auto-fit,minmax(260px,1fr)); gap: 12px; }.panel { display: grid; gap: 12px; }
label { display: grid; gap: 5px; color: var(--text-secondary,#646a73); font-size: 13px; } input, select { height: 36px; border: 1px solid var(--card-b,#e5e6eb); border-radius: 8px; padding: 0 10px; background: #fff; }
.action-panel { border-color: #a9c6ff; }.table-panel { overflow-x: auto; } table { width: 100%; border-collapse: collapse; min-width: 760px; } th, td { padding: 10px; border-bottom: 1px solid var(--card-b,#e5e6eb); text-align: left; vertical-align: top; }
.access-ops { display: flex; gap: 6px; flex-wrap: wrap; }
.review-editor { display: grid; gap: 10px; padding: 14px; border: 1px solid var(--card-b,#e5e6eb); border-radius: 10px; background: #f8fafc; }.review-item { display: grid; grid-template-columns: minmax(0,1fr) 130px; gap: 12px; align-items: center; }.review-item code { overflow-wrap: anywhere; }
.support-workspace { border-color: #86aef7; background: linear-gradient(180deg,rgba(37,99,235,.04),#fff 120px); }
.support-summary { display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 10px; }
.support-summary article { display: grid; gap: 3px; padding: 12px; border: 1px solid var(--card-b,#e5e6eb); border-radius: 10px; background: #fff; }
.support-summary span, .support-summary small { color: var(--text-secondary,#646a73); font-size: 12px; }.support-summary strong { font-size: 18px; }
.support-audit { display: grid; gap: 10px; padding-top: 6px; border-top: 1px solid var(--card-b,#e5e6eb); }.support-mfa { display: flex; gap: 8px; flex-wrap: wrap; }.support-mfa input { width: 150px; letter-spacing: .14em; }
.error { padding: 12px; border-radius: 8px; background: #fff2f0; color: #b42318; }
@media (max-width:760px) { .hero, .review-head, .actions, .support-audit__head { display: grid; }.forms { grid-template-columns: 1fr; }.review-item { grid-template-columns: 1fr; } }
</style>