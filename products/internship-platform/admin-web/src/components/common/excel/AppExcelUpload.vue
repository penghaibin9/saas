<template>
  <div class="axu">
    <div class="axu__tpl" v-if="templateName || $slots.tpl">
      <div>
        <div class="axu__tpl-name">{{ templateName || 'Excel 模板' }}</div>
        <div v-if="requiredText" class="axu__tpl-hint">必填字段：{{ requiredText }}</div>
        <slot name="tpl" />
      </div>
      <AppButton variant="secondary" :loading="templateLoading" @click="$emit('download-template')">
        下载 Excel 模板
      </AppButton>
    </div>

    <label class="axu__upload">
      <input type="file" :accept="accept" class="axu__file" @change="onFile" />
      <span class="axu__upload-icon">⇪</span>
      <span>{{ fileName || '点击选择 Excel 文件（.xlsx）' }}</span>
    </label>
    <p v-if="error" class="axu__error">{{ error }}</p>
  </div>
</template>

<script>
/**
 * AppExcelUpload — 公共 Excel 上传选择器（底座前端组件）。
 * 只负责「下载模板 + 选择 .xlsx 文件」，不含业务；选中后 emit('file', File)。
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'AppExcelUpload',
  components: { AppButton },
  props: {
    templateName: { type: String, default: '' },
    requiredFields: { type: [String, Array], default: '' },
    accept: { type: String, default: '.xlsx,.xls' },
    templateLoading: { type: Boolean, default: false }
  },
  emits: ['file', 'download-template'],
  data() {
    return { fileName: '', error: '' }
  },
  computed: {
    requiredText() {
      return Array.isArray(this.requiredFields) ? this.requiredFields.join('、') : this.requiredFields
    }
  },
  methods: {
    reset() {
      this.fileName = ''
      this.error = ''
    },
    onFile(e) {
      const f = e.target.files?.[0]
      this.error = ''
      if (!f) return
      if (!/\.xlsx?$/i.test(f.name)) {
        this.error = '仅支持 .xlsx 格式文件（学校正式导入请使用 Excel 模板）'
        return
      }
      this.fileName = f.name
      this.$emit('file', f)
    }
  }
}
</script>

<style scoped>
.axu__tpl {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-section-blue);
}
.axu__tpl-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
.axu__tpl-hint {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.axu__upload {
  margin-top: var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-8) var(--space-4);
  border: 1.5px dashed var(--border-base);
  border-radius: var(--radius-md);
  color: var(--text-tertiary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: border-color var(--motion-fast) var(--ease-standard);
}
.axu__upload:hover {
  border-color: var(--primary-500);
  color: var(--primary-600);
}
.axu__upload-icon {
  font-size: 22px;
}
.axu__file {
  display: none;
}
.axu__error {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-xs);
  color: var(--danger-600);
}
</style>
