<template>
  <ModulePageShell
    :title="detail ? detail.warning.code + ' · 预警跟进' : '预警跟进'"
    :subtitle="detail ? detail.warning.name + '（' + detail.warning.className + '）· ' + detail.warning.sourceRule : ''"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.name"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>
    <p v-if="actionNotice" class="awd-notice" role="status">{{ actionNotice }}</p>

    <ErrorState v-if="error" :description="error" @retry="load" @back="$router.back()" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mp-grid-2">
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">预警信息</span>
            <span>
              <RiskTag :level="detail.warning.level" />
              <StatusTag :status="detail.warning.status" :label="statusLabel(detail.warning.status)" dot style="margin-left: var(--space-2)" />
            </span>
          </div>
          <div class="mp-card__body">
            <AppDescriptionList :items="warningDescItems" :columns="2" />
          </div>
        </section>

        <section v-if="detail.student" class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">学生信息</span>
            <button class="mp-link" @click="$router.push('/admin/academic/students/' + detail.student.id)">学业详情 →</button>
          </div>
          <div class="mp-card__body">
            <AppDescriptionList :items="studentDescItems" :columns="2" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">关联学业数据</span></div>
          <div class="mp-card__body">
            <div class="awd-block">
              <div class="awd-block__title">关联成绩</div>
              <ul class="awd-list">
                <li v-for="g in detail.extras.relatedGrades" :key="g">{{ g }}</li>
                <li v-if="!detail.extras.relatedGrades.length" class="mp-note">无关联成绩数据</li>
              </ul>
            </div>
            <div class="awd-block">
              <div class="awd-block__title">学分情况</div>
              <p class="awd-text">{{ detail.extras.relatedCredits || '—' }}</p>
            </div>
            <div class="awd-block">
              <div class="awd-block__title">历史预警</div>
              <ul class="awd-list">
                <li v-for="h in detail.extras.historyWarnings" :key="h">{{ h }}</li>
                <li v-if="!detail.extras.historyWarnings.length" class="mp-note">无历史预警</li>
              </ul>
            </div>
            <div v-if="detail.extras.suggestion" class="awd-suggestion">处理建议：{{ detail.extras.suggestion }}</div>
          </div>
        </section>
      </div>

      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">跟进记录（{{ detail.interventions.length }}）</span>
            <button
              v-if="visible('academic.warning.followup')"
              class="mp-link"
              :class="{ 'is-disabled': !can('academic.warning.followup') || closedOrVoided }"
              :title="reason('academic.warning.followup')"
              @click="openFollowup"
            >
              ＋ 新增跟进
            </button>
          </div>
          <div class="mp-card__body">
            <ul v-if="detail.interventions.length" class="mp-timeline">
              <li v-for="i in detail.interventions" :key="i.id" class="mp-timeline__item is-warning">
                <div class="mp-timeline__title">{{ i.wayLabel }} · {{ i.operator }}</div>
                <div class="mp-timeline__desc">
                  {{ i.content }}
                  <div v-if="i.result" class="mp-cell-sub">结果：{{ interventionResultLabel(i.result) }}</div>
                  <div v-if="i.nextPlan" class="mp-cell-sub">下一步：{{ i.nextPlan }}</div>
                </div>
                <div class="mp-timeline__time">{{ i.time }}</div>
              </li>
            </ul>
            <EmptyState v-else title="暂无跟进记录" description="领取预警后请及时记录谈话、家校联系或帮扶计划" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">操作审计</span></div>
          <div class="mp-card__body">
            <table class="mp-audit">
              <thead><tr><th>操作人</th><th>时间</th><th>动作</th><th>明细</th></tr></thead>
              <tbody>
                <tr v-for="a in detail.auditLogs" :key="a.id">
                  <td class="is-who">{{ a.operator }}<div class="mp-cell-sub">{{ a.roleName }}</div></td>
                  <td>{{ a.time }}</td>
                  <td>{{ auditActionLabel(a) }}</td>
                  <td>{{ a.detail }}</td>
                </tr>
                <tr v-if="!detail.auditLogs.length"><td colspan="4" class="mp-note">暂无审计记录</td></tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>

    <FormDrawer
      v-model:visible="followForm.visible"
      v-model="followForm.model"
      title="新增跟进记录"
      :fields="followFields"
      :submitting="followForm.submitting"
      note="跟进记录将同步进入学生360的学业过程页签，并写入审计日志。"
      submit-text="提交跟进"
      @submit="submitFollowup"
    />

    <AppConfirmDialog
      v-model:visible="closeDialog.visible"
      type="primary"
      title="关闭预警"
      message="确认关闭该预警？关闭后学生学业状态将按剩余预警重新计算，关闭结果会同步学生端。"
      confirm-text="确认关闭"
      require-reason
      phrase-scene-key="aa.warning.close"
      reason-label="关闭说明"
      reason-placeholder="请说明关闭依据（如成绩回升、学分补齐、补考通过），不少于 5 个字"
      :submitting="closeDialog.submitting"
      @confirm="submitClose"
    />

    <AppConfirmDialog
      v-model:visible="escalateDialog.visible"
      type="warning"
      title="升级预警"
      message="确认升级该预警？升级后等级将调整为高风险，并转交学院学业帮扶专班跟进。"
      confirm-text="确认升级"
      require-reason
      phrase-scene-key="aa.warning.escalate"
      reason-label="升级说明"
      reason-placeholder="请说明升级依据（如跟进无效、风险加剧），不少于 5 个字"
      :submitting="escalateDialog.submitting"
      @confirm="submitEscalate"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 学业预警跟进详情（/admin/academic/warnings/:id）。
 * 闭环：预警信息 + 学生信息 + 关联学业数据 → 新增跟进 → 关闭（说明留痕）/ 升级（转专班留痕）→ 操作审计。
 */
import { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDescriptionList } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { FormDrawer } from '@/modules/academicAffairs/components'
import { getWarningDetail, createIntervention, closeWarning, escalateWarning, remindWarnings } from '@/modules/academicAffairs/api/academic.api'
import { toast } from '@/utils/toast'
import { presentAuditRecord, safeLocalizedText } from '@/utils/presentationSafety'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'

export default {
  name: 'AcademicWarningDetailView',
  components: { ModulePageShell, ModuleToolbar, StatusTag, RiskTag, LoadingState, ErrorState, EmptyState, AppDescriptionList, AppConfirmDialog, FormDrawer },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      alive: true, scope: 0, readSeq: 0,
      loading: true,
      error: '',
      detail: null,
      pendingWrite: null,
      actionNotice: '',
      followForm: { visible: false, submitting: false, model: {} },
      closeDialog: { visible: false, submitting: false },
      escalateDialog: { visible: false, submitting: false }
    }
  },
  computed: {
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope])},
    closedOrVoided() {
      return !this.detail || ['CLOSED'].includes(this.detail.warning.status) || this.detail.warning.recordStatus === 'VOIDED'
    },
    toolbarActions() {
      const pa = this.ctx.permissionActions
      return [
        { key: 'remind', permission: 'academic.warning.batchRemind', label: '发送提醒' },
        { key: 'escalate', permission: 'academic.warning.escalate', label: '升级预警', variant: 'warning' },
        { key: 'close', permission: 'academic.warning.close', label: '关闭预警', variant: 'primary' }
      ]
        .filter((a) => pa[a.permission] && pa[a.permission].visible)
        .map((a) => ({
          ...a,
          disabled: !pa[a.permission].allowed || this.closedOrVoided || !!this.pendingWrite,
          disabledReason: !pa[a.permission].allowed ? pa[a.permission].reason : '预警已关闭或已作废'
        }))
    },
    warningDescItems() {
      if (!this.detail) return []
      const w = this.detail.warning
      const items = [
        { label: '预警类型', value: this.typeLabel(w.type) },
        { label: '触发原因', value: w.reason, span: 2 },
        { label: '触发时间', value: w.triggerTime },
        { label: '处理期限', value: w.deadline || '未设置' },
        { label: '跟进人', value: w.owner || '未分配' },
        { label: '已提醒', value: w.remindCount + ' 次' }
      ]
      if (w.closeResult) items.push({ label: '关闭说明', value: w.closeResult, span: 2 })
      if (w.recordStatus === 'VOIDED') items.push({ label: '误报说明', value: w.voidReason, span: 2 })
      return items
    },
    studentDescItems() {
      if (!this.detail || !this.detail.student) return []
      const s = this.detail.student
      return [
        { label: '学生', value: s.name + ' · ' + this.maskNo(s.studentNo) },
        { label: '班级', value: s.className + '（' + s.collegeName + '）' },
        { label: 'GPA / 挂科', value: (Number.isFinite(Number(s.gpa)) ? Number(s.gpa).toFixed(1) : '待核对') + ' / ' + (s.failedCount == null ? '待核对' : s.failedCount + ' 门') },
        { label: '学分进度', value: s.obtainedCredits == null || s.requiredCredits == null ? '待核对' : s.obtainedCredits + ' / ' + s.requiredCredits },
        { label: '辅导员', value: s.counselor },
        { label: '联系电话', value: s.phone || '未登记' }
      ]
    },
    followFields() {
      return [
        {
          key: 'way',
          label: '跟进方式',
          type: 'select',
          required: true,
          options: [
            { value: 'TALK', label: '当面谈话' },
            { value: 'PHONE', label: '电话联系' },
            { value: 'FAMILY', label: '家校联系' },
            { value: 'PLAN', label: '帮扶计划' }
          ]
        },
        { key: 'content', label: '跟进内容', type: 'textarea', required: true, placeholder: '记录本次跟进的过程与学生情况（不少于 5 个字）' },
        { key: 'result', label: '跟进结果', type: 'text' },
        { key: 'nextPlan', label: '下一步计划', type: 'text' }
      ]
    }
  },
  watch:{identity(){this.clearPrivate()},'$route.params.id'(){this.clearPrivate();this.load()}},
  created() {
    this.load()
  },
  beforeUnmount(){this.alive=false;this.clearPrivate()},
  methods: {
    current(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity&&c.id===String(this.$route.params.id)},
    clearPrivate(){this.scope++;this.readSeq++;this.loading=false;this.detail=null;this.error='';this.followForm={visible:false,submitting:false,model:{}};this.closeDialog={visible:false,submitting:false};this.escalateDialog={visible:false,submitting:false};this.pendingWrite=null;this.actionNotice=''},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    fail(err,fallback){if(this.denied(err))this.clearPrivate();return gradeError(err,fallback)},
    auditActionLabel(row) { return presentAuditRecord(row).displayAction },
    interventionResultLabel(value) { return safeLocalizedText({ value, dictionary: { EFFECTIVE: '有效', INEFFECTIVE: '效果不明显', COMPLETED: '已完成', FOLLOWING: '持续跟进', CLOSED: '已关闭' }, unknownLabel: '结果待确认' }) },
    can(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible && pa.allowed)
    },
    visible(key) {
      const pa = this.ctx.permissionActions[key]
      return !!(pa && pa.visible)
    },
    reason(key) {
      const pa = this.ctx.permissionActions[key]
      return pa && !pa.allowed ? pa.reason : ''
    },
    maskNo(v) {
      return v ? v.slice(0, -4) + '**' + v.slice(-2) : ''
    },
    typeLabel(v) {
      return (this.ctx.statusOptions.warningType.find((o) => o.value === v) || {}).label || (v ? '待确认' : '—')
    },
    statusLabel(v) {
      return (this.ctx.statusOptions.warningStatus.find((o) => o.value === v) || {}).label || (v ? '待确认' : '—')
    },
    async load() {
      const c={scope:this.scope,identity:this.identity,id:String(this.$route.params.id),seq:++this.readSeq};this.loading=true;this.error=''
      try{const res=await getWarningDetail(c.id);if(!this.current(c)||c.seq!==this.readSeq)return;if(res.code!==0)throw res;if(String(res.data?.warning?.id)!==c.id||!Array.isArray(res.data?.interventions)||!Array.isArray(res.data?.auditLogs))throw {code:503};this.detail=res.data}
      catch(err){if(this.current(c)&&c.seq===this.readSeq)this.error=this.fail(err,'预警详情读取失败，请重试。')}
      finally{if(this.current(c)&&c.seq===this.readSeq)this.loading=false}
    },
    async writeAction(kind,send,verify,success){
      if(this.pendingWrite||!this.detail)return false
      const id=String(this.detail.warning.id),c={scope:this.scope,identity:this.identity,id};this.pendingWrite={kind,id};this.actionNotice='结果待核实，请勿重复操作。'
      let res;try{res=await send()}catch(err){res=err}
      if(!this.current(c))return false
      if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingWrite=null;this.actionNotice='';toast.error(this.fail(res,'本次操作未受理。'));return false}
      let fresh;try{fresh=await getWarningDetail(id)}catch(err){fresh=err}
      if(!this.current(c))return false
      if(res?.code===0&&fresh?.code===0&&String(fresh.data?.warning?.id)===id&&verify(fresh.data,res)){this.detail=fresh.data;this.pendingWrite=null;this.actionNotice=success;toast.success(success);return true}
      this.actionNotice='结果待核实：已读取当前预警，但不能确认本次操作是否落库。请勿重复操作。';return false
    },
    async onToolbar(key) {
      if (key === 'remind') {
        const before=Number(this.detail.warning.remindCount)
        await this.writeAction('remind',()=>remindWarnings([this.detail.warning.id]),fresh=>Number.isFinite(before)&&Number(fresh.warning.remindCount)>before,'已核对提醒计数更新；通知送达和阅读状态请查看通知台账。')
      } else if (key === 'close') {
        this.closeDialog = { visible: true, submitting: false }
      } else if (key === 'escalate') {
        this.escalateDialog = { visible: true, submitting: false }
      }
    },
    openFollowup() {
      if (!this.can('academic.warning.followup') || this.closedOrVoided) return
      this.followForm = { visible: true, submitting: false, model: { way: 'TALK' } }
    },
    async submitFollowup() {
      if(!this.followForm.model.content||this.followForm.model.content.trim().length<5)return
      const frozen={...this.followForm.model,content:this.followForm.model.content.trim()};let returnedId='';this.followForm.submitting=true
      const ok=await this.writeAction('followup',async()=>{const res=await createIntervention(this.detail.warning.id,frozen);returnedId=String(res?.data?.id||'');return res},fresh=>!!returnedId&&fresh.interventions.some(item=>String(item.id)===returnedId&&item.content===frozen.content),'已核对正式跟进记录。')
      this.followForm.submitting=false;if(ok)this.followForm.visible=false
    },
    async submitClose({ reason }) {
      const frozen=String(reason||'').trim();this.closeDialog.submitting=true
      const ok=await this.writeAction('close',()=>closeWarning(this.detail.warning.id,{result:frozen}),fresh=>fresh.warning.status==='CLOSED'&&String(fresh.warning.closeResult||'')===frozen,'已核对正式关闭状态和关闭说明。')
      this.closeDialog.submitting=false;if(ok)this.closeDialog.visible=false
    },
    async submitEscalate({ reason }) {
      const frozen=String(reason||'').trim();this.escalateDialog.submitting=true
      const ok=await this.writeAction('escalate',()=>escalateWarning(this.detail.warning.id,{reason:frozen}),fresh=>fresh.warning.status==='ESCALATED'&&fresh.warning.level==='HIGH','已核对当前预警为高风险升级状态；升级原因以审计记录为准。')
      this.escalateDialog.submitting=false;if(ok)this.escalateDialog.visible=false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.awd-block {
  margin-bottom: var(--space-3);
}
.awd-notice { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border-radius: var(--radius-base); background: var(--warning-50, #fff7e8); color: var(--warning-700, #9a5200); }
.awd-block__title {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--space-1);
}
.awd-list {
  margin: 0;
  padding-left: var(--space-5);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.awd-list li {
  padding: 2px 0;
}
.awd-text {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.awd-suggestion {
  margin-top: var(--space-3);
  font-size: var(--font-size-sm);
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  line-height: var(--line-height-base);
}
</style>
