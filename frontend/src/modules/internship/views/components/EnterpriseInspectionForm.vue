<template>
  <AppDrawer :visible="true" :title="record ? (readonly ? '考察详情' : '编辑考察草稿') : '登记企业考察'" mode="modal" size="large" @update:visible="close">
    <p class="inspection-company">{{ companyName }}<span>{{ base?.statusLabel || '新草稿' }}</span></p>
    <AppInlineAlert v-if="error" type="danger" :description="error" />
    <div v-if="latest" class="inspection-conflict" role="status">
      <strong>最新记录：{{ latest.statusLabel }} · 版本 {{ latest.version }}</strong>
      <p>{{ latest.conclusion || '未填写结论' }}</p>
      <p>当前填写内容已保留。重新加载会放弃当前未保存内容。</p>
      <AppButton variant="secondary" @click="replaceWithLatest">放弃当前填写，加载最新记录</AppButton>
    </div>
    <AppForm :model="form" layout="vertical" @submit="save">
      <AppDescriptionList v-if="readonly" class="inspection-summary" :items="readFields" size="compact" />
      <fieldset v-if="!readonly" :disabled="saving" class="inspection-fields">
        <legend>考察安排</legend>
        <AppFormItem v-slot="{ id }" label="考察方式">
          <AppSelect :id="id" v-model="form.inspectionType" :disabled="readonly || saving" :options="typeOptions" />
        </AppFormItem>
        <AppFormItem v-slot="{ id }" label="考察时间">
          <AppTextInput :id="id" v-model="form.inspectionDate" type="datetime-local" />
        </AppFormItem>
        <AppFormItem v-slot="{ id }" label="考察人员">
          <AppTextInput :id="id" v-model="form.inspectors" placeholder="参与考察的人员" />
        </AppFormItem>
        <AppFormItem v-slot="{ id }" label="准入有效期至" hint="按学校审核结果填写；空值表示未设置到期日">
          <AppTextInput :id="id" v-model="form.validUntil" type="datetime-local" />
        </AppFormItem>
        <AppFormItem v-slot="{ id }" class="inspection-full" label="实际工作场所">
          <AppTextInput :id="id" v-model="form.workplaceAddress" placeholder="记录实习工作地点" />
        </AppFormItem>
      </fieldset>
      <fieldset v-if="!readonly" :disabled="saving" class="inspection-fields">
        <legend>现场条件与结论</legend>
        <AppFormItem v-for="field in conditionFields" :key="field.key" v-slot="{ id }" :label="field.label">
          <AppTextarea :id="id" v-model="form[field.key]" :rows="2" :placeholder="field.hint" />
        </AppFormItem>
        <AppFormItem v-slot="{ id }" class="inspection-full" label="考察结论" hint="可先保存草稿；提交审核前需填写结论">
          <AppTextarea :id="id" v-model="form.conclusion" :rows="3" placeholder="概述考察事实和结论" />
        </AppFormItem>
        <AppFormItem v-slot="{ id }" label="发现的风险">
          <AppTextarea :id="id" v-model="form.riskItems" :rows="3" placeholder="如有风险，记录具体事实" />
        </AppFormItem>
        <AppFormItem v-slot="{ id }" label="整改要求">
          <AppTextarea :id="id" v-model="form.rectificationItems" :rows="3" placeholder="记录整改事项和跟进要求" />
        </AppFormItem>
      </fieldset>
      <section class="inspection-evidence" aria-label="考察材料">
        <h3>考察材料 <small>{{ form.fileIds.length }}/20</small></h3>
        <FileUploader v-if="!readonly" biz-type="TEMP_PRIVATE" :disabled="saving || form.fileIds.length >= 20" button-text="添加考察材料"
          @progress="uploading = true" @uploaded="uploaded" @cancelled="uploading = false" @error="uploadError" />
        <p v-if="fileError" role="alert">{{ fileError }}</p>
        <SecureFileList :items="files" :loading="filesLoading" empty-text="暂无考察材料" @refresh="loadFiles" @preview="preview" @download="download" />
        <div v-if="!readonly" class="inspection-remove">
          <button v-for="file in files" :key="file.fileId" type="button" :disabled="saving" @click="removeFile(file.fileId)">移除 {{ file.fileName || '该材料' }}</button>
        </div>
      </section>
      <section v-if="base?.reviewedAt" class="inspection-review">
        <h3>审核结果</h3>
        <p>{{ base.statusLabel }} · {{ base.reviewedByName }} · {{ dateTime(base.reviewedAt) }}</p>
        <p>{{ base.reviewComment || '未填写审核意见' }}</p>
      </section>
    </AppForm>
    <template #footer>
      <AppButton variant="ghost" :disabled="saving" @click="close">{{ readonly ? '关闭' : '取消' }}</AppButton>
      <AppButton v-if="!readonly" variant="primary" :loading="saving" :disabled="uploading || filesLoading || !!fileError" @click="save">保存草稿</AppButton>
    </template>
  </AppDrawer>
</template>

<script>
import { AppDrawer, AppButton } from '@/components/ui'
import { AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppInlineAlert, AppDescriptionList } from '@/components/common'
import FileUploader from '@/components/file/FileUploader.vue'
import SecureFileList from '@/components/file/SecureFileList.vue'
import { fileSdk } from '@/services/file/fileSdk'
import { complianceApi } from '@/modules/internship/api/compliance.api'
import { formatDateTime } from '@/utils/dateUtils'

const TEXT_KEYS = ['inspectors', 'workplaceAddress', 'safetyCondition', 'accommodationCondition', 'mentorCondition', 'remunerationCondition', 'conclusion', 'riskItems', 'rectificationItems']
function draft(record) {
  const value = record || {}
  return {
    ...Object.fromEntries(TEXT_KEYS.map((key) => [key, value[key] || ''])),
    inspectionType: value.inspectionType || 'DOCUMENT',
    inspectionDate: formatDateTime(value.inspectionDate, '').replace(' ', 'T'),
    validUntil: formatDateTime(value.validUntil, '').replace(' ', 'T'),
    fileIds: [...(value.fileIds || [])].map(String)
  }
}
export default {
  name: 'EnterpriseInspectionForm',
  components: { AppDrawer, AppButton, AppForm, AppFormItem, AppTextInput, AppTextarea, AppSelect, AppInlineAlert, AppDescriptionList, FileUploader, SecureFileList },
  props: {
    companyId: { type: String, required: true }, companyName: { type: String, required: true },
    batchId: { type: String, default: '' }, record: { type: Object, default: null }, canManage: Boolean
  },
  emits: ['close', 'saved'],
  data() {
    return { form: draft(this.record), base: this.record, saving: false, uploading: false, error: '', latest: null,
      files: [], filesLoading: false, fileError: '', sequence: 0, alive: true,
      typeOptions: [{ value: 'DOCUMENT', label: '书面审查' }, { value: 'ONSITE', label: '实地考察' }, { value: 'REMOTE', label: '远程考察' }],
      conditionFields: [{ key: 'safetyCondition', label: '安全条件', hint: '作业环境、防护与安全安排' },
        { key: 'accommodationCondition', label: '住宿条件', hint: '住宿环境与生活保障' },
        { key: 'mentorCondition', label: '指导条件', hint: '企业导师与指导安排' },
        { key: 'remunerationCondition', label: '报酬条件', hint: '报酬约定与发放安排' }]
    }
  },
  computed: {
    readonly() { return !this.canManage || (!!this.base && this.base.status !== 'DRAFT') },
    readFields() {
      const row = this.base || {}
      return [
        { label: '考察方式', value: row.inspectionTypeLabel }, { label: '考察时间', value: formatDateTime(row.inspectionDate) },
        { label: '考察人员', value: row.inspectors }, { label: '准入有效期至', value: formatDateTime(row.validUntil, '未设置到期日') },
        { label: '实际工作场所', value: row.workplaceAddress, span: 2 },
        ...this.conditionFields.map(field => ({ label: field.label, value: row[field.key], span: 2 })),
        { label: '考察结论', value: row.conclusion, span: 2 }, { label: '发现的风险', value: row.riskItems, span: 2 },
        { label: '整改要求', value: row.rectificationItems, span: 2 }
      ]
    }
  },
  created() { this.loadFiles() },
  beforeUnmount() { this.alive = false; this.sequence++ },
  methods: {
    dateTime: formatDateTime,
    close() { if (!this.saving) this.$emit('close') },
    async loadFiles() {
      const sequence = ++this.sequence
      this.filesLoading = true; this.fileError = ''
      const results = await Promise.allSettled(this.form.fileIds.map((id) => fileSdk.metadata(id)))
      if (!this.alive || sequence !== this.sequence) return
      this.files = results.map((result, index) => result.status === 'fulfilled' ? result.value : {
        fileId: this.form.fileIds[index], fileName: `材料 ${index + 1}`, statusText: '读取失败或无权查看'
      })
      if (results.some((result) => result.status === 'rejected')) this.fileError = '部分材料读取失败，请重试或移除后重新添加。'
      this.filesLoading = false
    },
    uploaded(file) {
      this.uploading = false
      if (!this.alive || this.readonly || !file.fileId) return
      const id = String(file.fileId)
      if (!this.form.fileIds.includes(id)) this.form.fileIds.push(id)
      this.loadFiles()
    },
    uploadError(error) { this.uploading = false; this.fileError = error?.message || '上传失败，请重试' },
    removeFile(id) { this.form.fileIds = this.form.fileIds.filter((value) => value !== String(id)); this.loadFiles() },
    async preview(file) { try { await fileSdk.preview(file.fileId) } catch (e) { this.fileError = e.message || '预览失败' } },
    async download(file) { try { await fileSdk.download(file.fileId, file.fileName) } catch (e) { this.fileError = e.message || '下载失败' } },
    replaceWithLatest() {
      if (!this.latest || this.saving) return
      this.base = this.latest; this.form = draft(this.latest); this.latest = null; this.error = ''; this.loadFiles()
    },
    async save() {
      if (this.saving || this.readonly || this.uploading || this.filesLoading || this.fileError) return
      this.error = ''; this.saving = true
      try {
        if (this.files.some((file) => !file.readyForBusiness)) throw new Error('材料尚未通过安全检查，请刷新材料状态后再保存。')
        const body = { ...this.form, companyId: this.companyId,
          inspectionDate: this.form.inspectionDate ? new Date(this.form.inspectionDate).toISOString() : null,
          validUntil: this.form.validUntil ? new Date(this.form.validUntil).toISOString() : null }
        if (this.base) body.expectedVersion = this.base.version
        else if (this.batchId) body.batchId = this.batchId
        const response = this.base ? await complianceApi.updateInspection(this.base.id, body) : await complianceApi.createInspection(body)
        if (!this.alive) return
        if (response.code !== 0) {
          this.error = response.message || '保存失败，已保留填写内容'
          if (this.base) {
            const fresh = await complianceApi.listInspections(this.companyId)
            if (!this.alive) return
            const row = fresh.code === 0 && (Array.isArray(fresh.data) ? fresh.data : fresh.data?.list || []).find((item) => String(item.id) === String(this.base.id))
            if (row && row.version !== this.base.version) this.latest = row
          }
          return
        }
        if (typeof window !== 'undefined') window.__SAAS_DIRTY_FORM_GUARD__?.markSaved?.()
        this.$emit('saved', response.data)
      } catch (error) { if (this.alive) this.error = error.message || '保存失败，已保留填写内容' }
      finally { this.saving = false }
    }
  }
}
</script>

<style scoped>
.inspection-company { display: flex; justify-content: space-between; gap: 12px; margin: 0 0 18px; font-weight: 600; }
.inspection-company span, small { color: var(--text-secondary); font-weight: 400; }
.inspection-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px 18px; border: 0; padding: 0; margin: 0 0 24px; min-width: 0; }
.inspection-fields legend { padding: 0 0 12px; font-weight: 600; }
.inspection-fields :deep(.app-form-item) { margin: 0; }
.inspection-fields :deep(.app-form-item__label) { line-height: 22px; margin-bottom: 6px; }
.inspection-full { grid-column: 1 / -1; }
.inspection-evidence h3, .inspection-review h3 { font-size: 14px; }
.inspection-evidence { display: grid; gap: 12px; }
.inspection-summary { margin-bottom: 20px; background: var(--card, #fff); border: 1px solid var(--border-base); border-radius: 8px; }
.inspection-summary :deep(.app-desc-list__value) { white-space: pre-wrap; }
.inspection-remove { display: flex; gap: 10px; flex-wrap: wrap; }
.inspection-remove button { border: 0; background: none; color: var(--text-secondary); cursor: pointer; }
.inspection-conflict { margin: 12px 0; padding: 14px; background: var(--warning-50, #fff8eb); border: 1px solid var(--warning-200, #eed4a0); border-radius: 8px; }
@media (max-width: 640px) { .inspection-fields { grid-template-columns: 1fr; } }
</style>
