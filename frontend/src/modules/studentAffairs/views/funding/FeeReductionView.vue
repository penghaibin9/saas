<template>
  <AppPageShell title="减免与临时补助" subtitle="学费减免 / 临时困难补助：申请 → 审核 → 发放。金额按角色脱敏。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="减免与临时补助">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.funding.reduction.manage" @click="formVisible=true">代录申请</AppPermissionButton>
      </div>
      <AppSectionCard v-if="formVisible" title="申请减免/临补">
        <div class="fr-grid">
          <div class="fr-field"><span>学生 *</span><AppStudentPicker v-model="form.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" /></div>
          <label class="fr-field"><span>类型</span><AppSelect v-model="form.itemType" :options="ITEM_TYPE_OPTIONS" placeholder="" /></label>
          <label class="fr-field"><span>金额</span><AppNumberInput v-model="form.amount" :min="0" /></label>
          <label class="fr-field fr-wide"><span>理由 *（≥5字）</span><AppTextInput v-model="form.reason" /></label>
        </div>
        <p v-if="form.error" class="fr-error">{{ form.error }}</p>
        <div class="fr-actions"><button type="button" class="fr-btn" @click="formVisible=false">取消</button>
          <AppPermissionButton code="studentAffairs.funding.reduction.manage" :loading="acting==='sub'" @click="submit">提交</AppPermissionButton></div>
      </AppSectionCard>
      <AppSectionCard title="减免/临补台账">
        <div class="fr-filters">
          <button v-for="f in typeFilters" :key="f.key" type="button" class="fr-chip" :class="{ 'is-on': activeType===f.key }" @click="setType(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>学生</th><th>类型</th><th>金额</th><th>理由</th><th>状态</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="x in items" :key="x.feeId">
              <td><strong>{{ x.realName || ('#'+x.studentId) }}</strong></td>
              <td>{{ x.itemType==='REDUCTION'?'学费减免':'临时补助' }}</td>
              <td>{{ amountText(x.amount) }}</td>
              <td class="fr-reason">{{ x.reason }}</td>
              <td><StatusTag :type="frType(x.status)" :label="x.statusLabel || x.status" dot /></td>
              <td class="fr-ops">
                <template v-if="x.status==='SUBMITTED'">
                  <AppPermissionButton code="studentAffairs.funding.reduction.manage" size="sm" :loading="acting===x.feeId" @click="review(x,'APPROVE')">批准</AppPermissionButton>
                  <AppPermissionButton code="studentAffairs.funding.reduction.manage" size="sm" variant="secondary" danger @click="review(x,'REJECT')">驳回</AppPermissionButton>
                </template>
                <AppPermissionButton v-else-if="x.status==='APPROVED'" code="studentAffairs.funding.reduction.manage" size="sm" :loading="acting===x.feeId" @click="issue(x)">发放</AppPermissionButton>
                <span v-else class="fr-muted">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无记录</td></tr>
          </tbody>
        </table>
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
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const TYPE_FILTERS = [{ key: '', label: '全部' }, { key: 'REDUCTION', label: '学费减免' }, { key: 'TEMP_AID', label: '临时补助' }]
const ITEM_TYPE_OPTIONS = [{ value: 'REDUCTION', label: '学费减免' }, { value: 'TEMP_AID', label: '临时补助' }]

export default {
  name: 'FeeReductionView',
  components: {
    AppConfirmDialog, AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton,
    AppSectionCard, AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppTextInput
  },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', items: [], activeType: '', typeFilters: TYPE_FILTERS,
      formVisible: false, form: this.blank(), rejDlg: { visible: false, feeId: '' }
    }
  },
  computed: {
    ITEM_TYPE_OPTIONS: () => ITEM_TYPE_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const s = (k) => this.items.filter((x) => x.status === k).length
      return [
        { key: 'p', label: '待审核', value: s('SUBMITTED'), accent: 'warning' },
        { key: 'a', label: '已批准待发', value: s('APPROVED'), accent: 'processing' },
        { key: 'i', label: '已发放', value: s('ISSUED'), accent: 'success' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    blank() { return { studentId: '', itemType: 'REDUCTION', amount: null, reason: '', error: '' } },
    searchStudents(keyword) { return studentAffairsApi.searchStudents(keyword) },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getFeeReductions({ itemType: this.activeType })
      if (res.code === 0 && res.data) this.items = res.data.items || []
      else this.errorMessage = res.message || '加载失败'
      this.loading = false
    },
    setType(k) { if (this.activeType === k) return; this.activeType = k; this.load() },
    async submit() {
      const f = this.form
      const reason = (f.reason || '').trim()
      if (!f.studentId || !reason || reason.length < 5) { f.error = '学生与理由(≥5字)必填'; return }
      f.error = ''; this.acting = 'sub'
      const res = await studentAffairsApi.submitFeeReduction({ studentId: Number(f.studentId), itemType: f.itemType, amount: f.amount != null ? Number(f.amount) : undefined, reason })
      this.acting = ''
      if (res.code === 0) { toast.success('已提交'); this.formVisible = false; this.form = this.blank(); this.load() } else f.error = res.message || '提交失败'
    },
    async review(x, action) {
      if (action === 'REJECT') { this.rejDlg = { visible: true, feeId: x.feeId }; return }
      this.acting = x.feeId
      const res = await studentAffairsApi.reviewFeeReduction(x.feeId, action, '')
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    async submitReject({ reason }) {
      const d = this.rejDlg
      this.acting = d.feeId
      const res = await studentAffairsApi.reviewFeeReduction(d.feeId, 'REJECT', reason.trim())
      this.acting = ''
      if (res.code === 0) { d.visible = false; toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    async issue(x) {
      this.acting = x.feeId
      const res = await studentAffairsApi.issueFeeReduction(x.feeId)
      this.acting = ''
      if (res.code === 0) { toast.success('已发放'); this.load() } else toast.error(res.message || '发放失败')
    },
    amountText(a) { return (a == null || a === '') ? '—' : (typeof a === 'number' ? ('¥' + a) : a) },
    frType(s) { return ({ SUBMITTED: 'warning', APPROVED: 'processing', REJECTED: 'default', ISSUED: 'success' })[s] || 'default' }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); flex: 1; min-width: 300px; }
.fr-grid { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-3); margin-bottom: var(--space-3); }
.fr-wide { grid-column: span 3; }
.fr-field { display: flex; flex-direction: column; gap: 4px; font-size: var(--font-size-sm); }
.fr-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.fr-error { color: var(--danger-500,#dc2626); font-size: var(--font-size-sm); }
.fr-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.fr-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
.fr-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.fr-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fr-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fr-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 220px; }
.fr-ops { display: flex; gap: 6px; }
.fr-muted { color: var(--text-tertiary); }
@media (max-width: 960px) { .sa-grid--metrics, .fr-grid { grid-template-columns: 1fr; } .fr-wide { grid-column: span 1; } }
</style>
