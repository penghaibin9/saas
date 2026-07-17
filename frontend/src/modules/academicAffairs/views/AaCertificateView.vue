<template>
  <ModulePageShell
    title="毕业证书管理"
    :subtitle="'按终审结论批量生成证书编号（毕业证/结业证）· 电子注册号 · 发放登记 · 作废补发（编号不回收）'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="openGenerate">批量生成证书</AppButton>
    </template>

    <div class="aacert-bar">
      <AppTextInput v-model="keyword" placeholder="学号/姓名/证书编号" style="max-width:220px" @change="load" />
      <AppSelect v-model="statusFilter" :options="statusOptions" style="max-width:150px" @change="load" />
      <AppSelect v-model="typeFilter" :options="typeOptions" style="max-width:150px" @change="load" />
    </div>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!rows.length" title="暂无证书" description="从毕业审核批次批量生成" />
    <DataTable v-else :columns="columns" :rows="rows" row-key="certificateId">
      <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）<div class="mp-cell-sub">{{ row.majorName || '' }}</div></template>
      <template #cell-cert="{ row }">
        <div class="mp-cell-main">{{ row.certNo }}</div>
        <div class="mp-cell-sub">{{ row.eRegNo ? '电子注册号 ' + row.eRegNo : '无电子注册号' }} · {{ row.issueDate || '未填签发日期' }}</div>
      </template>
      <template #cell-type="{ row }">
        <StatusTag :type="row.certType === 'GRADUATION' ? 'success' : 'warning'"
                   :label="row.certType === 'GRADUATION' ? '毕业证' : '结业证'" dot />
      </template>
      <template #cell-status="{ row }">
        <StatusTag :type="row.status === 'ISSUED' ? 'success' : row.status === 'VOIDED' ? 'danger' : 'primary'"
                   :label="{ GENERATED: '已生成', ISSUED: '已发放', VOIDED: '已作废' }[row.status] || row.status" dot />
      </template>
      <template #cell-ops="{ row }">
        <button v-if="row.status === 'GENERATED'" class="mp-link" @click="issue(row)">登记发放</button>
        <button v-if="row.status !== 'VOIDED'" class="mp-link is-danger" @click="openVoid(row)">作废</button>
        <span v-if="row.status === 'VOIDED'" class="mp-cell-sub">{{ row.voidReason }}</span>
      </template>
    </DataTable>

    <AppDrawer :visible="genVisible" title="批量生成证书" @close="genVisible = false">
      <div class="aacert-form">
        <AppFormItem label="毕业审核批次 ID" required><AppTextInput v-model="genForm.batchId" placeholder="已终审的审核批次 ID" :disabled="saving" /></AppFormItem>
        <AppFormItem label="编号前缀（学校代码）" required><AppTextInput v-model="genForm.prefix" placeholder="如 13899" :disabled="saving" /></AppFormItem>
        <AppFormItem label="签发年份" required><AppTextInput v-model="genForm.year" placeholder="如 2025" :disabled="saving" /></AppFormItem>
        <AppFormItem label="电子注册号前缀"><AppTextInput v-model="genForm.eRegPrefix" placeholder="选填；空=不生成电子注册号" :disabled="saving" /></AppFormItem>
        <AppFormItem label="签发日期"><AppTextInput v-model="genForm.issueDate" placeholder="YYYY-MM-DD" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="info" description="按批次终审结论生成：毕业(GRADUATED)→毕业证，结业(COMPLETED)→结业证；已有未作废证书的学生自动跳过；编号连续流水、绝不回收。" />
        <AppInlineAlert v-if="genError" type="danger" :description="genError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="genVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitGenerate">生成</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="voidVisible" :title="'作废证书 · ' + (voidRow ? voidRow.certNo : '')" @close="voidVisible = false">
      <div class="aacert-form">
        <AppFormItem label="作废原因（≥5字）" required><AppTextarea v-model="voidReason" placeholder="如：打印信息有误需补发" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="voidError" type="danger" :description="voidError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="voidVisible = false">取消</AppButton>
        <AppButton variant="danger" :loading="saving" @click="submitVoid">作废</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 毕业证书管理（/admin/academic-affairs/certificates）：批量生成编号+台账+发放+作废。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect } from '@/components/common'
import { academicAffairsApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaCertificateView',
  components: {
    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,
    AppButton, AppDrawer, AppTextInput, AppTextarea, AppFormItem, AppConfirmDialog, AppInlineAlert, AppSelect
  },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      loading: true, error: '', rows: [], keyword: '', statusFilter: '', typeFilter: '',
      statusOptions: [{ label: '全部状态', value: '' }, { label: '已生成', value: 'GENERATED' },
                      { label: '已发放', value: 'ISSUED' }, { label: '已作废', value: 'VOIDED' }],
      typeOptions: [{ label: '全部类型', value: '' }, { label: '毕业证', value: 'GRADUATION' },
                    { label: '结业证', value: 'COMPLETION' }],
      columns: [{ key: 'student', title: '学生' }, { key: 'cert', title: '证书编号' },
                { key: 'type', title: '类型' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      genVisible: false, genForm: { batchId: '', prefix: '', year: '', eRegPrefix: '', issueDate: '' }, genError: '',
      voidVisible: false, voidRow: null, voidReason: '', voidError: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null
    }
  },
  async created() {
    const c = await api.getContext()
    if (c.code === 0) this.ctx = c.data
    this.load()
  },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const params = { pageSize: 100 }
      if (this.keyword) params.keyword = this.keyword
      if (this.statusFilter) params.status = this.statusFilter
      if (this.typeFilter) params.certType = this.typeFilter
      const res = await api.listCertificates(params)
      if (res.code === 0) this.rows = res.data.list
      else this.error = res.message
      this.loading = false
    },
    openGenerate() { this.genForm = { batchId: '', prefix: '', year: '', eRegPrefix: '', issueDate: '' }; this.genError = ''; this.genVisible = true },
    async submitGenerate() {
      if (!this.genForm.batchId || !this.genForm.prefix || !this.genForm.year) { this.genError = '批次/前缀/年份必填'; return }
      this.saving = true
      const res = await api.generateCertificates(this.genForm.batchId, {
        prefix: this.genForm.prefix, year: this.genForm.year,
        eRegPrefix: this.genForm.eRegPrefix || undefined, issueDate: this.genForm.issueDate || undefined
      })
      this.saving = false
      if (res.code === 0) { toast.success(res.message); this.genVisible = false; this.load() } else this.genError = res.message
    },
    issue(row) {
      this.confirmTitle = '登记发放'
      this.confirmMessage = `确认登记发放「${row.studentName}」的${row.certType === 'GRADUATION' ? '毕业证' : '结业证'}（${row.certNo}）？`
      this.pendingAction = async () => {
        const res = await api.issueCertificate(row.certificateId)
        if (res.code === 0) { toast.success('已登记发放'); this.load() } else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    openVoid(row) { this.voidRow = row; this.voidReason = ''; this.voidError = ''; this.voidVisible = true },
    async submitVoid() {
      if (!this.voidReason || this.voidReason.trim().length < 5) { this.voidError = '原因至少5字'; return }
      this.saving = true
      const res = await api.voidCertificate(this.voidRow.certificateId, this.voidReason.trim())
      this.saving = false
      if (res.code === 0) { toast.success('已作废（补发请重新生成）'); this.voidVisible = false; this.load() } else this.voidError = res.message
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aacert-bar { display: flex; gap: 8px; margin-bottom: 12px; }
.aacert-form { display: flex; flex-direction: column; gap: 12px; }
</style>
