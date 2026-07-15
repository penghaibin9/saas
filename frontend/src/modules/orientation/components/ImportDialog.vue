<template>
  <div v-if="visible" class="imd__mask" @click.self="close">
    <div class="imd" role="dialog" aria-modal="true">
      <header class="imd__header">
        <h3>{{ template?.name || '批量导入' }}</h3>
        <button type="button" class="imd__close" aria-label="关闭" @click="close">×</button>
      </header>

      <div class="imd__steps">
        <span v-for="(s, i) in steps" :key="s" class="imd__step" :class="{ 'is-active': step === i, 'is-done': step > i }">
          {{ i + 1 }}. {{ s }}
        </span>
      </div>

      <div class="imd__body">
        <AccountImportBoundaryNotice class="imd__boundary" />

        <!-- Step 0：模板与上传 -->
        <div v-if="step === 0" class="imd__panel">
          <div class="imd__tpl">
            <div>
              <div class="imd__tpl-name">{{ template?.fileName }}</div>
              <div class="imd__tpl-hint">必填字段：{{ requiredFields }}</div>
            </div>
            <AppButton variant="secondary" @click="downloadTemplate">下载模板</AppButton>
          </div>
          <label class="imd__upload">
            <input type="file" accept=".xlsx,.xls" class="imd__file" @change="onFile" />
            <span class="imd__upload-icon">⇪</span>
            <span>{{ fileName || '点击选择 Excel 文件（.xlsx）' }}</span>
          </label>
          <p v-if="error" class="imd__error">{{ error }}</p>
        </div>

        <!-- Step 1：校验预览 -->
        <div v-else-if="step === 1" class="imd__panel">
          <div class="imd__summary">
            共解析 <b>{{ validation.total }}</b> 行 · 校验通过
            <b class="is-good">{{ validation.validCount }}</b> 行 · 失败
            <b class="is-bad">{{ validation.total - validation.validCount }}</b> 行，仅导入校验通过的数据。
          </div>
          <table class="imd__table">
            <thead>
              <tr><th>行号</th><th>数据预览</th><th>校验结果</th></tr>
            </thead>
            <tbody>
              <tr v-for="r in validation.rows" :key="r.row" :class="{ 'is-invalid': !r.valid }">
                <td>{{ r.row }}</td>
                <td>{{ r.data }}</td>
                <td>
                  <span v-if="r.valid" class="imd__ok">通过</span>
                  <span v-else class="imd__fail">{{ r.error }}</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- Step 2：结果回执 -->
        <div v-else class="imd__panel imd__panel--result">
          <div class="imd__result-icon">✓</div>
          <div class="imd__result-title">导入完成</div>
          <div class="imd__result-desc">
            成功导入 {{ result?.imported ?? 0 }} 条数据，失败数据未导入。回执编号：{{ result?.receiptId }}
          </div>
          <div class="imd__result-audit">本次导入已写入审计日志，可在「操作留痕」中查看。</div>
        </div>
      </div>

      <footer class="imd__footer">
        <AppButton variant="ghost" @click="close">{{ step === 2 ? '关闭' : '取消' }}</AppButton>
        <AppButton v-if="step === 0" variant="primary" :disabled="!fileName" :loading="busy" @click="doValidate">
          解析并校验
        </AppButton>
        <AppButton v-if="step === 1" variant="primary" :disabled="!validation.validCount" :loading="busy" @click="doImport">
          导入 {{ validation.validCount }} 条通过数据
        </AppButton>
      </footer>
    </div>
  </div>
</template>

<script>
/**
 * ImportDialog — 通用导入弹窗（模块局部组件）。
 * 流程：下载模板 → 上传 Excel → 字段校验与错误预览 → 仅导入通过数据 → 结果回执（含审计说明）。
 * Props:
 *  - template: mock/api importTemplates 下发的模板对象
 *  - validateFn(fileName) / importFn({ validCount, fileName })：由页面注入的 api 调用
 */
import { AppButton } from '@/components/ui'
import AccountImportBoundaryNotice from '@/components/common/AccountImportBoundaryNotice.vue'
import { toast } from '@/utils/toast'

export default {
  name: 'ImportDialog',
  components: { AppButton, AccountImportBoundaryNotice },
  props: {
    visible: { type: Boolean, default: false },
    template: { type: Object, default: null },
    validateFn: { type: Function, required: true },
    importFn: { type: Function, required: true }
  },
  emits: ['update:visible', 'imported'],
  data() {
    return {
      steps: ['上传文件', '校验预览', '导入回执'],
      step: 0,
      fileName: '',
      busy: false,
      error: '',
      validation: { total: 0, validCount: 0, rows: [] },
      result: null
    }
  },
  computed: {
    requiredFields() {
      return (this.template?.fields || [])
        .filter((f) => f.required)
        .map((f) => f.label)
        .join('、')
    }
  },
  watch: {
    visible(v) {
      if (v) Object.assign(this, { step: 0, fileName: '', error: '', validation: { total: 0, validCount: 0, rows: [] }, result: null })
    }
  },
  methods: {
    close() {
      this.$emit('update:visible', false)
    },
    downloadTemplate() {
      toast.info(`已开始下载模板：${this.template?.fileName || ''}（演示环境为模拟下载）`)
    },
    onFile(e) {
      const f = e.target.files?.[0]
      this.error = ''
      if (!f) return
      if (!/\.xlsx?$/i.test(f.name)) {
        this.error = '仅支持 .xlsx / .xls 格式文件'
        return
      }
      this.fileName = f.name
    },
    async doValidate() {
      this.busy = true
      try {
        const res = await this.validateFn(this.fileName)
        if (res.code === 0) {
          this.validation = res.data
          this.step = 1
        } else {
          this.error = res.message
        }
      } finally {
        this.busy = false
      }
    },
    async doImport() {
      this.busy = true
      try {
        const res = await this.importFn({ validCount: this.validation.validCount, fileName: this.fileName })
        if (res.code === 0) {
          this.result = res.data
          this.step = 2
          this.$emit('imported', res.data)
        } else {
          toast.error(res.message)
        }
      } finally {
        this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.imd__mask {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 1000);
  background: var(--bg-mask);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}
.imd {
  width: min(640px, 100%);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.imd__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.imd__header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
}
.imd__close {
  border: none;
  background: none;
  font-size: 22px;
  color: var(--text-tertiary);
  cursor: pointer;
}
.imd__steps {
  display: flex;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-5);
  background: var(--bg-section-blue);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.imd__step.is-active {
  color: var(--primary-600);
  font-weight: var(--font-weight-semibold);
}
.imd__step.is-done {
  color: var(--success-600);
}
.imd__body {
  padding: var(--space-5);
  overflow-y: auto;
}
.imd__tpl {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-section-blue);
}
.imd__tpl-name {
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-medium);
}
.imd__tpl-hint {
  margin-top: 2px;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.imd__upload {
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
.imd__upload:hover {
  border-color: var(--primary-500);
  color: var(--primary-600);
}
.imd__upload-icon {
  font-size: 22px;
}
.imd__file {
  display: none;
}
.imd__error {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-xs);
  color: var(--danger-600);
}
.imd__summary {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}
.imd__summary .is-good {
  color: var(--success-600);
}
.imd__summary .is-bad {
  color: var(--danger-600);
}
.imd__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-size-xs);
}
.imd__table th,
.imd__table td {
  padding: var(--space-2);
  border-bottom: 1px solid var(--border-light);
  text-align: left;
}
.imd__table tr.is-invalid td {
  background: var(--danger-50);
}
.imd__ok {
  color: var(--success-600);
}
.imd__fail {
  color: var(--danger-600);
}
.imd__panel--result {
  text-align: center;
  padding: var(--space-6) 0;
}
.imd__result-icon {
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
.imd__result-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
}
.imd__result-desc {
  margin-top: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.imd__result-audit {
  margin-top: var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.imd__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-light);

}
</style>
