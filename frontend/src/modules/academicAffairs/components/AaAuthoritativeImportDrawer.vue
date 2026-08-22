<template>
  <div v-if="visible" class="aai-mask" @click.self="close">
    <section class="aai" role="dialog" aria-modal="true" :aria-label="title">
      <header class="aai-head">
        <div>
          <h3>{{ title }}</h3>
          <p>原文件进入 FileObject 安全扫描，浏览器只展示服务端预检；正式确认只发送 jobId + expectedVersion。</p>
        </div>
        <button type="button" aria-label="关闭" class="aai-close" @click="close">×</button>
      </header>

      <div class="aai-body">
        <AppInlineAlert
          type="info"
          title="服务器权威导入"
          description="失败行、冲突、任务版本和最终写入结果全部以后端为准；浏览器 rows 不参与正式写库。"
        />

        <div v-if="phaseLabel" class="aai-phase">当前阶段：<strong>{{ phaseLabel }}</strong></div>

        <div v-if="showImportMode" class="aai-mode">
          <div class="aai-label">导入策略</div>
          <label>
            <input v-model="importMode" type="radio" value="ATOMIC" :disabled="busy || !!job" />
            <span><strong>整批原子导入（推荐）</strong><small>任一行失败，整批不写入。</small></span>
          </label>
          <label>
            <input v-model="importMode" type="radio" value="PARTIAL" :disabled="busy || !!job" />
            <span><strong>合法行优先导入</strong><small>只提交服务端判定可写的合法行；失败行保留到服务器错误清单。</small></span>
          </label>
          <AppInlineAlert
            v-if="importMode === 'PARTIAL'"
            type="warning"
            description="PARTIAL 会形成部分成功的正式事实。确认前请核对合法/失败数量，并下载服务器错误清单留档。"
          />
        </div>

        <div class="aai-upload">
          <div>
            <div class="aai-label">1. 下载模板</div>
            <p>{{ templateName }}</p>
          </div>
          <AppButton :loading="templateBusy" :disabled="busy" @click="downloadTemplate">下载导入模板</AppButton>
        </div>

        <div class="aai-upload">
          <div class="aai-file">
            <div class="aai-label">2. 上传原始 XLSX</div>
            <input ref="fileInput" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" :disabled="busy || !!job" @change="onFile" />
            <p v-if="file">{{ file.name }} · {{ fileSize(file.size) }}</p>
          </div>
          <AppButton variant="primary" :loading="busy && !job" :disabled="!file || busy || !!job" @click="upload">上传并服务端预检</AppButton>
        </div>

        <div v-if="job" class="aai-job">
          <div class="aai-label">3. ImportJob 权威状态</div>
          <dl>
            <div><dt>任务号</dt><dd>#{{ job.id }}</dd></div>
            <div><dt>状态</dt><dd><AppStatusTag :type="statusType(job.status)" :label="statusLabel(job.status)" dot /></dd></div>
            <div><dt>任务版本</dt><dd>{{ job.version }}</dd></div>
            <div><dt>总行数</dt><dd>{{ preview.total }}</dd></div>
            <div><dt>合法</dt><dd>{{ preview.validRows }}</dd></div>
            <div><dt>失败</dt><dd>{{ preview.invalidRows }}</dd></div>
          </dl>
          <p v-if="job.errorMessage" class="aai-error">{{ job.errorMessage }}</p>
          <p v-if="polling" class="aai-note">安全扫描 / 服务端预检进行中，扫描通过前不会开放确认。</p>
        </div>

        <div v-if="job && preview.rows.length" class="aai-preview">
          <div class="aai-label">4. 服务端预检只读结果</div>
          <AppImportPreviewTable :rows="preview.rows" :errors="preview.errors" :preview-fields="previewFields" />
        </div>

        <div v-if="job && preview.invalidRows > 0" class="aai-errors">
          <AppImportErrorSummary
            :total="preview.total"
            :valid-rows="preview.validRows"
            :invalid-rows="preview.invalidRows"
            :downloading="errorBusy"
            @download-errors="downloadServerErrors"
          />
          <p class="aai-note">错误清单由服务器保存的 ImportRowError 生成，不使用浏览器 rows/errors 拼文件。</p>
        </div>

        <AppInlineAlert v-if="message" :type="messageType" :description="message" />
      </div>

      <footer class="aai-foot">
        <AppButton variant="ghost" :disabled="busy" @click="reset">重新选择文件</AppButton>
        <AppButton variant="ghost" :disabled="busy" @click="close">关闭</AppButton>
        <AppButton
          variant="primary"
          :loading="confirmBusy"
          :disabled="!canConfirm || busy"
          @click="confirm"
        >确认导入{{ preview.validRows ? ` ${preview.validRows} 条合法数据` : '' }}</AppButton>
      </footer>
    </section>
  </div>
</template>

<script>
import { AppButton } from '@/components/ui'
import { AppInlineAlert, AppStatusTag } from '@/components/common'
import { AppImportErrorSummary, AppImportPreviewTable } from '@/components/common/excel'
import { academicFileExchangeApi } from '@/modules/academicAffairs/api/academic-file-exchange.api'

const TERMINAL = new Set(['VALIDATED', 'VALIDATION_FAILED', 'FAILED', 'EXPIRED', 'SUCCEEDED'])
const EMPTY_PREVIEW = Object.freeze({ total: 0, validRows: 0, invalidRows: 0, rows: [], errors: [] })
const sleep = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))

function saveBlob(blob, filename) {
  const href = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = href
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(href)
}

export default {
  name: 'AaAuthoritativeImportDrawer',
  components: { AppButton, AppInlineAlert, AppStatusTag, AppImportErrorSummary, AppImportPreviewTable },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '权威 Excel 导入' },
    templateName: { type: String, default: '导入模板.xlsx' },
    previewFields: { type: Array, default: () => [] },
    phaseLabel: { type: String, default: '' },
    showImportMode: { type: Boolean, default: false },
    downloadTemplateFn: { type: Function, required: true },
    uploadFn: { type: Function, required: true }
  },
  emits: ['update:visible', 'imported'],
  data() {
    return {
      file: null,
      importMode: 'ATOMIC',
      job: null,
      preview: { ...EMPTY_PREVIEW },
      polling: false,
      templateBusy: false,
      uploadBusy: false,
      confirmBusy: false,
      errorBusy: false,
      message: '',
      messageType: 'info'
    }
  },
  computed: {
    busy() { return this.uploadBusy || this.confirmBusy || this.errorBusy },
    canConfirm() {
      if (!this.job || this.polling) return false
      if (this.job.canConfirm === true) return Number(this.preview.validRows || 0) > 0
      return this.job.status === 'VALIDATED' && Number(this.preview.invalidRows || 0) === 0 && Number(this.preview.validRows || 0) > 0
    }
  },
  watch: {
    visible(value) { if (value) this.reset() }
  },
  methods: {
    close() { this.$emit('update:visible', false) },
    reset() {
      this.file = null
      this.importMode = 'ATOMIC'
      this.job = null
      this.preview = { ...EMPTY_PREVIEW }
      this.polling = false
      this.message = ''
      this.messageType = 'info'
      if (this.$refs.fileInput) this.$refs.fileInput.value = ''
    },
    onFile(event) { this.file = event?.target?.files?.[0] || null },
    fileSize(size) {
      const bytes = Number(size || 0)
      if (bytes < 1024) return `${bytes} B`
      if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
      return `${(bytes / 1024 / 1024).toFixed(1)} MB`
    },
    statusLabel(status) {
      return {
        SCANNING: '安全扫描', PARSING: '服务端预检', VALIDATED: '预检通过',
        VALIDATION_FAILED: '预检存在失败行', CONFIRMING: '确认中', SUCCEEDED: '已完成',
        FAILED: '失败', EXPIRED: '已过期'
      }[status] || status || '未知'
    },
    statusType(status) {
      if (['VALIDATED', 'SUCCEEDED'].includes(status)) return 'success'
      if (['VALIDATION_FAILED', 'FAILED', 'EXPIRED'].includes(status)) return 'danger'
      if (['SCANNING', 'PARSING', 'CONFIRMING'].includes(status)) return 'primary'
      return 'default'
    },
    syncJob(item) {
      const source = item || {}
      const serverPreview = source.preview || {}
      this.job = {
        ...source,
        id: source.id,
        version: source.version,
        status: source.status,
        canConfirm: source.canConfirm === true,
        errorMessage: source.errorMessage || ''
      }
      this.preview = {
        total: Number(serverPreview.totalRows ?? source.totalRows ?? 0),
        validRows: Number(serverPreview.validRows ?? source.validRows ?? 0),
        invalidRows: Number(serverPreview.invalidRows ?? source.invalidRows ?? 0),
        rows: Array.isArray(serverPreview.rows) ? serverPreview.rows : [],
        errors: Array.isArray(serverPreview.errors) ? serverPreview.errors : []
      }
    },
    async downloadTemplate() {
      if (this.templateBusy) return
      this.templateBusy = true
      this.message = ''
      try {
        const result = await this.downloadTemplateFn()
        if (result?.code != null && result.code !== 0) throw new Error(result.message || '模板下载失败')
        const payload = result?.code === 0 ? result.data : result
        if (payload instanceof Blob) saveBlob(payload, this.templateName)
      } catch (error) {
        this.messageType = 'danger'
        this.message = error?.message || '模板下载失败'
      } finally {
        this.templateBusy = false
      }
    },
    async upload() {
      if (!this.file || this.uploadBusy) return
      this.uploadBusy = true
      this.message = ''
      try {
        const result = await this.uploadFn(this.file, this.importMode)
        if (!result || result.code !== 0) throw new Error(result?.message || '文件上传失败')
        this.syncJob(result.data)
        if (!TERMINAL.has(this.job.status)) await this.pollUntilTerminal()
        this.messageType = this.canConfirm ? 'success' : (this.preview.invalidRows ? 'warning' : 'info')
        this.message = this.canConfirm
          ? '服务端权威预检完成，可确认导入。'
          : (this.job?.errorMessage || '当前任务不可确认，请根据服务端结果处理后重新上传。')
      } catch (error) {
        this.messageType = 'danger'
        this.message = error?.message || '服务端预检失败'
      } finally {
        this.uploadBusy = false
      }
    },
    async pollUntilTerminal() {
      this.polling = true
      try {
        for (let attempt = 0; attempt < 60 && this.job && !TERMINAL.has(this.job.status); attempt += 1) {
          await sleep(1500)
          const detail = await academicFileExchangeApi.getImportJob(this.job.id)
          if (detail.code !== 0) throw new Error(detail.message || '导入任务读取失败')
          this.syncJob(detail.data)
        }
        if (this.job && !TERMINAL.has(this.job.status)) {
          throw new Error('文件仍在后台安全扫描，请稍后重新打开任务继续处理')
        }
      } finally {
        this.polling = false
      }
    },
    async confirm() {
      if (!this.canConfirm || !this.job || this.confirmBusy) return
      this.confirmBusy = true
      this.message = ''
      try {
        const result = await academicFileExchangeApi.confirmImport(this.job.id, this.job.version)
        if (result.code !== 0) throw new Error(result.message || '确认导入失败')
        this.syncJob(result.data)
        this.messageType = 'success'
        this.message = '导入已由服务器确认完成，页面将回读正式数据。'
        this.$emit('imported', result.data)
      } catch (error) {
        this.messageType = 'danger'
        this.message = error?.message || '确认导入失败'
        const detail = this.job?.id ? await academicFileExchangeApi.getImportJob(this.job.id) : null
        if (detail?.code === 0) this.syncJob(detail.data)
      } finally {
        this.confirmBusy = false
      }
    },
    async downloadServerErrors() {
      if (!this.job?.id || this.errorBusy) return
      this.errorBusy = true
      this.message = ''
      try {
        const exported = await academicFileExchangeApi.exportImportErrors(this.job.id)
        if (exported.code !== 0) throw new Error(exported.message || '错误清单生成失败')
        const exportJob = exported.data || {}
        const ticket = await academicFileExchangeApi.createExportDownloadTicket(exportJob.id, exportJob.version)
        if (ticket.code !== 0) throw new Error(ticket.message || '错误清单下载票据创建失败')
        const downloaded = await academicFileExchangeApi.downloadExport(ticket.data.downloadUrl)
        if (downloaded.code !== 0) throw new Error(downloaded.message || '错误清单下载失败')
        saveBlob(downloaded.data, `${this.templateName.replace(/\.xlsx$/i, '')}-错误清单.xlsx`)
        this.messageType = 'success'
        this.message = '服务器权威错误清单已下载；一次性票据已消费。'
      } catch (error) {
        this.messageType = 'danger'
        this.message = error?.message || '错误清单下载失败'
      } finally {
        this.errorBusy = false
      }
    }
  }
}
</script>

<style scoped>
.aai-mask { position: fixed; inset: 0; z-index: var(--z-modal, 1000); background: var(--bg-mask, rgba(15,23,42,.45)); display: flex; align-items: center; justify-content: center; padding: 20px; }
.aai { width: min(980px, 100%); max-height: calc(100vh - 40px); display: flex; flex-direction: column; overflow: hidden; background: var(--bg-card, #fff); border: 1px solid var(--border-light, #e5e7eb); border-radius: 16px; box-shadow: 0 24px 70px rgba(15,23,42,.22); }
.aai-head { display: flex; justify-content: space-between; gap: 16px; padding: 18px 22px; border-bottom: 1px solid var(--border-light, #e5e7eb); }
.aai-head h3 { margin: 0; font-size: 18px; }
.aai-head p, .aai-note { margin: 6px 0 0; color: var(--text-tertiary, #64748b); font-size: 12px; }
.aai-close { border: 0; background: none; font-size: 24px; cursor: pointer; color: var(--text-tertiary, #64748b); }
.aai-body { display: grid; gap: 14px; padding: 18px 22px; overflow: auto; }
.aai-phase { padding: 10px 12px; border-radius: 8px; background: var(--bg-section-blue, #eff6ff); font-size: 13px; }
.aai-label { font-size: 13px; font-weight: 600; color: var(--text-primary, #1f2937); }
.aai-upload { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 12px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 10px; }
.aai-upload p { margin: 4px 0 0; font-size: 12px; color: var(--text-tertiary, #64748b); }
.aai-file { min-width: 0; }
.aai-file input { margin-top: 8px; max-width: 100%; }
.aai-mode { display: grid; gap: 8px; padding: 12px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 10px; }
.aai-mode label { display: flex; gap: 8px; align-items: flex-start; }
.aai-mode label span { display: flex; flex-direction: column; gap: 2px; font-size: 13px; }
.aai-mode small { color: var(--text-tertiary, #64748b); }
.aai-job { padding: 12px; border: 1px solid var(--border-light, #e5e7eb); border-radius: 10px; }
.aai-job dl { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 10px; margin: 10px 0 0; }
.aai-job dl > div { min-width: 0; }
.aai-job dt { font-size: 12px; color: var(--text-tertiary, #64748b); }
.aai-job dd { margin: 3px 0 0; font-size: 14px; font-weight: 600; overflow-wrap: anywhere; }
.aai-error { color: var(--danger-600, #dc2626); font-size: 12px; }
.aai-preview, .aai-errors { display: grid; gap: 8px; }
.aai-foot { display: flex; justify-content: flex-end; gap: 8px; padding: 14px 22px; border-top: 1px solid var(--border-light, #e5e7eb); }
@media (max-width: 720px) { .aai-mask { padding: 10px; } .aai { max-height: calc(100vh - 20px); } .aai-upload { align-items: stretch; flex-direction: column; } .aai-job dl { grid-template-columns: repeat(2, minmax(0,1fr)); } .aai-foot { flex-wrap: wrap; } }
</style>
