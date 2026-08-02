<template>
  <ModulePageShell
    :title="detail ? detail.title : '岗位详情'"
    :subtitle="detail ? detail.companyName : '加载中'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/internship/positions')">← 返回岗位库</button>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else-if="detail">
      <div class="ed-head">
        <AppStatusTag :type="detail.statusTone" dot>{{ detail.statusLabel }}</AppStatusTag>
        <span v-if="detail.riskFlag" class="ed-bl">⚠ 风险岗位 · {{ detail.riskNote }}</span>
        <span class="ed-cap">已分配 {{ detail.allocatedCount }} / 容量 {{ detail.headcount }}</span>
        <div class="ed-head__spacer" />
        <button v-if="detail.status !== 'ARCHIVED'" class="mp-btn" @click="openEdit">编辑</button>
        <button v-if="detail.status === 'DRAFT'" class="mp-btn mp-btn--primary" @click="askStatus('SUBMIT')">提交审核</button>
        <button v-else-if="['PENDING', 'OFFLINE', 'SUSPENDED'].includes(detail.status)" class="mp-btn mp-btn--primary" @click="askStatus('PUBLISH')">上架</button>
        <button v-else-if="detail.status === 'PUBLISHED'" class="mp-btn" @click="askStatus('OFFLINE')">下架</button>
        <button v-if="detail.status === 'PUBLISHED'" class="mp-btn" @click="askStatus('SUSPEND')">暂停</button>
        <button v-if="detail.status !== 'ARCHIVED' && detail.status !== 'RISK'" class="mp-btn mp-btn--danger" @click="askRisk(true)">标记风险</button>
        <button v-if="detail.status === 'RISK'" class="mp-btn" @click="askRisk(false)">解除风险</button>
        <button v-if="detail.status !== 'ARCHIVED'" class="mp-btn" @click="askStatus('ARCHIVE')">归档</button>
      </div>

      <div v-if="detail.company && (detail.company.blacklist || detail.company.coopStatus !== 'ACTIVE')" class="ed-warn">
        所属企业当前为「{{ detail.company.coopStatusLabel }}{{ detail.company.blacklist ? ' · 黑名单' : '' }}」，该岗位不可上架。
      </div>

      <nav class="ed-tabs">
        <button v-for="t in tabs" :key="t.key" class="ed-tabs__item" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">{{ t.label }}</button>
      </nav>

      <section v-show="tab === 'basic'" class="mp-card">
        <div class="mp-card__body">
          <AppDescriptionList :items="basicFields" />
        </div>
      </section>

      <section v-show="tab === 'company'" class="mp-card">
        <div class="mp-card__body">
          <AppDescriptionList :items="companyFields" />
        </div>
      </section>

      <section v-show="tab === 'audit'" class="mp-card">
        <div class="mp-card__body">
          <AppAuditTrail :records="auditRecords" empty-text="暂无操作记录" />
        </div>
      </section>
    </template>

    <AppDrawer v-model:visible="editVisible" title="编辑岗位" mode="modal" size="large">
      <form class="ie-form" @submit.prevent="submitEdit">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">岗位名称 <i>*</i></span><AppTextInput v-model="form.title" /></label>
        <label class="ie-fld"><span class="ie-lbl">专业要求</span><AppTextInput v-model="form.majorRequirement" /></label>
        <label class="ie-fld"><span class="ie-lbl">年级要求</span><AppTextInput v-model="form.gradeRequirement" /></label>
        <label class="ie-fld"><span class="ie-lbl">工作地点</span><AppTextInput v-model="form.workLocation" /></label>
        <label class="ie-fld"><span class="ie-lbl">薪资</span><AppTextInput v-model="form.salaryRange" /></label>
        <label class="ie-fld"><span class="ie-lbl">容量</span><AppNumberInput v-model="form.headcount" :min="1" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><AppTextarea v-model="form.remark" :rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 岗位详情（/admin/internship/positions/:id）：主档 + 企业导师 + 审计 + 状态机 + 编辑（已归档不可编辑）。 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppStatusTag, AppAuditTrail, AppDescriptionList, AppTextInput, AppNumberInput, AppTextarea } from '@/components/common'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { positionApi } from '@/modules/internship/api/position.api'
import { toast } from '@/utils/toast'

export default {
  name: 'InternshipPositionDetailView',
  components: { ModulePageShell, AppStatusTag, AppAuditTrail, AppDescriptionList, AppTextInput, AppNumberInput, AppTextarea, LoadingState, ErrorState, AppDrawer, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false, detail: null, tab: 'basic',
      tabs: [{ key: 'basic', label: '主档' }, { key: 'company', label: '企业与导师' }, { key: 'audit', label: '审计记录' }],
      editVisible: false, form: {}, formError: '',
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null }
    }
  },
  computed: {
    basicFields() {
      const d = this.detail
      return [
        { label: '岗位类别', value: d.category }, { label: '专业要求', value: d.majorRequirement || '不限' },
        { label: '年级要求', value: d.gradeRequirement || '不限' }, { label: '工作地点', value: d.workLocation },
        { label: '薪资', value: d.salaryRange }, { label: '补贴', value: d.subsidy },
        { label: '容量', value: String(d.headcount) }, { label: '已分配', value: String(d.allocatedCount) },
        { label: '备注', value: d.remark }
      ]
    },
    companyFields() {
      const d = this.detail
      return [
        { label: '所属企业', value: d.companyName },
        { label: '企业合作状态', value: d.company ? d.company.coopStatusLabel : '' },
        { label: '企业导师', value: d.mentorName || '未指定' },
        { label: '实习批次', value: d.batchId || '未关联批次' }
      ]
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((a, i) => ({
        id: i,
        action: a.action,
        actor: a.operator,
        at: a.occurredAt
      }))
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const res = await positionApi.getPositionDetail(this.$route.params.id)
      if (res.code === 0) this.detail = res.data; else this.error = res.message
      this.loading = false
    },
    openEdit() {
      const d = this.detail
      this.form = { title: d.title, majorRequirement: d.majorRequirement, gradeRequirement: d.gradeRequirement, workLocation: d.workLocation, salaryRange: d.salaryRange, headcount: d.headcount, remark: d.remark }
      this.formError = ''
      this.editVisible = true
    },
    async submitEdit() {
      if (!this.form.title) { this.formError = '岗位名称必填'; return }
      this.submitting = true
      try {
        const res = await positionApi.updatePosition(this.detail.id, this.form)
        if (res.code === 0) { toast.success('已保存'); this.editVisible = false; this.load() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    askStatus(action) {
      const map = { SUBMIT: { t: '提交审核', c: '确认提交', type: 'primary' }, PUBLISH: { t: '上架岗位', c: '确认上架', type: 'primary' }, OFFLINE: { t: '下架岗位', c: '确认下架', type: 'warning' }, SUSPEND: { t: '暂停岗位', c: '确认暂停', type: 'warning' }, ARCHIVE: { t: '归档岗位', c: '确认归档', type: 'danger' } }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对本岗位执行「${m.t}」？`, type: m.type, confirmText: m.c, requireReason: false, action: 'STATUS_' + action }
    },
    askRisk(on) {
      this.confirm = { visible: true, title: on ? '标记风险岗位' : '解除风险', message: on ? '确认标记为风险岗位？' : '确认解除风险标记？（回到已下架）', type: on ? 'danger' : 'primary', confirmText: on ? '确认标记' : '确认解除', requireReason: on, reasonLabel: '风险说明', action: on ? 'RISK_ON' : 'RISK_OFF' }
    },
    async onConfirm({ reason } = {}) {
      const { action } = this.confirm
      this.submitting = true
      try {
        let res
        if (action.startsWith('STATUS_')) res = await positionApi.setPositionStatus(this.detail.id, { action: action.slice(7), reason: reason || '' })
        else if (action === 'RISK_ON') res = await positionApi.markPositionRisk(this.detail.id, { on: true, note: reason || '' })
        else if (action === 'RISK_OFF') res = await positionApi.markPositionRisk(this.detail.id, { on: false })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ed-head { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ed-head__spacer { flex: 1; }
.ed-bl { font-size: 12px; color: var(--danger, #dc2626); }
.ed-cap { font-size: 12px; color: var(--t2, #475569); }
.ed-warn { padding: 8px 12px; margin-bottom: var(--space-3); border: 1px solid var(--warning, #f59e0b); background: color-mix(in srgb, var(--warning, #f59e0b) 8%, transparent); border-radius: 8px; font-size: 12px; color: var(--warning, #b45309); }
.ed-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.ed-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.ed-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.mp-btn { padding: 7px 14px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn--danger { color: var(--danger, #dc2626); border-color: var(--danger, #dc2626); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); }
</style>
