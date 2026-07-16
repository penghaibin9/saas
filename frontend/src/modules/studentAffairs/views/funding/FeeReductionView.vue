<template>
  <AppPageShell title="减免与临时补助" subtitle="学费减免 / 临时困难补助：申请 → 审核 → 发放。金额按角色脱敏。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="减免与临时补助">
    <template #actions>
      <AppPermissionButton code="studentAffairs.funding.reduction.manage" @click="openForm">代录申请</AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

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
                  <AppPermissionButton code="studentAffairs.funding.reduction.manage" size="sm" variant="secondary" danger @click="openReject(x)">驳回</AppPermissionButton>
                </template>
                <AppPermissionButton v-else-if="x.status==='APPROVED'" code="studentAffairs.funding.reduction.manage" size="sm" :loading="acting===x.feeId" @click="issue(x)">发放</AppPermissionButton>
                <span v-else class="fr-muted">—</span>
              </td>
            </tr>
            <tr v-if="!items.length"><td colspan="6" class="sa-empty">暂无记录</td></tr>
          </tbody>
        </table>
        <!-- 后端 /student-affairs/fee-reductions 当前不接受 page/pageSize 参数（服务层直接返回全量 items，无 total），
             暂不引入 AppPagination；如后续台账量增长需先补后端分页能力。 -->
      </AppSectionCard>
    </AppGlobalState>

    <!-- 代录申请 -->
    <AppDrawer v-model:visible="drawer.visible" title="申请减免/临补">
      <div class="sa-form">
        <AppFormItem label="学生主档ID" required>
          <AppNumberInput v-model="drawer.form.studentId" :min="1" placeholder="请输入学生主档ID" :disabled="acting==='sub'" />
        </AppFormItem>
        <AppFormItem label="类型">
          <AppSelect v-model="drawer.form.itemType" :options="itemTypeOptions" :disabled="acting==='sub'" />
        </AppFormItem>
        <AppFormItem label="金额">
          <AppNumberInput v-model="drawer.form.amount" :min="0" placeholder="选填" :disabled="acting==='sub'" />
        </AppFormItem>
        <AppFormItem label="理由" required hint="至少5字">
          <AppTextarea v-model="drawer.form.reason" :rows="3" placeholder="请说明申请理由，不少于 5 字" :disabled="acting==='sub'" />
        </AppFormItem>
        <AppInlineAlert v-if="drawer.errorMessage" type="danger" :description="drawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="fr-btn" :disabled="acting==='sub'" @click="drawer.visible=false">取消</button>
        <AppPermissionButton code="studentAffairs.funding.reduction.manage" :loading="acting==='sub'" @click="submit">提交</AppPermissionButton>
      </template>
    </AppDrawer>

    <!-- 驳回（原因必填，保留强制校验） -->
    <AppConfirmDialog
      v-model:visible="rejectDialog.visible"
      title="驳回申请"
      message="驳回后本次申请不予批准，需说明驳回意见。"
      type="danger"
      confirm-text="确认驳回"
      :require-reason="true"
      reason-label="驳回意见（至少5字）"
      reason-placeholder="请说明驳回意见，不少于 5 字"
      phrase-scene-key="sa.aid.reject"
      :submitting="acting===rejectDialog.feeId"
      @confirm="onRejectConfirm"
    />
  </AppPageShell>
</template>

<script>
import { AppConfirmDialog, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput,
        AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppTextarea } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const TYPE_FILTERS = [{ key: '', label: '全部' }, { key: 'REDUCTION', label: '学费减免' }, { key: 'TEMP_AID', label: '临时补助' }]
const ITEM_TYPE_OPTIONS = [{ label: '学费减免', value: 'REDUCTION' }, { label: '临时补助', value: 'TEMP_AID' }]

export default {
  name: 'FeeReductionView',
  components: { AppConfirmDialog, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
               AppNumberInput, AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppTextarea,
               StatusTag: AppStatusTag },
  data() {
    return {
      loading: true, acting: '', errorMessage: '', items: [], activeType: '', typeFilters: TYPE_FILTERS,
      itemTypeOptions: ITEM_TYPE_OPTIONS,
      drawer: { visible: false, form: this.blank(), errorMessage: '' },
      rejectDialog: { visible: false, feeId: '' }
    }
  },
  computed: {
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
    blank() { return { studentId: null, itemType: 'REDUCTION', amount: null, reason: '' } },
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getFeeReductions({ itemType: this.activeType })
      if (res.code === 0 && res.data) this.items = res.data.items || []
      else this.errorMessage = res.message || '加载失败'
      this.loading = false
    },
    setType(k) { if (this.activeType === k) return; this.activeType = k; this.load() },
    openForm() {
      this.drawer.form = this.blank()
      this.drawer.errorMessage = ''
      this.drawer.visible = true
    },
    async submit() {
      const f = this.drawer.form
      if (!f.studentId || !f.reason || f.reason.trim().length < 5) { this.drawer.errorMessage = '学生ID与理由(≥5字)必填'; return }
      this.drawer.errorMessage = ''
      this.acting = 'sub'
      const res = await studentAffairsApi.submitFeeReduction({ studentId: Number(f.studentId), itemType: f.itemType, amount: f.amount != null ? Number(f.amount) : undefined, reason: f.reason })
      this.acting = ''
      if (res.code === 0) { toast.success('已提交'); this.drawer.visible = false; this.load() } else this.drawer.errorMessage = res.message || '提交失败'
    },
    async review(x, action) {
      this.acting = x.feeId
      const res = await studentAffairsApi.reviewFeeReduction(x.feeId, action, '')
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    openReject(x) {
      this.rejectDialog = { visible: true, feeId: x.feeId }
    },
    async onRejectConfirm({ reason }) {
      const feeId = this.rejectDialog.feeId
      this.acting = feeId
      const res = await studentAffairsApi.reviewFeeReduction(feeId, 'REJECT', reason)
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.rejectDialog.visible = false; this.load() } else toast.error(res.message || '操作失败')
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
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.fr-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); }
.fr-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.fr-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fr-reason { color: var(--text-secondary); font-size: var(--font-size-sm); max-width: 220px; }
.fr-ops { display: flex; gap: 6px; }
.fr-muted { color: var(--text-tertiary); }
.sa-form { display: flex; flex-direction: column; gap: var(--space-1); }
.fr-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 7px 16px; cursor: pointer; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr; } }
</style>
