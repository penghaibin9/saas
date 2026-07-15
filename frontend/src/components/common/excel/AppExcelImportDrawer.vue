<template>
  <div v-if="visible" class="aeid__mask" @click.self="close">
    <div class="aeid" role="dialog" aria-modal="true">
      <header class="aeid__header">
        <h3>{{ title }}</h3>
        <button type="button" class="aeid__close" aria-label="关闭" @click="close">×</button>
      </header>

      <div class="aeid__steps">
        <span
          v-for="(s, i) in steps"
          :key="s"
          class="aeid__step"
          :class="{ 'is-active': step === i, 'is-done': step > i }"
        >{{ i + 1 }}. {{ s }}</span>
      </div>

      <div class="aeid__body">
        <AccountImportBoundaryNotice v-if="showAccountBoundary" class="aeid__boundary" />

        <!-- Step 0：模板 + 上传 -->
        <AppExcelUpload
          v-if="step === 0"
          ref="uploader"
          :template-name="templateName"
          :required-fields="requiredFields"
          :template-loading="templateBusy"
          @file="onFile"
          @download-template="downloadTemplate"
        />

        <!-- Step 1：预校验预览 -->
        <div v-else-if="step === 1">
          <AppImportErrorSummary
            :total="pre.total"
            :valid-rows="pre.validRows"
            :invalid-rows="pre.invalidRows"
            :downloading="errBusy"
            @download-errors="downloadErrors"
          />
          <AppImportPreviewTable
            :rows="pre.rows"
            :errors="pre.errors"
            :preview-fields="previewFields"
          />
        </div>

        <!-- Step 2：回执 -->
        <div v-else class="aeid__result">
          <div class="aeid__result-icon">✓</div>
          <div class="aeid__result-title">导入完成</div>
          <div class="aeid__result-desc">成功导入 {{ result?.created ?? 0 }} 条数据，失败数据未导入。</div>
          <div class="aeid__result-audit">本次导入已写入审计与导入记录，可在「通用导入记录」中查看。</div>
        </div>
      </div>

      <footer class="aeid__footer">
        <AppButton variant="ghost" @click="close">{{ step === 2 ? '关闭' : '取消' }}</AppButton>
        <AppButton
          v-if="step === 0"
          variant="primary"
          :disabled="!selectedFile"
          :loading="busy"
          @click="doPreValidate"
        >预校验</AppButton>
        <AppButton
          v-if="step === 1"
          variant="primary"
          :disabled="!pre.validRows || pre.invalidRows > 0"
          :loading="busy"
          @click="doConfirm"
        >确认导入 {{ pre.validRows }} 条</AppButton>
      </footer>
    </div>
  </div>
</template>

<script>
/**
 * AppExcelImportDrawer — 公共 Excel 导入抽屉（底座前端主组件）。
 * 统一「下载 Excel 模板 → 上传 Excel → 预校验 → 下载错误行 Excel → 确认导入」全流程。
 * 页面只注入 4 个后端调用，不再各写一套导入弹窗：
 *  - downloadTemplateFn: () => Promise            下载 Excel 模板（后端 blob）
 *  - uploadFn: (File) => Promise<res>             上传 .xlsx，res.data 为统一预校验结构
 *      { total, validRows, invalidRows, passed, rows, errors }
 *  - confirmFn: ({ rows }) => Promise<res>        确认导入，res.data.created 为成功条数
 *  - downloadErrorsFn?: ({ rows, errors }) => Promise<res>  下载错误行 Excel（后端 pack 结构）
 * 严格口径：预校验有失败行时禁止确认；写操作不 mock 成功（由页面注入的真实接口负责）。
 */
import { AppButton } from '@/components/ui'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { toast } from '@/utils/toast'
import AccountImportBoundaryNotice from '@/components/common/AccountImportBoundaryNotice.vue'
import AppExcelUpload from './AppExcelUpload.vue'
import AppImportPreviewTable from './AppImportPreviewTable.vue'
import AppImportErrorSummary from './AppImportErrorSummary.vue'

const EMPTY_PRE = { total: 0, validRows: 0, invalidRows: 0, passed: false, rows: [], errors: [] }

export default {
  name: 'AppExcelImportDrawer',
  components: { AppButton, AccountImportBoundaryNotice, AppExcelUpload, AppImportPreviewTable, AppImportErrorSummary },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '批量导入' },
    templateName: { type: String, default: 'Excel 模板' },
    showAccountBoundary: { type: Boolean, default: false },
    requiredFields: { type: [String, Array], default: '' },
    previewFields: { type: Array, default: () => [] },
    downloadTemplateFn: { type: Function, default: null },
    uploadFn: { type: Function, required: true },
    confirmFn: { type: Function, required: true },
    downloadErrorsFn: { type: Function, default: null }
  },
  emits: ['update:visible', 'imported'],
  data() {
    return {
      steps: ['上传文件', '预校验', '导入回执'],
      step: 0,
      selectedFile: null,
      busy: false,
      templateBusy: false,
      errBusy: false,
      pre: { ...EMPTY_PRE },
      result: null
    }
  },
  watch: {
    visible(v) {
      if (v) Object.assign(this, { step: 0, selectedFile: null, pre: { ...EMPTY_PRE }, result: null })
    }
  },
  methods: {
    close() {
      this.$emit('update:visible', false)
    },
    onFile(f) {
      this.selectedFile = f
    },
    async downloadTemplate() {
      if (!this.downloadTemplateFn) return
      this.templateBusy = true
      try {
        await this.downloadTemplateFn()
      } catch (e) {
        toast.error(e?.message || '模板下载失败')
      } finally {
        this.templateBusy = false
      }
    },
    async doPreValidate() {
      if (!this.selectedFile) return
      this.busy = true
      try {
        const res = await this.uploadFn(this.selectedFile)
        if (res?.code === 0) {
          this.pre = { ...EMPTY_PRE, ...res.data }
          this.step = 1
        } else {
          toast.error(res?.message || '预校验失败')
        }
      } catch (e) {
        toast.error(e?.message || '预校验失败')
      } finally {
        this.busy = false
      }
    },
    async downloadErrors() {
      if (!this.downloadErrorsFn) {
        toast.info('未配置错误行下载')
        return
      }
      this.errBusy = true
      try {
        const res = await this.downloadErrorsFn({ rows: this.pre.rows, errors: this.pre.errors })
        if (res?.code === 0) downloadXlsxFromApi(res.data)
        else toast.error(res?.message || '错误行下载失败')
      } catch (e) {
        toast.error(e?.message || '错误行下载失败')
      } finally {
        this.errBusy = false
      }
    },
    async doConfirm() {
      if (this.pre.invalidRows > 0) {
        toast.error('存在未通过预校验的行，请先修正后重新上传')
        return
      }
      this.busy = true
      try {
        const res = await this.confirmFn({ rows: this.pre.rows })
        if (res?.code === 0) {
          this.result = res.data
          this.step = 2
          this.$emit('imported', res.data)
        } else {
          toast.error(res?.message || '导入失败')
        }
      } catch (e) {
        toast.error(e?.message || '导入失败')
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.aeid__mask {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 1000);
  background: var(--bg-mask);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}
.aeid__boundary {
  margin-bottom: var(--space-4);
}
.aeid {
  width: min(680px, 100%);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.aeid__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.aeid__header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
}
.aeid__close {
  border: none;
  background: none;
  font-size: 22px;
  color: var(--text-tertiary);
  cursor: pointer;
}
.aeid__steps {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-5);
  background: var(--bg-section-blue);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.aeid__step.is-active {
  color: var(--primary-600);
  font-weight: var(--font-weight-semibold);
}
.aeid__step.is-done {
  color: var(--success-600);
}
.aeid__body {
  padding: var(--space-5);
  overflow-y: auto;
}
.aeid__result {
  text-align: center;
  padding: var(--space-6) 0;
}
.aeid__result-icon {
  width: 48px;
  height: 48px;
  margin: 0 auto var(--space-3);
  border-radius: var(--radius-full);
  background: var(--success-50);
  color: var(--success-600);
  font-size: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.aeid__result-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}
.aeid__result-desc {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.aeid__result-audit {
  margin-top: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.aeid__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-light);
}
</style>
