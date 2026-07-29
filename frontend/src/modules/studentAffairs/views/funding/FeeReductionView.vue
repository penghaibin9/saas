<template>
  <AppPageShell title="减免与临时补助" subtitle="学费减免 / 临时困难补助：申请 → 审核 → 发放。金额按角色脱敏。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="减免与临时补助">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">减免与临补台账</span>
          <h3 class="sa-summary-strip__title">先审核申请依据，再处理已批准待发记录</h3>
          <p class="sa-summary-strip__text">待审核、已批准待发和已发放分开统计。老师可先处理黄色待办，再核对发放结果。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.reduction.manage')" code="studentAffairs.funding.reduction.manage" @click="formVisible=true">代录申请</AppPermissionButton>
        </div>
      </div>

      <div class="sa-workflow-strip" aria-label="减免与临补办理流程">
        <div class="sa-workflow-step" data-step="1">登记学生、类型、金额和申请理由</div>
        <div class="sa-workflow-step" data-step="2">审核申请依据，批准或驳回</div>
        <div class="sa-workflow-step" data-step="3">对已批准记录登记发放结果</div>
      </div>

      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
      </div>

      <AppSectionCard v-if="formVisible" class="sa-inline-workspace" title="申请减免/临补">
        <p class="fr-intro">请依据正式申请材料代录。理由应说明学生实际困难和申请依据，便于后续审核留痕。</p>
        <div class="fr-grid">
          <div class="fr-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="fr-field"><span>类型</span><AppSelect v-model="form.itemType" :options="ITEM_TYPE_OPTIONS" placeholder="" /></label>
          <label class="fr-field"><span>金额</span><AppNumberInput v-model="form.amount" :min="0" /></label>
          <label class="fr-field fr-wide"><span>申请理由 *（≥5字）</span><AppTextInput v-model="form.reason" placeholder="说明困难情况、申请依据和用途" /></label>
        </div>
        <p v-if="form.error" class="fr-error">{{ form.error }}</p>
        <div class="fr-actions"><button type="button" class="fr-btn" @click="formVisible=false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.funding.reduction.manage')" code="studentAffairs.funding.reduction.manage" :loading="acting==='sub'" @click="submit">提交</AppPermissionButton></div>
      </AppSectionCard>

      <AppSectionCard title="减免/临补台账">
        <p class="fr-section-hint">按类型筛选后处理当前记录。批准是主要操作，驳回和发放保持原有状态规则。</p>
        <div class="fr-filters">
          <button v-for="f in typeFilters" :key="f.key" type="button" class="fr-chip" :class="{ 'is-on': activeType===f.key }" @click="setType(f.key)">{{ f.label }}</button>
        </div>
        <DataTable v-if="items.length" :columns="feeColumns" :rows="items" row-key="feeId">
          <template #cell-student="{ row }"><span class="mp-cell-main">{{ row.realName || ('#'+row.studentId) }}</span></template>
          <template #cell-itemType="{ row }">{{ row.itemType==='REDUCTION'?'学费减免':'临时补助' }}</template>
          <template #cell-amount="{ row }">{{ amountText(row.amount) }}</template>
          <template #cell-reason="{ row }"><span class="fr-reason">{{ row.reason }}</span></template>
          <template #cell-status="{ row }"><StatusTag :type="frType(row.status)" :label="row.statusLabel || row.status" dot /></template>
          <template #cell-actions="{ row }">
            <div class="fr-ops">
              <template v-if="row.status==='SUBMITTED'">
                <AppPermissionButton :allowed="canBtn('studentAffairs.funding.reduction.manage')" code="studentAffairs.funding.reduction.manage" size="sm" :loading="acting===row.feeId" @click="review(row,'APPROVE')">批准</AppPermissionButton>
                <AppPermissionButton :allowed="canBtn('studentAffairs.funding.reduction.manage')" code="studentAffairs.funding.reduction.manage" size="sm" variant="secondary" danger @click="review(row,'REJECT')">驳回</AppPermissionButton>
              </template>
              <AppPermissionButton :allowed="canBtn('studentAffairs.funding.reduction.manage')" v-else-if="row.status==='APPROVED'" code="studentAffairs.funding.reduction.manage" size="sm" :loading="acting===row.feeId" @click="issue(row)">发放</AppPermissionButton>
              <span v-else class="fr-muted">—</span>
            </div>
          </template>
        </DataTable>
        <p v-else class="sa-empty">当前筛选下暂无减免或临时补助记录。</p>
      </AppSectionCard>
    </AppGlobalState>

    <!-- 驳回意见：后端 review_reduction 卡 ≥5 字。挂 sa.aid.reject——该词库是「家庭经济困难认定驳回」
         口径（收入证明不全/材料不符/不符合本批次条件/已享受同类资助），学费减免同为资助事项、
         同一套判据，可直接复用；未新增或改动任何词条。 -->
    <AppConfirmDialog
      v-model:visible="rejDlg.visible" title="驳回减免/补助申请" type="danger" confirm-text="确认驳回"
      require-reason :reason-min-length="5" reason-label="驳回意见（≥5 字）"
      phrase-scene-key="sa.aid.reject" :submitting="acting === rejDlg.feeId" @confirm="submitReject"
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


const TYPE_FILTERS = [{ key: '', label: '全部' }, { key: 'REDUCTION', label: '学费减免' }, { key: 'TEMP_AID', label: '临时补助' }]
const ITEM_TYPE_OPTIONS = [{ value: 'REDUCTION', label: '学费减免' }, { value: 'TEMP_AID', label: '临时补助' }]
const FEE_COLUMNS = [
  { key: 'student', title: '学生' },
  { key: 'itemType', title: '类型' },
  { key: 'amount', title: '金额' },
  { key: 'reason', title: '理由' },
  { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', align: 'right', width: '160px' }
]

export default {
  name: 'FeeReductionView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput, DataTable
  },
  data() {
    return {
      feeColumns: FEE_COLUMNS,
      loading: true, acting: '', errorMessage: '', items: [], statusCounts: null, activeType: '', typeFilters: TYPE_FILTERS,
      formVisible: false, form: this.blank(), rejDlg: { visible: false, feeId: '' }
    }
  },
  computed: {
    ITEM_TYPE_OPTIONS: () => ITEM_TYPE_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.statusCounts === null ? '—' : (this.statusCounts[k] || 0)
      return [
        { key: 'p', label: '待审核', value: s('SUBMITTED'), accent: 'warning' },
        { key: 'a', label: '已批准待发', value: s('APPROVED'), accent: 'processing' },
        { key: 'i', label: '已发放', value: s('ISSUED'), accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    blank() { return { studentId: '', itemType: 'REDUCTION', amount: null, reason: '', error: '' } },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getFeeReductions({ itemType: this.activeType })
      if (res.code === 0 && res.data) {
        this.items = res.data.items || []
        this.statusCounts = res.data.statusCounts || null
      }
      else this.errorMessage = res.message || '加载失败'
      this.loading = false
    },
    setType(k) { if (this.activeType === k) return; this.activeType = k; this.load() },
    async submit() {
      const f = this.form
      const reason = (f.reason || '').trim()
      if (!f.studentId || !reason || reason.length < 5) { f.error = '学生与理由(≥5字)必填'; return }
      f.error = ''; this.acting = 'sub'
      const res = await studentAffairsApi.submitFeeReduction({ studentId: Number(f.studentId), itemType: f.itemType, amount: f.amount != null ? String(f.amount) : undefined, reason })
      this.acting = ''
      if (res.code === 0) { toast.success('已提交'); this.formVisible = false; this.form = this.blank(); this.load() } else f.error = res.message || '提交失败'
    },
    async review(x, action) {
      if (action === 'REJECT') { this.rejDlg = { visible: true, feeId: x.feeId, version: x.version }; return }
      this.acting = x.feeId
      const res = await studentAffairsApi.reviewFeeReduction(x.feeId, action, '', x.version)
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    async submitReject({ reason }) {
      const d = this.rejDlg
      this.acting = d.feeId
      const res = await studentAffairsApi.reviewFeeReduction(d.feeId, 'REJECT', reason.trim(), d.version)
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    async issue(x) {
      this.acting = x.feeId
      const res = await studentAffairsApi.issueFeeReduction(x.feeId, x.version)
      this.acting = ''
      if (res.code === 0) { toast.success('已发放'); this.load() } else toast.error(res.message || '发放失败')
    },
    amountText(a) { return (a == null || a === '') ? '—' : (typeof a === 'number' ? ('¥' + a) : a) },
    frType(s) { return ({ SUBMITTED: 'warning', APPROVED: 'processing', REJECTED: 'default', ISSUED: 'success' })[s] || 'default' }
  }
}
</script>

<style scoped>
.fr-intro,
.fr-section-hint { margin: 0 0 var(--space-3); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.fr-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.fr-wide { grid-column: span 3; }
.fr-field { display: flex; flex-direction: column; gap: 5px; min-width: 0; font-size: var(--font-size-sm); }
.fr-field > span { color: var(--text-secondary); font-weight: var(--font-weight-medium); }
.fr-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.fr-actions { display: flex; gap: var(--space-3); justify-content: flex-end; padding-top: var(--space-3); border-top: 1px solid var(--border-light); }
.fr-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.fr-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fr-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.fr-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 260px; white-space: normal; line-height: 1.55; }
.fr-ops { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.fr-muted { color: var(--text-tertiary); }
@media (max-width: 960px) { .fr-grid { grid-template-columns: 1fr; } .fr-wide { grid-column: span 1; } }
@import '@/styles/module-page.css';
</style>
