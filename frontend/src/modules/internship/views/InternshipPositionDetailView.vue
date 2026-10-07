<template>
  <ModulePageShell class="pd-page" :title="detail?.title || '岗位详情'" :subtitle="detail?.companyName || ''">
    <template #actions>
      <button class="mp-btn" type="button" @click="goBack">{{ backLocation ? '返回上一页' : '返回岗位库' }}</button>
      <RouterLink v-if="canEdit" class="mp-btn" :to="editLink">编辑完整资料</RouterLink>
    </template>
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else-if="detail">
      <div class="pd-summary">
        <AppStatusTag :type="detail.statusTone" dot>{{ detail.statusLabel }}</AppStatusTag>
        <span>已分配 {{ detail.allocatedCount }} / {{ detail.headcount }} 人</span>
        <span>{{ detail.batchName || '未关联有效批次' }}</span>
        <RouterLink :to="sectionLink('publish')" class="mp-link">{{ detail.compliance?.passed ? '发布条件已具备' : '查看发布检查' }}</RouterLink>
      </div>
      <p v-if="detail.riskFlag" class="pd-notice pd-danger" role="status">风险岗位 · {{ detail.riskNote }}</p>
      <nav class="pd-tabs" aria-label="岗位详情分区">
        <RouterLink v-for="item in tabs" :key="item.key" :to="sectionLink(item.key)" :aria-current="tab === item.key ? 'page' : undefined" :class="{ 'is-active': tab === item.key }">{{ item.label }}</RouterLink>
      </nav>
      <section v-if="tab === 'basic'" class="mp-card">
        <div class="mp-card__head"><h2 class="mp-card__title">岗位资料</h2></div>
        <div class="mp-card__body">
          <h3 class="pd-label">工作内容</h3><p class="pd-content">{{ detail.workContent || '尚未填写工作内容' }}</p>
          <AppDescriptionList :items="basicFields" />
        </div>
      </section>
      <section v-else-if="tab === 'rights'" class="mp-card">
        <div class="mp-card__head"><h2 class="mp-card__title">权益条件</h2><RouterLink v-if="canEdit" class="mp-link" :to="editLink">补充或修改条件</RouterLink></div>
        <div class="mp-card__body">
          <div v-for="group in rightsGroups" :key="group.title" class="pd-group"><h3 class="pd-label">{{ group.title }}</h3><AppDescriptionList :items="group.items" /></div>
        </div>
      </section>
      <div v-else-if="tab === 'publish'" class="pd-stack">
        <section class="mp-card">
          <div class="mp-card__head"><h2 class="mp-card__title">发布检查</h2><button class="mp-link" :disabled="submitting" @click="load">重新检查</button></div>
          <div class="mp-card__body">
            <p class="pd-result">{{ detail.compliance?.passed ? '当前岗位资料通过发布检查' : '完成以下核对后再上架' }}</p>
            <p v-if="!detail.compliance" class="pd-muted">暂未取得检查结果，请重新检查。</p>
            <ul v-if="issues.length" class="pd-issues">
              <li v-for="(issue, index) in issues" :key="index"><AppStatusTag :type="issue.tone">{{ issue.kind }}</AppStatusTag><div><strong>{{ issue.title }}</strong><p>{{ issue.reason }}</p></div></li>
            </ul>
            <div class="pd-actions"><RouterLink v-if="canEdit" class="mp-link" :to="editLink">编辑岗位资料</RouterLink><RouterLink v-if="canViewCompany" class="mp-link" :to="companyLink('inspections')">核对企业准入</RouterLink></div>
            <p class="pd-notice">{{ detail.campaignId ? '本岗位关联招聘季。学生可选范围还取决于招聘季开放时间、企业参与状态、学生资格及岗位余量。' : '本岗位尚未关联招聘季，上架后不会自动进入学生选岗目录。' }}</p>
          </div>
        </section>
        <section class="mp-card">
          <div class="mp-card__head"><h2 class="mp-card__title">岗位状态</h2><AppStatusTag :type="detail.statusTone">{{ detail.statusLabel }}</AppStatusTag></div>
          <div class="mp-card__body">
            <p class="pd-muted">{{ stateHint }}</p>
            <div class="pd-actions">
              <button v-for="action in statusActions" :key="action.key" class="mp-btn" :class="{ 'mp-btn--primary': ['SUBMIT', 'PUBLISH'].includes(action.key), 'pd-danger': action.key === 'ARCHIVE' }" :disabled="submitting || (action.key === 'PUBLISH' && !detail.compliance?.passed)" @click="askStatus(action.key)">{{ action.label }}</button>
              <button v-if="canManage && detail.status !== 'ARCHIVED'" class="mp-btn" :disabled="submitting" @click="askRisk(!detail.riskFlag)">{{ detail.riskFlag ? '解除风险' : '标记风险' }}</button>
            </div>
          </div>
        </section>
      </div>
      <section v-else-if="tab === 'company'" class="mp-card">
        <div class="mp-card__head"><h2 class="mp-card__title">企业与导师</h2><RouterLink v-if="canViewCompany" class="mp-link" :to="companyLink('basic')">查看企业资料</RouterLink></div>
        <div class="mp-card__body"><AppDescriptionList :items="companyFields" /></div>
      </section>
      <section v-else class="mp-card">
        <div class="mp-card__head"><h2 class="mp-card__title">操作记录</h2></div>
        <div class="mp-card__body"><AppAuditTrail :records="auditRecords" empty-text="暂无操作记录" /></div>
      </section>
    </template>
    <AppConfirmDialog v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message" :type="confirm.type" :confirm-text="confirm.title" :require-reason="confirm.requireReason" :reason-min-length="confirm.action === 'RETURN' ? 1 : 5" :reason-label="confirm.action === 'RETURN' ? '补正意见（企业可见）' : '风险说明'" :submitting="submitting" :confirm-disabled="!!actionError" @confirm="onConfirm">
      <p v-if="actionError" class="pd-notice pd-danger" role="alert">{{ actionError }}。请关闭弹窗，重新检查岗位后再办理。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppStatusTag, AppAuditTrail, AppDescriptionList } from '@/components/common'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { positionApi } from '@/modules/internship/api/position.api'
import { canCode } from '@/modules/internship/composables/permission'
import { REMUNERATION_TYPE_LABEL, REMUNERATION_CYCLE_LABEL } from '@/modules/internship/constants/position.constants'
import { toast } from '@/utils/toast'

const FIELD_NAMES = { workContent: '工作内容', dailyHours: '每日工时', weeklyHours: '每周工时', nightShift: '是否夜班', overtimeAllowed: '是否允许加班', restDaysPerWeek: '每周休息天数', remunerationType: '报酬类型', accommodationProvided: '是否提供住宿', mealProvided: '是否提供餐食', hazardousFlag: '是否危险岗位' }
const ACTION_LABELS = { CREATE: '创建岗位', UPDATE: '编辑岗位', STATUS_SUBMIT: '提交审核', STATUS_RETURN: '退回补正', STATUS_PUBLISH: '上架岗位', STATUS_OFFLINE: '下架岗位', STATUS_SUSPEND: '暂停岗位', STATUS_ARCHIVE: '归档岗位', RISK_ON: '标记风险', RISK_OFF: '解除风险' }
const yesNo = (value) => value === true ? '是' : value === false ? '否' : '待补充'
const quantity = (value, unit) => value == null ? '待补充' : String(value) + unit

export default {
  name: 'InternshipPositionDetailView',
  components: { ModulePageShell, LoadingState, ErrorState, AppStatusTag, AppAuditTrail, AppDescriptionList, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', detail: null, submitting: false, loadSequence: 0, actionError: '',
      tabs: [{ key: 'basic', label: '岗位资料' }, { key: 'rights', label: '权益条件' }, { key: 'publish', label: '发布管理' }, { key: 'company', label: '企业与导师' }, { key: 'audit', label: '操作记录' }],
      confirm: { visible: false, title: '', message: '', type: 'primary', requireReason: false } }
  },
  computed: {
    canManage() { return Array.isArray(this.ctx.permissionPatterns) && canCode(this.ctx, 'internship.position.manage') },
    canPublish() { return Array.isArray(this.ctx.permissionPatterns) && canCode(this.ctx, 'internship.position.publish') },
    canViewCompany() { return canCode(this.ctx, 'internship.enterprise.view') },
    canEdit() { return this.canManage && !this.loading && !this.error && this.detail && this.detail.status !== 'ARCHIVED' },
    tab() { return this.tabs.some((item) => item.key === this.$route.query.section) ? this.$route.query.section : 'basic' },
    listQuery() { const query = { ...this.$route.query }; delete query.section; delete query.returnTo; return query },
    backLocation() {
      const ref = this.$route.query.returnTo
      if (typeof ref !== 'string' || !/^\/admin\/internship\/(?:students|enterprises)(?:\/\d+)?(?:\?|$)/.test(ref)) return ''
      const batchId = this.detail?.batchId || this.$route.query.batchId
      const refBatchId = new URL(ref, 'https://local.invalid').searchParams.get('batchId')
      return !batchId || !refBatchId || refBatchId === String(batchId) ? ref : ''
    },
    editLink() { return { path: '/admin/internship/positions/' + this.detail.id + '/edit', query: { ...this.listQuery, section: this.tab } } },
    basicFields() {
      const d = this.detail
      return [{ label: '工作地址', value: d.workAddress || d.workLocation }, { label: '岗位类别', value: d.category },
        { label: '专业要求', value: d.majorRequirement || '不限' }, { label: '年级要求', value: d.gradeRequirement || '不限' },
        { label: '岗位容量', value: quantity(d.headcount, ' 人') }, { label: '剩余名额', value: quantity(d.remaining, ' 人') },
        { label: '薪资说明', value: d.salaryRange }, { label: '补贴说明', value: d.subsidy }, { label: '备注', value: d.remark }]
    },
    rightsGroups() {
      const d = this.detail
      return [{ title: '工时与休息', items: [
        { label: '每日工时', value: quantity(d.dailyHours, ' 小时') }, { label: '每周工时', value: quantity(d.weeklyHours, ' 小时') },
        { label: '班次', value: d.shiftType === 'DAY' ? '日班' : d.shiftType }, { label: '每周休息', value: quantity(d.restDaysPerWeek, ' 天') },
        { label: '是否夜班', value: yesNo(d.nightShift) }, { label: '允许加班', value: yesNo(d.overtimeAllowed) }] },
      { title: '报酬与食宿', items: [
        { label: '报酬类型', value: REMUNERATION_TYPE_LABEL[d.remunerationType] || '待补充' }, { label: '报酬金额', value: quantity(d.remunerationAmount, ' 元') },
        { label: '发放周期', value: REMUNERATION_CYCLE_LABEL[d.remunerationCycle] || '待补充' },
        { label: '提供住宿', value: yesNo(d.accommodationProvided) }, { label: '提供餐食', value: yesNo(d.mealProvided) }] },
      { title: '安全与设备', items: [
        { label: '危险岗位', value: yesNo(d.hazardousFlag) }, { label: '特殊设备', value: d.specialEquipment },
        { label: '禁止安排说明', value: d.prohibitedReason }] }]
    },
    companyFields() {
      const d = this.detail
      return [{ label: '所属企业', value: d.companyName }, { label: '合作状态', value: d.company?.coopStatusLabel },
        { label: '企业导师', value: d.mentorName || '未指定' }, { label: '实习批次', value: d.batchName || '未关联有效批次' },
        { label: '岗位来源', value: d.sourceType === 'ENTERPRISE' ? '企业报送' : '学校建档' },
        { label: '招聘季关联', value: d.campaignId ? '已关联招聘季' : '未关联招聘季' }]
    },
    issues() {
      const c = this.detail?.compliance || {}
      return [['blockers', '需处理', 'danger'], ['unknowns', '待补充', 'warning'], ['warnings', '提醒', 'warning']].flatMap(([key, kind, tone]) =>
        (c[key] || []).map((issue) => ({ ...issue, kind, tone, title: FIELD_NAMES[issue.field] || issue.title || issue.label,
          reason: issue.code === 'REQUIRED_UNKNOWN' && FIELD_NAMES[issue.field] ? '尚未填写，请核对后补充。' : issue.reason })))
    },
    statusActions() { return ['SUBMIT', 'PUBLISH', 'RETURN', 'OFFLINE', 'SUSPEND', 'ARCHIVE'].filter(this.allowedStatus).map((key) => ({ key, label: ACTION_LABELS['STATUS_' + key] })) },
    stateHint() {
      if (this.detail.status === 'ARCHIVED') return '岗位已归档，保留资料与操作记录。'
      if (!this.canPublish && !this.canManage) return '当前身份可查看岗位资料；状态办理由有权限的负责人完成。'
      return { DRAFT: '资料核对后提交审核，再由有发布权限的负责人上架。', PENDING: '核对发布检查后上架；资料需完善时，填写意见并退回补正。', PUBLISHED: '岗位已上架；变更权益条件后将重新检查。', RISK: '解除风险后回到已下架，需要重新检查并上架。' }[this.detail.status] || '上架前重新核对岗位资料、企业准入与剩余名额。'
    },
    auditRecords() { return (this.detail?.auditTrail || []).map((a, i) => ({ id: i, action: a.action, actionLabel: ACTION_LABELS[a.action], actor: a.operator, at: a.occurredAt, reason: a.detail?.reason || a.detail?.note || '' })) }
  },
  watch: { '$route.params.id'() { this.load() } },
  created() { this.load() },
  beforeUnmount() { this.loadSequence++ },
  methods: {
    sectionLink(section) { return { path: this.$route.path, query: { ...this.listQuery, section } } },
    companyLink(section) { return { path: '/admin/internship/enterprises/' + this.detail.companyId, query: { batchId: this.detail.batchId || this.listQuery.batchId, section, returnTo: this.$route.fullPath } } },
    goBack() {
      if (this.backLocation) return this.$router.push(this.backLocation)
      this.$router.push({ path: '/admin/internship/positions', query: this.listQuery })
    },
    async load() {
      const sequence = ++this.loadSequence, id = this.$route.params.id
      this.loading = true; this.error = ''; this.detail = null; this.submitting = false; this.confirm.visible = false; this.actionError = ''
      const res = await positionApi.getPositionDetail(id)
      if (sequence !== this.loadSequence || id !== this.$route.params.id) return
      if (res.code === 0) this.detail = res.data
      else this.error = res.message || '岗位详情暂时无法读取'
      this.loading = false
    },
    allowedStatus(action) {
      if (!this.canPublish || !this.detail || this.loading || this.error) return false
      const states = { SUBMIT: ['DRAFT'], RETURN: ['PENDING'], PUBLISH: ['PENDING', 'OFFLINE', 'SUSPENDED'], OFFLINE: ['PUBLISHED', 'SUSPENDED', 'FULL'], SUSPEND: ['PUBLISHED'] }
      return action === 'ARCHIVE' ? this.detail.status !== 'ARCHIVED' : (states[action] || []).includes(this.detail.status)
    },
    askStatus(action) {
      if (this.submitting || !this.allowedStatus(action) || (action === 'PUBLISH' && !this.detail.compliance?.passed)) return
      const title = ACTION_LABELS['STATUS_' + action]
      this.actionError = ''
      this.confirm = { visible: true, title, message: action === 'RETURN' ? '退回后企业可修改原岗位并重新提交。请填写具体补正事项，意见将对该企业可见。' : '确认对「' + this.detail.title + '」执行' + title + '？', type: action === 'ARCHIVE' ? 'danger' : 'primary', requireReason: action === 'RETURN', action, id: this.detail.id, version: this.detail.version }
    },
    askRisk(on) {
      if (!this.canManage || this.submitting || !this.detail || this.detail.status === 'ARCHIVED') return
      this.actionError = ''
      this.confirm = { visible: true, title: on ? '标记风险' : '解除风险', message: on ? '标记后岗位停止供给，请填写风险说明。' : '解除后回到已下架，需要重新检查并上架。', type: on ? 'danger' : 'primary', requireReason: on, action: on ? 'RISK_ON' : 'RISK_OFF', id: this.detail.id, version: this.detail.version }
    },
    async onConfirm({ reason = '' } = {}) {
      const { action, id, version } = this.confirm, sequence = this.loadSequence
      if (!this.confirm.visible || this.submitting || this.actionError || !this.detail || id !== this.detail.id) return
      const risk = action === 'RISK_ON' || action === 'RISK_OFF'
      if (risk ? !this.canManage : !this.allowedStatus(action)) return
      if (action === 'RETURN' && (!reason.trim() || reason.trim().length > 1000)) { toast.error('请填写 1 至 1000 字的补正意见'); return }
      this.submitting = true
      try {
        const res = risk ? await positionApi.markPositionRisk(id, { on: action === 'RISK_ON', note: reason, expectedVersion: version })
          : await positionApi.setPositionStatus(id, { action, reason, expectedVersion: version })
        if (sequence !== this.loadSequence || id !== this.$route.params.id) return
        if (res.code === 0) { toast.success('岗位已更新'); await this.load() } else this.actionError = res.message || '办理失败'
      } finally { if (sequence === this.loadSequence) this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.pd-page { gap: 12px; }
.pd-summary, .pd-actions { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.pd-summary { color: var(--t2, #475569); font-size: 13px; }
.pd-tabs { display: flex; gap: 20px; overflow-x: auto; border-bottom: 1px solid var(--line, #dce3ed); }
.pd-tabs a { padding: 10px 2px; color: var(--t2, #475569); white-space: nowrap; text-decoration: none; border-bottom: 2px solid transparent; font-size: 14px; }
.pd-tabs a.is-active { color: var(--pri, #2563eb); border-color: currentColor; font-weight: 600; }
.pd-stack { display: grid; gap: 16px; }
@media (min-width: 1050px) { .pd-stack { grid-template-columns: minmax(0, 1.5fr) minmax(280px, 1fr); align-items: start; } }
.pd-label { margin: 0 0 10px; font-size: 13px; color: var(--t2, #475569); font-weight: 600; }
.pd-content { white-space: pre-wrap; overflow-wrap: anywhere; margin: 0 0 22px; line-height: 1.7; }
.pd-group + .pd-group { border-top: 1px solid var(--line, #dce3ed); margin-top: 18px; padding-top: 18px; }
.pd-result { margin: 0 0 14px; font-weight: 600; }
.pd-muted { color: var(--t2, #475569); font-size: 13px; line-height: 1.7; }
.pd-notice { padding: 12px 14px; margin: 16px 0; background: color-mix(in srgb, var(--pri, #2563eb) 5%, transparent); border-radius: 8px; line-height: 1.6; font-size: 13px; }
.pd-danger { color: var(--danger, #b91c1c); }
.pd-issues { list-style: none; padding: 0; margin: 0 0 16px; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 24px; }
.pd-issues li { display: flex; align-items: start; gap: 10px; font-size: 13px; }
.pd-issues p { color: var(--t2, #475569); margin: 4px 0 0; line-height: 1.5; }
.mp-card__title { margin: 0; }
.mp-btn { display: inline-flex; text-decoration: none; padding: 7px 12px; border: 1px solid var(--line, #dce3ed); border-radius: 7px; background: var(--surface, #fff); font-size: 13px; cursor: pointer; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
button:disabled { opacity: .5; cursor: not-allowed; }
a:focus-visible, button:focus-visible { outline: 2px solid var(--pri, #2563eb); outline-offset: 3px; }
@media (max-width: 760px) { .pd-issues { grid-template-columns: 1fr; } .pd-tabs { gap: 14px; } }
</style>
