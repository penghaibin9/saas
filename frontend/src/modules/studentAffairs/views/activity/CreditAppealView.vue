<template>
  <AppPageShell
    title="第二课堂积分申诉"
    subtitle="学生对二课学时缺记/记错提出申诉；通过会写入正式积分台账，必须核对主张类型、数值和理由。"
    role-name="团委 / 学工处"
    data-scope-name="按数据范围（辅导员限本班）"
    watermark-purpose="第二课堂积分申诉"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载申诉..." @retry="load" @back="$router.push('/admin/student-affairs/activity')">
      <div class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">积分申诉复核</span>
          <h3 class="sa-summary-strip__title">先核对申诉类型、主张数值和事实理由，再决定是否写入正式台账</h3>
          <p class="sa-summary-strip__text">“缺记”补录缺失值，“记错”用于更正已有记录。待审核记录是本页首要处理事项。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.activity.create')" code="studentAffairs.activity.create" :loading="saving" @click="openForm">代录申诉</AppPermissionButton>
        </div>
      </div>

      <div class="sa-workflow-strip" aria-label="积分申诉流程">
        <div class="sa-workflow-step" data-step="1">核对学生、申诉类型和积分项目</div>
        <div class="sa-workflow-step" data-step="2">核验主张数值与事实理由</div>
        <div class="sa-workflow-step" data-step="3">通过后写入正式积分台账</div>
      </div>

      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics"><AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" /></div>
      </div>

      <AppSectionCard v-if="formVisible" class="sa-inline-workspace" title="提交积分申诉">
        <p class="ca-form-hint">代录前请确认学生已有线下申请材料。主张数值和理由会直接进入后续复核依据。</p>
        <div class="ca-grid">
          <div class="ca-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="ca-field"><span>类型</span><AppSelect v-model="form.appealType" :options="APPEAL_TYPE_OPTIONS" placeholder="" /></label>
          <label class="ca-field"><span>积分类型</span><AppSelect v-model="form.claimCreditType" :options="CTYPE_OPTIONS" placeholder="" /></label>
          <label class="ca-field"><span>主张数值 *（0.01-9999.99）</span><AppNumberInput v-model="form.claimValue" :min="0.01" :max="9999.99" :step="0.01" /></label>
          <label class="ca-field ca-field--wide"><span>申诉理由 *（5-1000字）</span><AppTextInput v-model="form.reason" :maxlength="1000" /></label>
        </div>
        <p class="ca-help">“记错”应关联已有积分记录；“缺记”可不指定活动，但必须填写明确主张数值和事实理由。</p>
        <p v-if="form.error" class="ca-error">{{ form.error }}</p>
        <div class="ca-actions"><button type="button" class="ca-btn" :disabled="saving" @click="closeForm">取消</button><AppPermissionButton :allowed="canBtn('studentAffairs.activity.create')" code="studentAffairs.activity.create" :loading="saving" :disabled="!formValid" @click="save">提交</AppPermissionButton></div>
      </AppSectionCard>

      <AppSectionCard title="申诉记录">
        <p class="ca-section-hint">优先处理“待审核”。通过会影响正式积分台账，驳回必须填写可回看的复核意见。</p>
        <div class="ca-filters"><button v-for="f in statusFilters" :key="f.key" type="button" class="ca-chip" :class="{ 'is-on': activeStatus === f.key }" @click="setStatus(f.key)">{{ f.label }}</button></div>
        <DataTable v-if="items.length || pagination.total > 0" :columns="appealColumns" :rows="items" row-key="appealId" :pagination="pagination" @page-change="onPageChange">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('学生#' + row.studentId) }}</span><div class="mp-cell-sub">{{ row.studentNo || '' }}</div></template>
          <template #cell-appealType="{ row }">{{ row.appealType === 'MISSING' ? '缺记' : '记错' }}</template>
          <template #cell-claim="{ row }"><strong>{{ ctypeLabel(row.claimCreditType) }} {{ row.claimValue != null ? row.claimValue : '—' }}</strong></template>
          <template #cell-reason="{ row }"><span class="ca-reason">{{ row.reason }}</span></template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="row.statusLabel || row.status" dot /><em v-if="row.reviewOpinion" class="ca-opinion">{{ row.reviewOpinion }}</em></template>
          <template #cell-actions="{ row }">
            <div class="ca-ops" v-if="canReview(row)">
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.confirm')" code="studentAffairs.activity.confirm" size="sm" :loading="acting===row.appealId" :disabled="!hasVersion(row)" @click="openApprove(row)">核对后通过</AppPermissionButton>
              <AppPermissionButton :allowed="canBtn('studentAffairs.activity.confirm')" code="studentAffairs.activity.confirm" size="sm" variant="secondary" danger :loading="acting===row.appealId" :disabled="!hasVersion(row)" @click="openReject(row)">驳回</AppPermissionButton>
            </div>
            <span v-else class="ca-dash">—</span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前筛选下暂无积分申诉记录。</p>
      </AppSectionCard>
    </AppGlobalState>

    <AppConfirmDialog
      v-model:visible="approveDlg.visible"
      title="确认通过并写入积分台账"
      :message="approveDlg.message"
      confirm-text="确认通过"
      :submitting="acting === approveDlg.appealId"
      @confirm="submitApprove"
    />
    <AppConfirmDialog
      v-model:visible="rejDlg.visible"
      title="驳回积分申诉"
      type="danger"
      confirm-text="确认驳回"
      require-reason
      :reason-min-length="5"
      reason-label="驳回意见（5-1000字）"
      :submitting="acting === rejDlg.appealId"
      @confirm="submitReject"
    />
  </AppPageShell>
</template>

<script>
import {
  AppConfirmDialog, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
  AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextInput
} from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const APPEAL_COLUMNS = [
  { key: 'student', title: '学生' }, { key: 'appealType', title: '类型' },
  { key: 'claim', title: '主张' }, { key: 'reason', title: '理由' },
  { key: 'status', title: '状态' }, { key: 'actions', title: '操作', align: 'right', width: '190px' }
]
const CTYPE = { SECOND_CLASS: '二课学时', MORAL: '德育积分', VOLUNTEER_HOUR: '志愿时长' }
const CTYPE_OPTIONS = Object.entries(CTYPE).map(([value, label]) => ({ value, label }))
const APPEAL_TYPE_OPTIONS = [{ value: 'MISSING', label: '缺记' }, { value: 'WRONG', label: '记错' }]
const STATUS_FILTERS = [{ key: '', label: '全部' }, { key: 'SUBMITTED', label: '待审核' }, { key: 'APPROVED', label: '已通过' }, { key: 'REJECTED', label: '已驳回' }]

export default {
  name: 'CreditAppealView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      appealColumns: APPEAL_COLUMNS,
      loading: true, saving: false, acting: '', errorMessage: '', items: [], statusCounts: null,
      pagination: { page: 1, pageSize: 50, total: 0 },
      activeStatus: '', statusFilters: STATUS_FILTERS, formVisible: false, form: this.blankForm(),
      approveDlg: { visible: false, appealId: '', version: null, message: '' },
      rejDlg: { visible: false, appealId: '', version: null }
    }
  },
  computed: {
    CTYPE_OPTIONS: () => CTYPE_OPTIONS,
    APPEAL_TYPE_OPTIONS: () => APPEAL_TYPE_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.statusCount(k)
      return [
        { key: 'p', label: '待审核', value: s('SUBMITTED'), accent: 'warning' },
        { key: 'a', label: '已通过补记', value: s('APPROVED'), accent: 'success' },
        { key: 'r', label: '已驳回', value: s('REJECTED'), accent: 'default' }
      ]
    },
    claimError() {
      const value = Number(this.form.claimValue)
      if (!Number.isFinite(value) || value <= 0) return '主张数值必须大于0'
      if (value > 9999.99) return '主张数值不得超过9999.99'
      if (Math.round(value * 100) !== value * 100) return '主张数值最多保留2位小数'
      return ''
    },
    formValid() {
      const reason = (this.form.reason || '').trim()
      return !!this.form.studentId && !this.claimError && reason.length >= 5 && reason.length <= 1000
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    hasVersion(row) { return row && row.version !== undefined && row.version !== null && row.version !== '' },
    canReview(row) { return row.status === 'SUBMITTED' && (!Array.isArray(row.allowedActions) || row.allowedActions.some((x) => ['APPROVE', 'REJECT'].includes(x))) },
    statusCount(key) { if (this.statusCounts === null) return '—'; return this.statusCounts[key] != null ? this.statusCounts[key] : 0 },
    blankForm() { return { studentId: '', appealType: 'MISSING', claimCreditType: 'SECOND_CLASS', claimValue: '', reason: '', error: '' } },
    async load() {
      this.loading = true; this.errorMessage = ''; this.statusCounts = null
      try {
        const res = await studentAffairsApi.getCreditAppeals({ status: this.activeStatus, page: this.pagination.page, pageSize: this.pagination.pageSize })
        if (res.code !== 0 || !res.data) throw new Error(res.message || '申诉加载失败')
        this.items = res.data.items || []
        this.pagination.total = res.data.total != null ? res.data.total : this.items.length
        this.statusCounts = res.data.statusCounts || null
      } catch (e) { this.errorMessage = e.message || '申诉加载失败' }
      finally { this.loading = false }
    },
    setStatus(k) { if (this.activeStatus === k) return; this.activeStatus = k; this.pagination.page = 1; this.load() },
    onPageChange(page) { this.pagination.page = page; this.load() },
    openForm() { this.form = this.blankForm(); this.formVisible = true },
    closeForm() { if (!this.saving) this.formVisible = false },
    async save() {
      const m = this.form; const reason = (m.reason || '').trim()
      if (!m.studentId) { m.error = '请选择学生'; return }
      if (this.claimError) { m.error = this.claimError; return }
      if (reason.length < 5 || reason.length > 1000) { m.error = '申诉理由需5-1000字'; return }
      m.error = ''; this.saving = true
      try {
        const res = await studentAffairsApi.submitCreditAppeal({
          studentId: Number(m.studentId), appealType: m.appealType, claimCreditType: m.claimCreditType,
          claimValue: Number(m.claimValue), reason
        })
        if (res.code !== 0) throw new Error(res.message || '提交失败')
        toast.success('申诉已提交'); this.formVisible = false; this.pagination.page = 1; await this.load()
      } catch (e) { m.error = e.message || '提交失败' }
      finally { this.saving = false }
    },
    openApprove(row) {
      if (!this.canReview(row) || !this.hasVersion(row)) return
      this.approveDlg = {
        visible: true, appealId: row.appealId, version: row.version,
        message: `${row.realName || '该学生'}\n${this.ctypeLabel(row.claimCreditType)} ${row.claimValue}\n理由：${row.reason || '—'}\n\n通过后会写入正式积分台账，请确认事实与数值无误。`
      }
    },
    openReject(row) { if (this.canReview(row) && this.hasVersion(row)) this.rejDlg = { visible: true, appealId: row.appealId, version: row.version } },
    async submitApprove() {
      const d = this.approveDlg; this.acting = d.appealId
      try {
        const res = await studentAffairsApi.reviewCreditAppeal(d.appealId, 'APPROVE', '核验申请材料与积分主张后通过', d.version)
        if (res.code !== 0) throw new Error(res.message || '审核失败')
        d.visible = false; toast.success('已通过并写入积分台账'); await this.load()
      } catch (e) { toast.error(e.message || '审核失败') }
      finally { this.acting = '' }
    },
    async submitReject({ reason }) {
      const text = (reason || '').trim()
      if (text.length < 5 || text.length > 1000) { toast.error('驳回意见需5-1000字'); return }
      const d = this.rejDlg; this.acting = d.appealId
      try {
        const res = await studentAffairsApi.reviewCreditAppeal(d.appealId, 'REJECT', text, d.version)
        if (res.code !== 0) throw new Error(res.message || '审核失败')
        d.visible = false; toast.success('已驳回'); await this.load()
      } catch (e) { toast.error(e.message || '审核失败') }
      finally { this.acting = '' }
    },
    ctypeLabel(t) { return CTYPE[t] || t },
    statusType(s) { return ({ SUBMITTED: 'warning', APPROVED: 'success', REJECTED: 'default' })[s] || 'default' }
  }
}
</script>

<style scoped>
.ca-form-hint,
.ca-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.ca-grid { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:var(--space-3);margin-bottom:var(--space-3) }
.ca-field { display:flex;flex-direction:column;gap:5px;min-width:0;font-size:var(--font-size-sm) }
.ca-field > span { color: var(--text-secondary); font-weight: var(--font-weight-medium); }
.ca-field--wide { grid-column:span 4 }
.ca-error { color:var(--danger-500,#dc2626);font-size:var(--font-size-sm) }
.ca-help { color:var(--text-tertiary);font-size:12px;margin:0 0 var(--space-3);line-height:1.6 }
.ca-actions { display:flex;gap:var(--space-3);justify-content:flex-end;padding-top:var(--space-3);border-top:1px solid var(--border-light) }
.ca-btn { border:1px solid var(--border-light);background:var(--bg-card);border-radius:var(--radius-md);padding:7px 16px;cursor:pointer }
.ca-chip { border:1px solid var(--border-light);background:var(--bg-card);border-radius:var(--radius-full);padding:4px 14px;font-size:var(--font-size-sm);cursor:pointer }
.ca-chip.is-on { background:var(--color-primary);color:#fff;border-color:var(--color-primary) }
.ca-reason { color:var(--text-secondary);font-size:var(--font-size-sm);max-width:260px;white-space:normal;line-height:1.5 }
.ca-opinion { display:block;color:var(--text-tertiary);font-size:var(--font-size-xs);font-style:normal;margin-top:3px }
.ca-ops { display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end }
.ca-dash { color:var(--text-tertiary) }
@media(max-width:1100px){.ca-grid{grid-template-columns:1fr 1fr}.ca-field--wide{grid-column:span 2}}
@media(max-width:720px){.ca-grid{grid-template-columns:1fr}.ca-field--wide{grid-column:span 1}.ca-actions{justify-content:stretch}.ca-actions>*{flex:1}}
</style>
