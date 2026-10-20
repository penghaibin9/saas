<template>
  <section class="aa-proof" aria-label="形成方式依据核实">
    <header><h4>核实形成方式依据</h4><button type="button" :disabled="saving" @click="$emit('close')">收起补证</button></header>
    <p>每份来源分别核实，由校教务责任人依据学校正式材料确认。确认后保留原任务、来源字段和历史办理记录。</p>
    <p v-if="loading" role="status">正在读取正式来源和确认责任…</p>
    <p v-if="error" role="alert" class="aa-proof__error">{{ error }}</p>
    <button type="button" :disabled="loading || saving" @click="load">重新读取并核对来源</button>
    <p v-if="receipt" role="status">{{ receipt }}</p>
    <div v-if="result">
      <p><strong>{{ result.programName || '来源方案待核对' }} · 第{{ result.programVersion ?? '待核对' }}版 · {{ result.courseName || '课程待核对' }}</strong></p>
      <p>原始记录：{{ result.originalFormationModeLabel || '尚未证明' }}；当前依据：{{ result.formationModeLabel || '尚未证明' }}</p>
      <article v-if="result.proof" class="aa-proof__receipt">
        <strong>历史确认记录：{{ result.proof.formationModeLabel }}</strong>
        <p :role="result.proofValid === false ? 'alert' : 'status'">依据有效性：{{ result.proofValidityLabel || '有效性待核对' }}</p>
        <p>材料定位：{{ result.proof.evidenceLocator || '待核对' }}</p><p>依据说明：{{ result.proof.reason }}</p><p>确认时间：{{ result.proof.confirmedAt }}</p>
        <FilePreviewer v-if="result.proof.evidence" :file="result.proof.evidence" @error="onFileError" />
      </article>
      <div v-if="!canConfirm"><p>确认责任：校教务处正式责任人。</p><ul><li v-for="blocker in result.confirmationBlockers" :key="blocker.code">{{ blocker.message }}</li></ul><p v-if="!result.confirmationBlockers?.length && !result.proof">当前身份或来源条件不允许确认，请由校教务责任人核对。</p></div>
      <form v-if="canConfirm" @submit.prevent="openConfirmation">
        <fieldset :disabled="saving || loading">
          <label>选择形成方式<select v-model="form.formationMode"><option value="">请依据学校材料明确选择</option><option v-for="mode in modes" :key="mode.value" :value="mode.value">{{ mode.label }}</option></select></label>
          <label>正式依据材料（必填）<FileUploader :key="scopeKey" biz-type="ATTACHMENT" :disabled="saving || loading" button-text="上传正式依据材料" @uploaded="onUploaded" @progress="onUploadProgress" @error="onFileError" @cancelled="onUploadCancelled" /></label>
          <p v-if="uploadMessage" role="status">{{ uploadMessage }}</p>
          <FilePreviewer v-if="uploadedFile" :file="uploadedFile" @error="onFileError" />
          <button v-if="uploadedFile && uploadedFile.readyForBusiness !== true" type="button" :disabled="checkingFile" @click="refreshFile">重新核对文件安全状态</button>
          <label>材料页码、行号或章节定位（必填）<input v-model="form.evidenceLocator" maxlength="300" placeholder="例如：第3页第2节或表格第5行" /></label>
          <label>形成方式依据说明（必填）<textarea v-model="form.reason" maxlength="500" placeholder="说明材料如何证明本份方案课程的形成方式，至少5个字" /></label>
          <button type="submit" :disabled="uploading || checkingFile">核对并确认本份来源依据</button>
        </fieldset>
      </form>
    </div>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认本份形成方式依据" :message="confirmMessage" confirm-text="只确认本份来源依据" :submitting="saving" :confirm-disabled="!canConfirm || uploading || checkingFile" @confirm="confirmProof" />
  </section>
</template>

<script>
import FileUploader from '@/components/file/FileUploader.vue'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { fileSdk } from '@/services/file/fileSdk'
import { teachingTaskWorkbenchApi } from '../../api/teaching-task-workbench.api.js'

export default {
  name: 'AaFormationProof', components: { FileUploader, FilePreviewer, AppConfirmDialog },
  props: { programCourseId: { type: String, required: true }, contextKey: { type: String, required: true } }, emits: ['confirmed', 'close'],
  data() { return { result: null, form: { formationMode: '', evidenceLocator: '', reason: '' }, uploadedFile: null, uploadMessage: '', uploading: false, checkingFile: false, loading: false, saving: false, error: '', receipt: '', confirmVisible: false, needsReload: false, confirmationSubmitted: false, requestSeq: 0, disposed: false, commandKey: '', commandIdentity: '', modes: [{ value: 'ADMIN_FIXED', label: '固定行政班' }, { value: 'SELECTABLE', label: '学生自主选课' }, { value: 'MERGED', label: '合班' }, { value: 'RETAKE', label: '重修' }, { value: 'LAYERED', label: '分层' }] } },
  computed: {
    scopeKey() { return JSON.stringify([this.contextKey, this.programCourseId]) },
    canConfirm() { return this.result?.canConfirm === true && !this.result.proof && !this.needsReload && !this.confirmationSubmitted },
    confirmMessage() { const label = this.modes.find(mode => mode.value === this.form.formationMode)?.label || '待核对'; return `${this.result?.programName || '当前方案'}第${this.result?.programVersion ?? '待核对'}版 · ${this.result?.courseName || '当前课程'}：确认依据为“${label}”。材料定位：${this.form.evidenceLocator}。本次只为这一份来源补充正式依据，不修改原任务或来源，不确认另一份、不办理承接或发布。` }
  },
  watch: { scopeKey: { immediate: true, handler() { this.resetScope(); this.load() } } },
  beforeUnmount() { this.disposed = true; this.resetScope() },
  methods: {
    resetScope() { this.requestSeq++; this.result = null; this.form = { formationMode: '', evidenceLocator: '', reason: '' }; this.uploadedFile = null; this.error = ''; this.receipt = ''; this.uploadMessage = ''; this.uploading = false; this.checkingFile = false; this.loading = false; this.saving = false; this.confirmVisible = false; this.needsReload = false; this.confirmationSubmitted = false; this.commandKey = ''; this.commandIdentity = '' },
    async load() {
      if (this.saving || this.disposed) return
      const seq = ++this.requestSeq, scope = this.scopeKey
      const current = () => !this.disposed && seq === this.requestSeq && scope === this.scopeKey
      this.result = null; this.error = ''; this.loading = true; this.confirmVisible = false
      try {
        const response = await teachingTaskWorkbenchApi.getFormationProof(this.programCourseId)
        if (!current()) return
        if (response.code !== 0) throw new Error(response.message || '形成方式依据读取失败')
        if (String(response.data?.programCourseId) !== this.programCourseId || !/^[a-fA-F0-9]{64}$/.test(response.data?.sourceFingerprint || '')) throw new Error('来源对象或版本未能核对，请重新读取')
        this.result = response.data; this.needsReload = false
      } catch (error) { if (current()) this.error = error?.message || '依据读取失败，请重新读取' } finally { if (current()) this.loading = false }
    },
    onUploaded(file) { this.uploading = false; this.uploadedFile = file; this.uploadMessage = file?.readyForBusiness === true && /^[1-9]\d*$/.test(String(file?.fileId || '')) ? '材料已上传并安全就绪，可继续核对依据' : '材料尚未安全就绪，扫描待完成；请重新核对安全状态后再确认' },
    onUploadProgress() { this.uploading = true; this.uploadedFile = null; this.uploadMessage = '正在上传正式依据材料…' },
    onUploadCancelled() { this.uploading = false; this.uploadMessage = '上传已取消，请重新选择依据材料' },
    onFileError(error) { this.uploading = false; this.error = error?.message || '依据文件处理失败，请核对后重试' },
    async refreshFile() {
      if (!this.uploadedFile?.fileId || this.checkingFile || this.saving) return
      const scope = this.scopeKey, fileId = String(this.uploadedFile.fileId)
      this.checkingFile = true
      try { const file = await fileSdk.metadata(fileId); if (!this.disposed && scope === this.scopeKey && String(this.uploadedFile?.fileId) === fileId) this.onUploaded(file) } catch (error) { if (!this.disposed && scope === this.scopeKey) this.onFileError(error) } finally { if (!this.disposed && scope === this.scopeKey) this.checkingFile = false }
    },
    validate() {
      if (!this.canConfirm) return '当前身份或来源条件不允许确认，请由校教务责任人核对'
      if (!this.modes.some(mode => mode.value === this.form.formationMode)) return '请依据学校材料明确选择形成方式'
      if (this.uploading || this.checkingFile || this.uploadedFile?.readyForBusiness !== true || !/^[1-9]\d*$/.test(String(this.uploadedFile?.fileId || ''))) return '正式依据文件尚未安全就绪，不能确认'
      if (this.form.evidenceLocator.trim().length < 2 || this.form.evidenceLocator.trim().length > 300) return '请填写2至300字的材料页、行或章节定位'
      if (this.form.reason.trim().length < 5 || this.form.reason.trim().length > 500) return '请填写5至500字的形成方式依据说明'
      return ''
    },
    openConfirmation() { if (this.saving || this.loading) return; this.error = this.validate(); if (!this.error) this.confirmVisible = true },
    async confirmProof() {
      if (this.saving || this.loading || !this.confirmVisible) return
      this.error = this.validate(); if (this.error) return
      const scope = this.scopeKey, seq = this.requestSeq
      const current = () => !this.disposed && scope === this.scopeKey && seq === this.requestSeq
      const body = { formationMode: this.form.formationMode, evidenceFileId: String(this.uploadedFile.fileId), evidenceLocator: this.form.evidenceLocator.trim(), reason: this.form.reason.trim(), expectedSourceFingerprint: this.result.sourceFingerprint }
      const identity = JSON.stringify(body)
      if (identity !== this.commandIdentity || !this.commandKey) { this.commandIdentity = identity; this.commandKey = globalThis.crypto.randomUUID() }
      body.idempotencyKey = this.commandKey
      this.saving = true; this.receipt = ''
      try {
        const response = await teachingTaskWorkbenchApi.confirmFormationProof(this.programCourseId, body)
        if (!current()) return
        if (response.code !== 0) {
          if (response.httpStatus === 409 || response.code === 'DATA_CONFLICT') { this.needsReload = true; this.confirmVisible = false; this.error = `${response.message || '来源或依据已变化'}；已保留输入，请重新读取并核对后再确认` }
          else this.error = response.message || '确认失败，已保留输入，请核对后重试'
          return
        }
        this.confirmVisible = false; this.confirmationSubmitted = true; this.receipt = '来源确认请求已完成；正在重新读取持久结果。'; this.saving = false
        await this.load()
        if (this.disposed || scope !== this.scopeKey) return
        if (!this.result?.proof) this.receipt = '正式确认已提交，回执尚未读回；请重新读取核对，勿重复确认。'
        else if (this.result.proofValid === true) this.receipt = '本份来源依据已正式确认，并已重新读取有效的正式回执。'
        else this.receipt = this.result.proofValid === false ? '历史确认记录已读取，但当前依据已失效；请核对下方失效原因。' : '确认记录已读取，当前有效性尚未证明；请重新读取核对。'
        this.$emit('confirmed')
      } catch (error) { if (current()) this.error = error?.message || '确认请求失败，已保留输入，请核对后重试' } finally { if (!this.disposed && scope === this.scopeKey) this.saving = false }
    }
  }
}
</script>

<style scoped>
.aa-proof { margin-top: 16px; padding: 16px; border: 1px solid #dbe3ed; border-radius: 8px; background: #fff; }
.aa-proof header { display: flex; justify-content: space-between; gap: 12px; }
.aa-proof h4 { margin: 0; }
.aa-proof p { line-height: 1.6; overflow-wrap: anywhere; }
.aa-proof fieldset { border: 0; padding: 0; display: grid; gap: 12px; }
.aa-proof label { display: grid; gap: 8px; }
.aa-proof input, .aa-proof select, .aa-proof textarea { width: 100%; box-sizing: border-box; min-height: 36px; border: 1px solid #c7d2e0; border-radius: 5px; padding: 8px; }
.aa-proof button { min-height: 36px; padding: 6px 12px; border: 1px solid #c7d2e0; border-radius: 5px; background: white; color: #2d5cad; }
.aa-proof textarea { min-height: 90px; }
.aa-proof__error { color: #a33b22; }
.aa-proof__receipt { border-left: 3px solid #368056; padding-left: 12px; }
</style>
