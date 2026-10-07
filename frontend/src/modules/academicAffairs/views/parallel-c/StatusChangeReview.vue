<template>
  <section v-if="change" class="sc-review">
    <header><strong>{{ change.realName }} · {{ typeLabel(change.changeType) }}</strong><span>{{ statusLabel(change.status) }}</span></header>
    <div class="sc-evidence">
      <article><h3>来源对象与身份</h3><p>{{ change.realName || '姓名待核对' }}</p><p>{{ studentStatus(change.fromStatus) }} → {{ studentStatus(change.toStatus) }}</p></article>
      <article><h3>当前决定版本</h3><p>{{ version === null ? '版本尚未返回，请重新读取' : `决定版本 ${version}` }}</p><p>提交时核对本次确认的版本与当前任务。</p></article>
      <article><h3>申请与材料依据</h3><p>{{ change.reason || '申请原因未返回' }}</p><slot name="materials"><p>进入详情读取正式绑定材料。</p></slot></article>
      <article><h3>{{ canReview ? '当前审批节点' : '审批路径节点' }}</h3><p>{{ nodeLabel(change.currentNode) }}</p><p>{{ canReview ? '当前岗位可发起办理，具体对象范围由服务器核验。' : '当前岗位无可用审核动作。' }}</p></article>
      <article><h3>计划生效与正式结果</h3><p>{{ change.effectiveDate || '未设置计划日期' }}</p><p>{{ effectText }}</p></article>
      <article><h3>证据核对</h3><p>办理前重新读取同一申请；材料清单按详情中最新绑定核对。</p><p>{{ evidenceText }}</p></article>
    </div>
    <p v-if="error" role="alert" class="sc-error">{{ error }}</p>
    <div v-if="receipt" class="sc-receipt" role="status">
      <b>{{ receipt.verified ? '已核对正式办理结果' : '结果待核实' }}</b>
      <p>{{ receipt.label }}</p>
      <button v-if="pending" :disabled="saving || checking" @click="verify">{{ checking ? '正在读取…' : '查询原申请正式结果' }}</button>
    </div>
    <div v-if="canReview && !pending" class="sc-actions">
      <label>审批意见（退回、驳回至少 5 字）<textarea v-model="reason" :disabled="saving" rows="3" maxlength="2000" /></label>
      <div><button :disabled="saving" @click="ask('APPROVE')">通过本节点</button><button :disabled="saving" @click="ask('RETURN')">退回补充</button><button :disabled="saving" @click="ask('REJECT')">驳回申请</button></div>
    </div>
    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" :confirm-text="confirmTitle" :submitting="saving" @confirm="submit" @cancel="cancelConfirm">
      <p v-if="command?.evidence">正式材料回读：{{ materialReceipt(command.evidence) }}。</p>
      <p v-if="command?.reason">本次意见：{{ command.reason }}</p>
    </AppConfirmDialog>
  </section>
</template>

<script>
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { academicAffairsApi as api } from '../../api/academic-affairs.api'
import { statusChangeConvenienceApi } from '../../api/status-change-convenience.api'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import { TYPE_LABEL, STATUS_LABEL, NODE_LABEL } from '../../constants/status-change'
import { ACADEMIC_STUDENT_STATUS_LABELS } from '../../config/academicStudentLabels'
import { gradeError } from './grade-review'
import { decisionVersion, nodePermission, sameDecision, sameDecisionOutcome, matchesDecisionResult } from './status-change-review'

export default {
  name: 'StatusChangeReview',
  components: { AppConfirmDialog },
  props: { change: { type: Object, default: null }, ctx: { type: Object, required: true } },
  emits: ['updated', 'denied', 'busy'],
  data() { return { alive: true, scope: 0, saving: false, checking: false, reason: '', error: '', command: null, pending: null, receipt: null, evidence: null, confirmVisible: false } },
  computed: {
    identity() { const u = currentUserFromToken() || {}; return JSON.stringify([u.tenantId, u.userId, u.activeContextId, u.currentRoleCode, this.ctx.currentRole, this.ctx.dataScope, this.ctx.permissionPatterns]) },
    version() { return decisionVersion(this.change) },
    canReview() { if (!['SUBMITTED', 'IN_REVIEW'].includes(this.change?.status)) return false; const p = nodePermission(this.change); return !!p && matchPermission(this.ctx.permissionPatterns || [], `academicAffairs.statusChange.${p}`) },
    confirmTitle() { return ({ APPROVE: '确认通过本节点', RETURN: '确认退回补充', REJECT: '确认驳回申请' })[this.command?.action] || '确认办理' },
    confirmMessage() { return `${this.command?.row.realName || ''} · ${this.typeLabel(this.command?.row.changeType)}。本节点通过不等于学籍已变更，正式结果以回读为准。` },
    evidenceText() { return this.evidence ? `已读取当前决定版本 ${this.evidence.decisionVersion} 的正式材料：${this.materialReceipt(this.evidence)}。` : '尚未读取正式材料；选择审批动作时将重新读取同一申请与其正式绑定材料。' },
    effectText() { if (this.change?.status === 'APPROVED_PENDING_EFFECTIVE') return '终审已通过，当前学籍尚未改变；到期后仍需核对正式生效结果。'; if (this.change?.status === 'EFFECTIVE') return '本异动已正式生效；当前学籍可进入学生档案核对。'; return '终审可能进入待生效或正式生效，以服务器实际结果为准。' }
  },
  watch: {
    identity() { this.invalidate() },
    'change.changeId'() { this.invalidate() },
    'change.decisionVersion'() { if (!this.pending && !this.saving) this.cancelConfirm() }
  },
  beforeUnmount() { this.alive = false; this.invalidate() },
  methods: {
    typeLabel(v) { return TYPE_LABEL[v] || '异动类型待核对' },
    statusLabel(v) { return STATUS_LABEL[v] || '状态待核对' },
    nodeLabel(v) { return NODE_LABEL[v] || '暂无可办理节点' },
    studentStatus(v) { return ACADEMIC_STUDENT_STATUS_LABELS[v] || '学籍状态待核对' },
    capture() { return { scope: this.scope, identity: this.identity, id: String(this.change?.changeId || '') } },
    current(c) { return this.alive && c.scope === this.scope && c.identity === this.identity && c.id === String(this.change?.changeId || '') },
    cancelConfirm() { if (this.saving) return; this.command = null; this.confirmVisible = false },
    invalidate() { this.scope++; this.reason = ''; this.error = ''; this.command = null; this.pending = null; this.receipt = null; this.evidence = null; this.confirmVisible = false; this.saving = false; this.checking = false; this.$emit('busy', false) },
    fail(err, fallback) { if (/403|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION/.test([err?.code,err?.bizCode].join(' '))) { this.invalidate(); this.$emit('denied'); return }; this.error = gradeError(err, fallback) },
    async read(c) { const res = await api.getStatusChange(c.id); if (res?.code !== 0) throw res; if (String(res.data?.changeId || '') !== c.id) throw { code: 409 }; return res.data },
    materialReceipt(evidence) { const count = Array.isArray(evidence?.items) ? evidence.items.length : 0; return count ? `已绑定 ${count} 份材料` : '未绑定材料（已按正式清单核对）' },
    async readEvidence(c, row) { const res = await statusChangeConvenienceApi.listMaterials(c.id); if (res?.code !== 0) throw res; if (!this.current(c)) return null; return { changeId: c.id, decisionVersion: decisionVersion(row), items: Array.isArray(res.data?.items) ? res.data.items : [] } },
    async ask(action) {
      if (this.saving || this.pending || !this.canReview || !['APPROVE', 'RETURN', 'REJECT'].includes(action)) return
      if (action !== 'APPROVE' && this.reason.trim().length < 5) { this.error = '退回或驳回原因至少 5 字。'; return }
      const c = this.capture()
      if (this.version === null) {
        this.saving = true; this.$emit('busy', true)
        try { const row = await this.read(c); if (this.current(c)) { this.$emit('updated', row); this.error = '已重新读取，请核对申请后重新选择办理动作。' } }
        catch (err) { if (this.current(c)) this.fail(err, '版本读取失败，请重试。') }
        finally { if (this.current(c)) { this.saving = false; this.$emit('busy', false) } }
        return
      }
      const selected = { ...this.change }
      this.checking = true; this.$emit('busy', true); this.error = ''
      try {
        const row = await this.read(c)
        if (!this.current(c)) return
        if (!sameDecision(selected, row)) { this.$emit('updated', row); throw { code: 409 } }
        const evidence = await this.readEvidence(c, row)
        if (!this.current(c) || !evidence) return
        this.evidence = evidence
        this.command = { ...c, row: { ...row }, evidence, action, reason: this.reason.trim() }
        this.confirmVisible = true
      } catch (err) { if (this.current(c)) this.fail(err, '正式材料读取失败，请重试后再办理。') }
      finally { if (this.current(c)) { this.checking = false; this.$emit('busy', false) } }
    },
    async submit() {
      const c = this.command
      if (!c || !this.current(c) || this.saving || this.pending || !this.canReview) return
      this.saving = true; this.$emit('busy', true); this.error = ''
      try {
        const before = await this.read(c)
        if (!this.current(c)) return
        if (!sameDecision(c.row, before)) { this.$emit('updated', before); throw { code: 409 } }
        const evidence = await this.readEvidence(c, before)
        if (!this.current(c) || !evidence) return
        c.evidence = evidence; this.evidence = evidence
        this.pending = c; this.receipt = { verified: false, label: '正在核对本次办理，请勿重复提交。' }
        let res; try { res = await api.reviewStatusChange(c.id, c.action, c.reason, decisionVersion(c.row)) } catch (err) { res = err }
        if (!this.current(c)) return
        if (res?.code !== 0 && /403|404|409|422|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))) { this.pending = null; this.receipt = null; throw res }
        c.ack = res?.code === 0 && matchesDecisionResult(c.row, c.action, res.data) ? { ...res.data } : null
        this.confirmVisible = false; this.command = null
        await this.verify()
      } catch (err) { if (this.current(c)) { this.command = null; this.confirmVisible = false; this.fail(err, '办理前核对未完成，请保留意见并重新核对。') } }
      finally { if (this.current(c)) { this.saving = false; this.$emit('busy', !!this.pending) } }
    },
    async verify() {
      const c = this.pending
      if (!c || !this.current(c) || this.checking) return
      this.checking = true
      try {
        const row = await this.read(c)
        if (!this.current(c)) return
        this.$emit('updated', row)
        if (!c.ack || !sameDecisionOutcome(c.ack, row) || !matchesDecisionResult(c.row, c.action, row)) {
          this.receipt = { verified: false, label: `当前正式状态：${this.statusLabel(row.status)}。尚不能确认本次操作回执，请勿重复提交。` }; return
        }
        this.receipt = { verified: true, label: `${this.statusLabel(row.status)}；${row.status === 'APPROVED_PENDING_EFFECTIVE' ? '当前学籍尚未改变。' : '以正式申请记录为准。'}` }
        this.pending = null; this.reason = ''; this.error = ''; this.$emit('busy', false)
      } catch (err) { if (this.current(c)) this.fail(err, '结果待核实，请稍后查询原申请。') }
      finally { if (this.current(c)) this.checking = false }
    }
  }
}
</script>

<style scoped>
.sc-review{display:grid;gap:16px}.sc-review header{display:flex;justify-content:space-between;gap:16px;padding:18px;background:var(--bg-white,#fff);border:1px solid var(--border-200,#e1e7ef);border-left:4px solid var(--primary-500,#3564b4);border-radius:10px}.sc-evidence{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.sc-evidence article{padding:16px;border:1px solid var(--border-200,#e1e7ef);border-radius:8px;background:var(--bg-white,#fff)}h3{font-size:14px;margin:0 0 12px}p{font-size:13px;line-height:1.7;margin:6px 0;overflow-wrap:anywhere}.sc-actions{display:grid;gap:12px}.sc-actions label{display:grid;gap:8px;font-size:13px}textarea{padding:10px;border:1px solid var(--border-200,#e1e7ef);border-radius:8px;font:inherit;background:var(--bg-white,#fff);color:inherit}.sc-actions>div{display:flex;gap:12px}button{padding:8px 14px;border:1px solid var(--border-200,#ccd7e7);background:var(--bg-white,#fff);color:var(--primary-600,#285aab);border-radius:7px;cursor:pointer}button:disabled{opacity:.5;cursor:default}.sc-error{color:var(--danger-600,#b42318)}.sc-receipt{padding:14px;background:var(--primary-50,#edf4ff);border-radius:8px}@media(max-width:900px){.sc-evidence{grid-template-columns:1fr}}
</style>
