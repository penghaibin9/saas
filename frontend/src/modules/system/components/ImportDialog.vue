<template>
  <AppDrawer :visible="visible" :title="'批量导入 · ' + (template.name || '')" @update:visible="$emit('update:visible', $event)">
    <div class="imp">
      <div class="imp__steps">
        <span v-for="(s, i) in ['下载模板', '上传并校验', '确认导入']" :key="s" class="imp__step" :class="{ 'is-on': step === i, 'is-done': step > i }">
          <i class="imp__step-no">{{ i + 1 }}</i>{{ s }}
        </span>
      </div>

      <template v-if="step === 0">
        <div class="mp-card">
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">模板文件</span><span class="mp-kv__v">{{ template.fileName }}（{{ template.version }}）</span></div>
            <div class="mp-kv"><span class="mp-kv__k">模板字段</span><span class="mp-kv__v">{{ (template.fields || []).join('、') }}</span></div>
          </div>
        </div>
        <ul class="imp__rules">
          <li v-for="r in template.rules" :key="r">{{ r }}</li>
        </ul>
        <AppButton variant="secondary" :loading="downloading" @click="downloadTemplate">
          ⇩ 下载标准 Excel 模板
        </AppButton>
      </template>

      <template v-else-if="step === 1">
        <label class="imp__upload">
          <input ref="fileInput" type="file" class="imp__file-input" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" @change="selectFile" />
          <span class="mp-note">仅支持标准 .xlsx；上传后执行 dry-run 预检，不会直接写入数据库</span>
          <span v-if="file" class="imp__filename">已选择：{{ file.name }}</span>
        </label>
        <div v-if="preview" class="imp__result">
          <div class="imp__stat">
            共 <b>{{ preview.total }}</b> 行 · 校验通过 <b class="is-ok">{{ preview.valid }}</b> · 存在错误 <b class="is-err">{{ preview.invalid }}</b>
          </div>
          <table v-if="preview.errors.length" class="mp-audit">
            <thead><tr><th>行号</th><th>字段</th><th>错误原因</th></tr></thead>
            <tbody>
              <tr v-for="(e, index) in preview.errors" :key="e.row + '-' + e.field + '-' + index"><td>{{ e.row ? '第 ' + e.row + ' 行' : '全局' }}</td><td>{{ e.field }}</td><td>{{ e.message }}</td></tr>
            </tbody>
          </table>
          <button v-if="preview.errors.length" class="mp-link" @click="downloadErrors">⇩ 下载 Excel 错误回执</button>
        </div>
      </template>

      <template v-else>
        <div class="mp-card">
          <div class="mp-card__body">
            <div class="mp-kv"><span class="mp-kv__k">导入批次</span><span class="mp-kv__v">{{ preview && preview.batchNo }}</span></div>
            <div class="mp-kv"><span class="mp-kv__k">写入范围</span><span class="mp-kv__v">仅校验通过的 {{ preview && preview.valid }} 行；错误行不写入</span></div>
            <div class="mp-kv"><span class="mp-kv__k">审计留痕</span><span class="mp-kv__v">导入回执与错误清单将写入操作日志</span></div>
          </div>
        </div>
        <p class="mp-note">确认后数据立即生效；如导入有误可在列表中按批次号筛选并逐条停用（不提供物理删除）。</p>
      </template>
    </div>
    <template #footer>
      <AppButton v-if="step > 0" variant="ghost" @click="step--">上一步</AppButton>
      <AppButton v-if="step === 0" variant="primary" @click="step = 1">下一步：上传文件</AppButton>
      <AppButton v-else-if="step === 1" variant="primary" :disabled="!file" :loading="checking" @click="runCheck">
        {{ preview ? '重新校验' : '开始校验' }}
      </AppButton>
      <AppButton v-if="step === 1 && preview && preview.invalid === 0" variant="primary" @click="step = 2">下一步：确认导入</AppButton>
      <AppButton v-if="step === 2" variant="primary" :loading="submitting" @click="confirmImport">确认导入 {{ preview && preview.valid }} 行</AppButton>
    </template>
  </AppDrawer>
</template>

<script>
/**
 * ImportDialog — 系统管理模块局部组件：三步导入流（模板下载 → 校验预览 → 导入回执）。
 * Props：template（importTemplates 中的一项）、runValidate(File)、runImport(batchNo) 为
 * 父页面传入的 api 调用（返回统一契约 Promise），组件内不直接 import api，保持模块内可复用。
 */
import { AppButton } from '@/components/ui'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { toast } from '@/utils/toast'

export default {
  name: 'SystemImportDialog',
  components: { AppButton, AppDrawer },
  props: {
    visible: { type: Boolean, default: false },
    template: { type: Object, required: true },
    runValidate: { type: Function, required: true },
    runImport: { type: Function, required: true },
    runDownloadTemplate: { type: Function, required: true },
    runDownloadErrors: { type: Function, default: null }
  },
  emits: ['update:visible', 'done'],
  data() {
    return {
      step: 0, file: null, preview: null, checking: false, submitting: false,
      downloading: false, downloadingErrors: false
    }
  },
  watch: {
    visible(v) {
      if (v) Object.assign(this, { step: 0, file: null, preview: null })
    }
  },
  methods: {
    async downloadTemplate() {
      this.downloading = true
      const res = await this.runDownloadTemplate()
      this.downloading = false
      if (res.code === 0) toast.success(res.message || '标准 Excel 模板已下载')
      else toast.error(res.message)
    },
    selectFile(event) {
      const selected = event.target.files && event.target.files[0]
      this.preview = null
      if (!selected) {
        this.file = null
        return
      }
      if (!selected.name.toLowerCase().endsWith('.xlsx')) {
        this.file = null
        event.target.value = ''
        toast.error('师生账号导入只支持标准 .xlsx 文件')
        return
      }
      this.file = selected
    },
    async downloadErrors() {
      if (!this.preview?.batchNo || this.downloadingErrors || !this.runDownloadErrors) return
      this.downloadingErrors = true
      const res = await this.runDownloadErrors(this.preview.batchNo)
      this.downloadingErrors = false
      if (res.code === 0) toast.success(res.message || 'Excel 错误回执已下载')
      else toast.error(res.message)
    },
    async runCheck() {
      this.checking = true
      const res = await this.runValidate(this.file)
      this.checking = false
      if (res.code === 0) this.preview = res.data
      else toast.error(res.message)
    },
    async confirmImport() {
      this.submitting = true
      const res = await this.runImport(this.preview.batchNo)
      this.submitting = false
      if (res.code === 0) {
        toast.success((res.data.receipt || res.message || '导入完成') + '，已写入审计日志')
        this.$emit('update:visible', false)
        this.$emit('done')
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.imp {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.imp__steps {
  display: flex;
  gap: var(--space-4);
}
.imp__step {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.imp__step-no {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-base);
  font-style: normal;
  font-size: var(--font-size-xs);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.imp__step.is-on {
  color: var(--primary-600);
  font-weight: var(--font-weight-semibold);
}
.imp__step.is-on .imp__step-no {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.imp__step.is-done .imp__step-no {
  background: var(--success-500);
  border-color: var(--success-500);
  color: #fff;
}
.imp__rules {
  margin: 0;
  padding-left: var(--space-4);
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.imp__upload {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.imp__file-input {
  height: 36px;
  border: 1px dashed var(--border-base);
  border-radius: var(--radius-base);
  padding: 0 var(--space-3);
  font: inherit;
  font-size: var(--font-size-sm);
  background: var(--bg-section-blue);
  outline: none;
}
.imp__result {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.imp__stat {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.imp__stat .is-ok {
  color: var(--success-600);
}
.imp__stat .is-err {
  color: var(--danger-600);
}
</style>
