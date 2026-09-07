<template>
  <AppPageShell title="减免与临时补助" subtitle="申请审核与结果落实" role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="减免与临时补助">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载申请台账…" @retry="load" @back="$router.push('/admin/student-affairs/funding')">
      <AppSectionCard title="申请办理台账" compact>
        <div v-if="focusId" class="fr-focus"><strong>当前申请 · {{ focusId }}</strong><button type="button" class="fr-secondary" @click="clearFocus">返回办理台账</button></div>
        <div v-else class="fr-statusbar" aria-label="按办理状态筛选">
          <button v-for="item in quickStatuses" :key="item.value || 'ALL'" type="button" :class="{ active: filters.status === item.value }" @click="setStatus(item.value)"><span>{{ item.label }}</span><strong>{{ item.value ? count(item.value) : Number(statusCounts.ALL || 0) }}</strong></button>
          <AppPermissionButton class="fr-create" code="studentAffairs.funding.reduction.manage" :allowed="canBtn('studentAffairs.funding.reduction.manage')" @click="openRegister">代录申请</AppPermissionButton>
        </div>
        <div v-if="!focusId" class="fr-toolbar">
          <AppTextInput v-model="filters.keyword" class="fr-search" type="search" placeholder="姓名、学号或申请理由" clearable @change="applyFilters" @clear="applyFilters" />
          <AppSelect v-model="filters.itemType" class="fr-filter" :options="typeOptions" @change="applyFilters" />
          <AppTextInput v-model="filters.yearCode" class="fr-year" placeholder="学年，如 2026-2027" :maxlength="9" @change="applyFilters" />
          <button type="button" class="fr-secondary" :disabled="loading" @click="applyFilters">查询</button>
        </div>
        <DataTable v-if="items.length" :columns="feeColumns" :rows="items" row-key="feeId">
          <template #cell-student="{ row }"><strong class="fr-main">{{ row.realName || `学生 ${row.studentId}` }}</strong><small class="fr-sub">{{ row.studentNo || '学号待核对' }}</small></template>
          <template #cell-request="{ row }"><strong class="fr-main">{{ typeLabel(row.itemType) }} · {{ row.yearCode || '学年待核对' }}</strong><small class="fr-sub">{{ categoryLabel(row.reasonCategory) }} · {{ amountText(row.amount) }}</small></template>
          <template #cell-reason="{ row }"><span class="fr-reason">{{ row.reason }}</span><div v-if="row.evidence?.length" class="fr-files"><button v-for="file in row.evidence" :key="file.fileId" type="button" :disabled="fileBusy === file.fileId" @click="openEvidence(file)">{{ file.fileName || '查看材料' }}</button></div></template>
          <template #cell-status="{ row }"><StatusTag :type="statusTone(row.status)" :label="row.statusLabel || row.status" dot /><small v-if="row.reviewOpinion" class="fr-opinion">{{ row.reviewOpinion }}</small></template>
          <template #cell-actions="{ row }"><div class="fr-actions">
            <AppPermissionButton v-if="allows(row, 'APPROVE')" code="studentAffairs.funding.reduction.manage" :allowed="canBtn('studentAffairs.funding.reduction.manage')" size="sm" @click="openAction(row, 'APPROVE')">批准</AppPermissionButton>
            <AppPermissionButton v-if="allows(row, 'RETURN')" code="studentAffairs.funding.reduction.manage" :allowed="canBtn('studentAffairs.funding.reduction.manage')" size="sm" variant="secondary" @click="openAction(row, 'RETURN')">退回补正</AppPermissionButton>
            <AppPermissionButton v-if="allows(row, 'REJECT')" code="studentAffairs.funding.reduction.manage" :allowed="canBtn('studentAffairs.funding.reduction.manage')" size="sm" variant="secondary" danger @click="openAction(row, 'REJECT')">驳回</AppPermissionButton>
            <AppPermissionButton v-if="allows(row, 'FULFILL')" code="studentAffairs.funding.reduction.manage" :allowed="canBtn('studentAffairs.funding.reduction.manage')" size="sm" @click="openAction(row, 'FULFILL')">{{ row.itemType === 'REDUCTION' ? '确认减免' : '登记发放' }}</AppPermissionButton>
            <div v-if="row.status === 'ISSUED'" class="fr-muted"><span>已落实 · {{ row.issuedAt ? new Date(row.issuedAt).toLocaleString('zh-CN', { hour12: false }) : '时间待核对' }}</span><small class="fr-opinion">{{ row.fulfillmentReference || '未填写凭证摘要' }}</small></div>
            <span v-else-if="!row.allowedActions?.length" class="fr-muted">只读</span>
          </div></template>
        </DataTable>
        <div v-else class="fr-empty"><strong>{{ focusId ? '该申请不存在或不在当前权限范围内' : emptyText }}</strong></div>
        <AppPagination v-if="total > pageSize || page > 1" v-model:page="page" v-model:pageSize="pageSize" :total="total" :disabled="loading" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <AppDrawer v-model:visible="registerDrawer.visible" title="代录减免或临时补助" subtitle="用于线下纸质来件，学生本人也可在学生端提交。" mode="modal" size="large">
      <div class="fr-form"><div class="fr-grid">
        <AppFormItem label="学生" required><AppStudentPicker v-model="registerDrawer.form.studentId" placeholder="按姓名 / 学号搜索" :disabled="saving" /></AppFormItem>
        <AppFormItem label="申请类型" required><AppSelect v-model="registerDrawer.form.itemType" :options="typeOptions.slice(1)" :disabled="saving" @change="registerDrawer.form.reasonCategory = 'OTHER'" /></AppFormItem>
        <AppFormItem label="申请学年" required><AppTextInput v-model="registerDrawer.form.yearCode" :maxlength="9" placeholder="2026-2027" :disabled="saving" /></AppFormItem>
        <AppFormItem label="困难类别" required><AppSelect v-model="registerDrawer.form.reasonCategory" :options="categoryOptions(registerDrawer.form.itemType)" :disabled="saving" /></AppFormItem>
        <AppFormItem label="申请金额（元）" required><AppNumberInput v-model="registerDrawer.form.amount" :min="0.01" :precision="2" :disabled="saving" /></AppFormItem>
        <AppFormItem label="证明材料" hint="选填；上传件须通过安全检查后才能提交。"><FileUploader biz-type="REDUCTION" :disabled="saving" button-text="选择材料" @uploaded="onUploaded" @error="onUploadError" /><div v-if="registerDrawer.form.evidence" class="fr-uploaded"><span>{{ registerDrawer.form.evidence.fileName }}</span><button v-if="!registerDrawer.form.evidence.readyForBusiness" type="button" @click="refreshUploaded">检查状态</button></div></AppFormItem>
        <AppFormItem class="fr-span2" label="申请理由" required hint="写清困难事实、发生时间和申请依据。"><AppTextarea v-model="registerDrawer.form.reason" :rows="4" :maxlength="1000" placeholder="至少10字" :disabled="saving" /></AppFormItem>
      </div><AppInlineAlert v-if="registerDrawer.errorMessage" type="danger" :description="registerDrawer.errorMessage" /></div>
      <template #footer><button type="button" class="fr-secondary" :disabled="saving" @click="registerDrawer.visible = false">取消</button><AppPermissionButton code="studentAffairs.funding.reduction.manage" :allowed="canBtn('studentAffairs.funding.reduction.manage')" :loading="saving" @click="submitRegister">提交待审核</AppPermissionButton></template>
    </AppDrawer>

    <AppDrawer v-model:visible="actionDrawer.visible" :title="actionTitle" :subtitle="actionSubtitle" mode="modal" size="small">
      <div v-if="actionDrawer.row" class="fr-form">
        <div class="fr-context"><span>{{ actionDrawer.row.realName }} · {{ actionDrawer.row.studentNo }}</span><strong>{{ typeLabel(actionDrawer.row.itemType) }} · {{ actionDrawer.row.yearCode }} · {{ amountText(actionDrawer.row.amount) }}</strong></div>
        <AppFormItem v-if="['RETURN','REJECT'].includes(actionDrawer.action)" label="处理意见" required><AppTextarea v-model="actionDrawer.form.opinion" :rows="4" :maxlength="1000" :placeholder="actionDrawer.action === 'RETURN' ? '说明需要补正的具体信息或材料' : '说明不予通过的具体依据'" :disabled="saving" /></AppFormItem>
        <AppFormItem v-else-if="actionDrawer.action === 'APPROVE'" label="审核意见"><AppTextarea v-model="actionDrawer.form.opinion" :rows="3" :maxlength="1000" placeholder="选填" :disabled="saving" /></AppFormItem>
        <AppFormItem v-else label="结果凭证摘要"><AppTextInput v-model="actionDrawer.form.fulfillmentReference" :maxlength="200" :placeholder="actionDrawer.row.itemType === 'REDUCTION' ? '如：财务减免清单批次' : '如：财务转账批次'" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="actionDrawer.errorMessage" type="danger" :description="actionDrawer.errorMessage" />
      </div>
      <template #footer><button type="button" class="fr-secondary" :disabled="saving" @click="actionDrawer.visible = false">取消</button><AppPermissionButton code="studentAffairs.funding.reduction.manage" :allowed="canBtn('studentAffairs.funding.reduction.manage')" :loading="saving" @click="submitAction">{{ actionConfirmText }}</AppPermissionButton></template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppStudentPicker, AppTextarea, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import FileUploader from '@/components/file/FileUploader.vue'
import { DataTable } from '@/components/business'
import { fileSdk } from '@/services/file/fileSdk'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const COLUMNS = [{ key: 'student', title: '学生', width: '145px' }, { key: 'request', title: '申请项目', width: '210px' }, { key: 'reason', title: '理由与材料' }, { key: 'status', title: '状态', width: '170px' }, { key: 'actions', title: '下一步', align: 'right', width: '250px' }]
const TYPES = [{ label: '全部类型', value: '' }, { label: '学费减免', value: 'REDUCTION' }, { label: '临时困难补助', value: 'TEMP_AID' }]
const CATEGORIES = {
  REDUCTION: [{ label: '特殊身份', value: 'SPECIAL_IDENTITY' }, { label: '特别困难', value: 'EXTREME_DIFFICULTY' }, { label: '其他', value: 'OTHER' }],
  TEMP_AID: [{ label: '重大疾病', value: 'SERIOUS_ILLNESS' }, { label: '自然灾害', value: 'DISASTER' }, { label: '家庭变故', value: 'FAMILY_CHANGE' }, { label: '意外事故', value: 'ACCIDENT' }, { label: '其他', value: 'OTHER' }]
}
const academicYear = () => { const now = new Date(); const start = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1; return `${start}-${start + 1}` }
const freshRegister = () => ({ studentId: '', itemType: 'REDUCTION', yearCode: academicYear(), reasonCategory: 'OTHER', amount: null, reason: '', evidence: null })

export default {
  name: 'FeeReductionView',
  components: { AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppNumberInput, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppSelect, AppStudentPicker, AppTextarea, AppTextInput, DataTable, FileUploader, StatusTag: AppStatusTag },
  props: { ctx: { type: Object, default: null } },
  data() { return { feeColumns: COLUMNS, typeOptions: TYPES, quickStatuses: [{ label: '待审核', value: 'SUBMITTED' }, { label: '已批准', value: 'APPROVED' }, { label: '待补正', value: 'RETURNED' }, { label: '已落实', value: 'ISSUED' }, { label: '全部', value: '' }], loading: true, saving: false, fileBusy: '', loadSeq: 0, errorMessage: '', items: [], statusCounts: {}, filters: { keyword: '', itemType: '', yearCode: '', status: 'SUBMITTED' }, page: 1, pageSize: 20, total: 0, registerDrawer: { visible: false, form: freshRegister(), errorMessage: '' }, actionDrawer: { visible: false, row: null, action: '', form: {}, errorMessage: '' } } },
  computed: {
    focusId() { return String(this.$route.query.recordId ?? '') },
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    hasFilters() { return Boolean(this.filters.keyword || this.filters.itemType || this.filters.yearCode) },
    emptyText() { if (this.hasFilters) return '没有匹配的申请'; return ({ SUBMITTED: '当前没有待审核申请', APPROVED: '当前没有待落实申请', RETURNED: '当前没有待补正申请', ISSUED: '暂无已落实记录' })[this.filters.status] || '当前范围还没有申请' },
    actionTitle() { return ({ APPROVE: '批准申请', RETURN: '退回学生补正', REJECT: '驳回申请', FULFILL: this.actionDrawer.row?.itemType === 'REDUCTION' ? '确认学费减免' : '登记补助发放' })[this.actionDrawer.action] || '处理申请' },
    actionSubtitle() { return ({ APPROVE: '批准后进入结果落实。', RETURN: '学生 PC 与小程序会看到具体补正意见。', REJECT: '驳回后本次申请结束。', FULFILL: this.actionDrawer.row?.itemType === 'REDUCTION' ? '确认财务收费台账已经执行减免。' : '确认补助款已经进入财务发放流程。' })[this.actionDrawer.action] || '' },
    actionConfirmText() { return ({ APPROVE: '确认批准', RETURN: '确认退回', REJECT: '确认驳回', FULFILL: this.actionDrawer.row?.itemType === 'REDUCTION' ? '确认减免' : '登记发放' })[this.actionDrawer.action] || '确认' }
  },
  watch: { '$route.query.recordId': { immediate: true, handler() { this.page = 1; this.actionDrawer.visible = false; this.load() } } }, beforeUnmount() { this.loadSeq++ },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) }, count(status) { return Number(this.statusCounts?.[status] || 0) }, allows(row, action) { return Array.isArray(row?.allowedActions) && row.allowedActions.includes(action) },
    typeLabel(type) { return type === 'TEMP_AID' ? '临时困难补助' : '学费减免' }, categoryOptions(type) { return CATEGORIES[type] || CATEGORIES.REDUCTION }, categoryLabel(value) { return Object.values(CATEGORIES).flat().find(item => item.value === value)?.label || '其他' },
    statusTone(status) { return ({ SUBMITTED: 'warning', RETURNED: 'danger', APPROVED: 'processing', REJECTED: 'default', ISSUED: 'success', WITHDRAWN: 'default' })[status] || 'default' },
    amountText(value) { return value === null || value === undefined || value === '' ? '—' : (Number.isFinite(Number(value)) ? `¥${Number(value).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : value) },
    async load() { const seq = ++this.loadSeq; this.loading = true; this.errorMessage = ''; try { if (this.focusId && !/^[1-9]\d*$/.test(this.focusId)) throw new Error('申请链接无效，请返回台账重新选择'); const query = this.focusId ? { recordId: this.focusId, page: 1, pageSize: 1 } : { ...this.filters, keyword: this.filters.keyword.trim(), yearCode: this.filters.yearCode.trim(), page: this.page, pageSize: this.pageSize }; const response = await studentAffairsApi.getFeeReductions(query); if (seq !== this.loadSeq) return; if (response.code !== 0 || !response.data) throw new Error(response.message || '申请台账加载失败'); this.items = response.data.items || []; this.total = Number(response.data.total || 0); this.statusCounts = response.data.statusCounts || {}; const lastPage = Math.max(1, Math.ceil(this.total / this.pageSize)); if (this.page > lastPage) { this.page = lastPage; await this.load() } } catch (error) { if (seq === this.loadSeq) this.errorMessage = error.message || '申请台账加载失败' } finally { if (seq === this.loadSeq) this.loading = false } },
    clearFocus() { const query = { ...this.$route.query }; delete query.recordId; return this.$router.replace({ query }) },
    applyFilters() { this.page = 1; this.load() }, setStatus(status) { this.filters.status = status; this.applyFilters() }, openRegister() { this.registerDrawer = { visible: true, form: freshRegister(), errorMessage: '' } },
    validate(form) { const year = String(form.yearCode || '').trim(); const amount = Number(form.amount); const reason = String(form.reason || '').trim(); if (!form.studentId) return '请选择学生'; if (!/^\d{4}-\d{4}$/.test(year) || Number(year.slice(5)) !== Number(year.slice(0, 4)) + 1) return '申请学年应为连续的 YYYY-YYYY'; if (!Number.isFinite(amount) || amount <= 0) return '申请金额必须大于0'; if (reason.length < 10) return '请填写至少10字的申请理由'; if (form.evidence && !form.evidence.readyForBusiness) return '证明材料仍在安全检查，请稍后检查状态再提交'; return '' },
    async submitRegister() { if (this.saving) return; const form = this.registerDrawer.form; const error = this.validate(form); if (error) { this.registerDrawer.errorMessage = error; return } this.saving = true; this.registerDrawer.errorMessage = ''; try { const response = await studentAffairsApi.submitFeeReduction({ studentId: String(form.studentId), itemType: form.itemType, yearCode: form.yearCode.trim(), reasonCategory: form.reasonCategory, amount: String(form.amount), reason: form.reason.trim(), attachmentIds: form.evidence ? [form.evidence.fileId] : [] }); if (response.code !== 0) throw new Error(response.message || '申请代录失败'); toast.success('申请已进入待审核'); this.registerDrawer.visible = false; this.page = 1; await this.load() } catch (error) { this.registerDrawer.errorMessage = error.message || '申请代录失败' } finally { this.saving = false } },
    openAction(row, action) { this.actionDrawer = { visible: true, row, action, form: { opinion: '', fulfillmentReference: '' }, errorMessage: '' } },
    async submitAction() { if (this.saving || !this.actionDrawer.row) return; const { row, action, form } = this.actionDrawer; const opinion = String(form.opinion || '').trim(); if (!this.allows(row, action)) { this.actionDrawer.errorMessage = '当前状态已变化，请刷新后重试'; return } if (['RETURN', 'REJECT'].includes(action) && opinion.length < 5) { this.actionDrawer.errorMessage = '请填写至少5字的具体处理意见'; return } this.saving = true; this.actionDrawer.errorMessage = ''; try { const body = { action, version: row.version, opinion: opinion || undefined, ...(action === 'FULFILL' ? { fulfillmentChannel: row.itemType === 'REDUCTION' ? 'TUITION_LEDGER' : 'BANK_TRANSFER', fulfillmentReference: String(form.fulfillmentReference || '').trim() || undefined } : {}) }; const response = await studentAffairsApi.actionFeeReduction(row.feeId, body); if (response.code !== 0) throw new Error(response.message || '申请处理失败'); toast.success(({ APPROVE: '申请已批准', RETURN: '已退回学生补正', REJECT: '申请已驳回', FULFILL: row.itemType === 'REDUCTION' ? '学费减免已确认' : '补助发放已登记' })[action]); this.actionDrawer.visible = false; await this.load() } catch (error) { this.actionDrawer.errorMessage = error.message || '申请处理失败'; if (error.bizCode === 'APPROVAL_VERSION_CONFLICT') await this.load() } finally { this.saving = false } },
    onUploaded(file) { this.registerDrawer.form.evidence = file; this.registerDrawer.errorMessage = '' }, onUploadError(error) { this.registerDrawer.errorMessage = error?.message || '证明材料上传失败' },
    async refreshUploaded() { const file = this.registerDrawer.form.evidence; if (!file?.fileId) return; try { this.registerDrawer.form.evidence = await fileSdk.metadata(file.fileId) } catch (error) { this.registerDrawer.errorMessage = error.message || '文件状态检查失败' } },
    async openEvidence(file) { if (!file?.fileId || this.fileBusy) return; this.fileBusy = file.fileId; try { if (file.canPreview) await fileSdk.preview(file.fileId, file.fileName); else if (file.canDownload) await fileSdk.download(file.fileId, file.fileName); else throw new Error('材料尚未通过安全检查') } catch (error) { toast.error(error.message || '材料打开失败') } finally { this.fileBusy = '' } }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.fr-focus { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
.fr-statusbar { display:flex; align-items:center; gap:8px; margin-bottom:12px; overflow-x:auto; }.fr-statusbar > button { display:flex; align-items:center; gap:7px; min-height:34px; padding:5px 11px; border:1px solid var(--border-light); border-radius:999px; color:var(--text-secondary); background:var(--bg-card); cursor:pointer; white-space:nowrap; }.fr-statusbar > button.active { border-color:var(--color-primary); color:var(--color-primary); background:color-mix(in srgb,var(--color-primary) 10%,var(--bg-card)); }.fr-statusbar > .fr-create { margin-left:auto; flex:none; }
.fr-toolbar { display:grid; grid-template-columns:minmax(240px,1fr) 180px 180px auto; gap:8px; margin-bottom:12px; }.fr-secondary { min-height:34px; padding:0 15px; border:1px solid var(--border-light); border-radius:var(--radius-md); color:var(--text-primary); background:var(--bg-card); cursor:pointer; }
.fr-main,.fr-sub,.fr-reason,.fr-opinion { display:block; }.fr-sub,.fr-reason + .fr-files { margin-top:4px; }.fr-sub { color:var(--text-secondary); }.fr-reason { max-width:360px; color:var(--text-secondary); font-size:var(--font-size-sm); line-height:1.45; }.fr-files { display:flex; flex-wrap:wrap; gap:6px; }.fr-files button,.fr-uploaded button { border:0; padding:0; color:var(--color-primary); background:none; cursor:pointer; font-size:12px; }.fr-opinion { max-width:180px; color:var(--text-secondary); font-size:12px; line-height:1.4; }.fr-actions { display:flex; flex-wrap:wrap; justify-content:flex-end; gap:6px; }.fr-muted { color:var(--text-tertiary); }
.fr-empty { padding:28px 16px; text-align:center; color:var(--text-secondary); }.fr-empty strong { color:var(--text-primary); }.fr-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }.fr-span2 { grid-column:1/-1; }.fr-context { display:flex; flex-direction:column; gap:5px; margin-bottom:16px; padding:12px; border-radius:10px; background:var(--bg-page); }.fr-context span { color:var(--text-secondary); font-size:12px; }.fr-uploaded { display:flex; justify-content:space-between; gap:10px; margin-top:8px; color:var(--text-secondary); font-size:12px; }
@media (max-width:960px) { .fr-toolbar { grid-template-columns:1fr 1fr; }.fr-search { grid-column:1/-1; } } @media (max-width:680px) { .fr-grid,.fr-toolbar { grid-template-columns:1fr; }.fr-span2,.fr-search { grid-column:auto; } }
</style>
