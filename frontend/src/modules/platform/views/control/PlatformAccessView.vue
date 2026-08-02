<template>
  <ModulePageShell title="平台访问治理" subtitle="职责分离、临时提升、受控学校协助与访问复核" role-name="平台负责人 / 安全审计" data-scope-name="平台控制面">
    <div class="access-page">
      <section class="hero">
        <div>
          <h3>平台人员不再共用超级管理员</h3>
          <p>商务、交付、客户成功、运维和安全审计按职责分开；学校数据协助必须绑定工单或事件、租户、具体范围和自动到期时间。</p>
        </div>
        <AppButton @click="load">刷新</AppButton>
      </section>

      <section class="metrics">
        <article><strong>{{ assignments.length }}</strong><span>职责分配</span></article>
        <article><strong>{{ activeElevations }}</strong><span>有效临时提升</span></article>
        <article><strong>{{ activeSessions }}</strong><span>有效受控协助</span></article>
        <article><strong>{{ reviews.length }}</strong><span>待复核记录</span></article>
      </section>

      <section class="forms">
        <form class="panel" @submit.prevent="saveAssignment">
          <h3>分配平台职责</h3>
          <label>平台用户 ID<input v-model.trim="assignmentForm.userId" required placeholder="平台用户 ID" /></label>
          <label>职责
            <select v-model="assignmentForm.dutyCode">
              <option v-for="item in dutyOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label>说明<input v-model.trim="assignmentForm.reason" required minlength="5" placeholder="分配原因" /></label>
          <AppButton variant="primary" :loading="saving === 'assignment'" type="submit">保存职责</AppButton>
        </form>

        <form class="panel" @submit.prevent="createElevation">
          <h3>临时权限提升</h3>
          <label>平台用户 ID<input v-model.trim="elevationForm.userId" required /></label>
          <label>具体能力<input v-model.trim="elevationForm.capabilities" required placeholder="如 operations.manage, incident.manage" /></label>
          <label>有效分钟<input v-model.number="elevationForm.durationMinutes" type="number" min="1" max="240" required /></label>
          <label>批准人<input v-model.trim="elevationForm.approvedBy" required /></label>
          <label>原因<input v-model.trim="elevationForm.reason" required minlength="5" /></label>
          <AppButton variant="primary" :loading="saving === 'elevation'" type="submit">创建临时提升</AppButton>
        </form>

        <form class="panel" @submit.prevent="createSupportSession">
          <h3>受控学校协助</h3>
          <label>学校租户 ID<input v-model.trim="supportForm.tenantId" required /></label>
          <label>工单或事件 ID<input v-model.trim="supportForm.ticketId" required placeholder="TICKET-001" /></label>
          <label>批准范围<input v-model.trim="supportForm.scopes" required placeholder="如 file.metadata, tenant.health" /></label>
          <label>协助原因<input v-model.trim="supportForm.reason" required minlength="5" placeholder="说明本次协助目的" /></label>
          <label>有效分钟<input v-model.number="supportForm.durationMinutes" type="number" min="1" max="120" required /></label>
          <AppButton variant="primary" :loading="saving === 'support'" type="submit">创建协助会话</AppButton>
        </form>
      </section>

      <section class="panel table-panel">
        <h3>职责分配</h3>
        <table>
          <thead><tr><th>平台用户</th><th>职责</th><th>状态</th><th>到期</th><th>版本</th></tr></thead>
          <tbody>
            <tr v-for="item in assignments" :key="item.id"><td>{{ item.userId }}</td><td>{{ item.dutyCode }}</td><td>{{ item.status || 'ACTIVE' }}</td><td>{{ item.expiresAt || '长期' }}</td><td>{{ item.version }}</td></tr>
            <tr v-if="!assignments.length"><td colspan="5">暂无职责分配</td></tr>
          </tbody>
        </table>
      </section>

      <section class="panel table-panel">
        <h3>临时提升与受控协助</h3>
        <table>
          <thead><tr><th>类型</th><th>操作人</th><th>学校 / 能力</th><th>工单 / 原因</th><th>到期</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="item in elevations" :key="`e-${item.id}`"><td>临时提升</td><td>{{ item.userId }}</td><td>{{ (item.capabilities || []).join(' / ') }}</td><td>{{ item.reason }}</td><td>{{ item.expiresAt }}</td><td>{{ item.status }}</td></tr>
            <tr v-for="item in sessions" :key="`s-${item.id}`"><td>受控协助</td><td>{{ item.operatorUserId }}</td><td>{{ item.tenantId }} · {{ (item.scopes || []).join(' / ') }}</td><td>{{ item.ticketId || item.incidentId }}</td><td>{{ item.expiresAt }}</td><td>{{ item.status }}</td></tr>
            <tr v-if="!elevations.length && !sessions.length"><td colspan="6">暂无临时提升或受控协助会话</td></tr>
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
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const splitValues = (value) => String(value || '').split(',').map((item) => item.trim()).filter(Boolean)

export default {
  name: 'PlatformAccessView',
  components: { AppButton, ModulePageShell },
  data() {
    return {
      assignments: [], elevations: [], sessions: [], reviews: [], error: '', saving: '',
      dutyOptions: [
        { value: 'PLATFORM_OWNER', label: '平台负责人' },
        { value: 'PLATFORM_COMMERCIAL', label: '商务' },
        { value: 'PLATFORM_DELIVERY', label: '交付' },
        { value: 'PLATFORM_CUSTOMER_SUCCESS', label: '客户成功' },
        { value: 'PLATFORM_OPERATIONS', label: '运维' },
        { value: 'PLATFORM_SECURITY_AUDITOR', label: '安全审计' }
      ],
      assignmentForm: { userId: '', dutyCode: 'PLATFORM_COMMERCIAL', reason: '' },
      elevationForm: { userId: '', capabilities: '', durationMinutes: 60, approvedBy: '', reason: '' },
      supportForm: { tenantId: '', ticketId: '', scopes: '', reason: '', durationMinutes: 60 }
    }
  },
  computed: {
    activeElevations() { return this.elevations.filter((item) => item.status === 'ACTIVE').length },
    activeSessions() { return this.sessions.filter((item) => item.status === 'ACTIVE').length }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.error = ''
      const [a, e, s, r] = await Promise.all([
        platformControlApi.listAccessAssignments(),
        platformControlApi.listElevationSessions(),
        platformControlApi.listSupportSessions(),
        platformControlApi.listAccessReviews()
      ])
      const failed = [a, e, s, r].find((item) => item.code !== 0)
      if (failed) { this.error = failed.message; return }
      this.assignments = a.data.items || []
      this.elevations = e.data.items || []
      this.sessions = s.data.items || []
      this.reviews = r.data.items || []
    },
    async saveAssignment() {
      this.saving = 'assignment'
      const res = await platformControlApi.saveAccessAssignment({ ...this.assignmentForm, status: 'ACTIVE' })
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      toast.success('平台职责已保存')
      this.assignmentForm = { userId: '', dutyCode: 'PLATFORM_COMMERCIAL', reason: '' }
      await this.load()
    },
    async createElevation() {
      this.saving = 'elevation'
      const res = await platformControlApi.createElevationSession({
        ...this.elevationForm,
        capabilities: splitValues(this.elevationForm.capabilities)
      })
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      toast.success('临时提升已创建并将在到期后自动失效')
      this.elevationForm = { userId: '', capabilities: '', durationMinutes: 60, approvedBy: '', reason: '' }
      await this.load()
    },
    async createSupportSession() {
      this.saving = 'support'
      const res = await platformControlApi.createSupportSession({
        tenantId: Number(this.supportForm.tenantId),
        ticketId: this.supportForm.ticketId,
        scopes: splitValues(this.supportForm.scopes),
        reason: this.supportForm.reason,
        durationMinutes: this.supportForm.durationMinutes
      })
      this.saving = ''
      if (res.code !== 0) return toast.error(res.message)
      toast.success('受控协助会话已创建')
      this.supportForm = { tenantId: '', ticketId: '', scopes: '', reason: '', durationMinutes: 60 }
      await this.load()
    }
  }
}
</script>

<style scoped>
.access-page { display: grid; gap: 16px; }
.hero, .panel, .metrics article { background: var(--surface, #fff); border: 1px solid var(--card-b, #e5e6eb); border-radius: 12px; padding: 18px; }
.hero { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.hero h3, .panel h3 { margin: 0 0 6px; }
.hero p { margin: 0; color: var(--text-secondary, #646a73); max-width: 900px; }
.metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.metrics article { display: grid; gap: 4px; }
.metrics strong { font-size: 26px; }
.forms { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
.panel { display: grid; gap: 12px; }
label { display: grid; gap: 5px; color: var(--text-secondary, #646a73); font-size: 13px; }
input, select { height: 36px; border: 1px solid var(--card-b, #e5e6eb); border-radius: 8px; padding: 0 10px; background: #fff; }
.table-panel { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; min-width: 720px; }
th, td { padding: 10px; border-bottom: 1px solid var(--card-b, #e5e6eb); text-align: left; vertical-align: top; }
.error { padding: 12px; border-radius: 8px; background: #fff2f0; color: #b42318; }
</style>
