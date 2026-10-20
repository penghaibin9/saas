<template>
  <div v-if="visible" class="exd__mask" @click.self="close">
    <div class="exd" role="dialog" aria-modal="true" :aria-label="title">
      <header class="exd__header">
        <h3>{{ title }}</h3>
        <button type="button" class="exd__close" aria-label="关闭" @click="close">×</button>
      </header>

      <div class="exd__body">
        <template v-if="!result">
        <section class="exd__section">
          <div class="exd__label">导出范围</div>
          <label v-for="s in options.scopes || []" :key="s.value" class="exd__radio">
            <input v-model="scope" type="radio" :value="s.value" :disabled="busy" />
            {{ s.label }}
            <span v-if="s.value === 'SELECTED'" class="exd__radio-hint">（已选 {{ selectedCount }} 条）</span>
          </label>
        </section>

        <section class="exd__section">
          <div class="exd__label">台账包含的字段</div>
          <div v-for="g in options.fieldGroups || []" :key="g.key" class="exd__check" :class="{ 'is-sensitive': g.sensitive }">
            <span>
              {{ g.label }}
              <em class="exd__fields">{{ (g.fields || []).join(' / ') }}</em>
            </span>
          </div>
        </section>

        <section class="exd__section">
          <div class="exd__label">脱敏与水印</div>
          <label v-if="hasSensitiveOptions" class="exd__check">
            <input v-model="mask" type="checkbox" :disabled="busy || (options.idCardPlainForbidden && hasSensitive)" />
            敏感字段脱敏导出（手机号 / 身份证 / 薪资）
          </label>
          <p v-else class="exd__hint">本导出不包含手机号、身份证号或薪资等敏感明文字段。</p>
          <p v-if="hasSensitiveOptions && options.idCardPlainForbidden" class="exd__hint">身份证号仅支持脱敏导出，平台不提供明文导出。</p>
          <p class="exd__hint">{{ options.watermarkNote }}</p>
        </section>

        <section class="exd__section">
          <label class="exd__label" for="orientation-export-purpose">导出用途（必填，不少于 5 个字）</label>
          <textarea
            id="orientation-export-purpose"
            v-model.trim="purpose"
            :disabled="busy"
            class="exd__purpose"
            rows="3"
            maxlength="200"
            placeholder="例如：2026级迎新现场报到核对"
          />
        </section>

        <section class="exd__section exd__section--audit">
          <label class="exd__check">
            <input v-model="auditConfirmed" type="checkbox" :disabled="busy" />
            {{ options.auditNotice || '我已知悉本次导出将写入审计日志' }}
          </label>
        </section>
        </template>

        <div v-if="result" class="exd__result">
          已生成导出文件：<b>{{ result.fileName }}</b>
          <div class="exd__result-meta">共 {{ result.rowCount ?? 0 }} 行 · 水印：{{ result.watermarkText }} · 导出记录编号：{{ result.taskId }}</div>
          <AppButton variant="secondary" @click="downloadResult">重新下载此文件</AppButton>
        </div>
      </div>

      <footer class="exd__footer">
        <span class="exd__scope-tip">数据范围：{{ dataScopeName }}</span>
        <div class="exd__ops">
          <AppButton variant="ghost" :disabled="busy" @click="close">{{ result ? '完成' : '取消' }}</AppButton>
          <AppButton v-if="!result" variant="primary" :disabled="!auditConfirmed || !fieldGroups.length || purpose.length < 5" :loading="busy" @click="doExport">
            确认导出
          </AppButton>
        </div>
      </footer>
    </div>
  </div>
</template>

<script>
/**
 * ExportDialog — 通用导出弹窗（模块局部组件）。
 * 覆盖：导出范围 / 固定字段说明 / 数据范围限制提示 / 脱敏选项（默认开）/ 水印说明 / 审计确认。
 * Props:
 *  - options: 后端能力对应的导出范围与固定字段说明
 *  - exportFn(payload)：页面注入的 api 调用
 */
import { AppButton } from '@/components/ui'
import { toast } from '@/utils/toast'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'

export default {
  name: 'ExportDialog',
  components: { AppButton },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, default: '导出数据' },
    options: { type: Object, default: () => ({}) },
    selectedCount: { type: Number, default: 0 },
    dataScopeName: { type: String, default: '' },
    exportFn: { type: Function, required: true }
  },
  emits: ['update:visible', 'exported'],
  data() {
    return { scope: 'SCOPE_ALL', fieldGroups: [], mask: true, purpose: '', auditConfirmed: false, busy: false, result: null, operationSerial: 0 }
  },
  computed: {
    hasSensitiveOptions() {
      return (this.options.fieldGroups || []).some((g) => g.sensitive)
    },
    hasSensitive() {
      return (this.options.fieldGroups || []).some((g) => g.sensitive && this.fieldGroups.includes(g.key))
    }
  },
  watch: {
    visible(v) {
      this.operationSerial++
      this.busy = false
      if (v) {
        this.scope = this.options.scopes?.[0]?.value || 'SCOPE_ALL'
        this.fieldGroups = (this.options.fieldGroups || []).filter((g) => !g.sensitive).map((g) => g.key)
        this.mask = this.options.maskDefault !== false
        this.purpose = ''
        this.auditConfirmed = false
        this.result = null
      }
    }
  },
  beforeUnmount() { this.operationSerial++ },
  methods: {
    close() {
      if (this.busy) return
      this.$emit('update:visible', false)
    },
    downloadResult() { if (this.result) downloadXlsxFromApi(this.result) },
    async doExport() {
      if (this.busy || this.result || !this.auditConfirmed || !this.fieldGroups.length || this.purpose.trim().length < 5) return
      const serial = this.operationSerial
      this.busy = true
      try {
        const res = await this.exportFn({
          scope: this.scope,
          fieldGroups: this.fieldGroups,
          mask: this.mask || this.hasSensitive,
          purpose: this.purpose,
          auditConfirmed: this.auditConfirmed
        })
        if (serial !== this.operationSerial) return
        if (res.code === 0) {
          this.result = res.data
          downloadXlsxFromApi(res.data)
          this.$emit('exported', res.data)
        } else {
          toast.error(res.message)
        }
      } catch (error) {
        if (serial === this.operationSerial) toast.error(error.message || '导出失败，请重试')
      } finally {
        if (serial === this.operationSerial) this.busy = false
      }
    }
  }
}
</script>

<style scoped>
.exd__mask {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal, 1000);
  background: var(--bg-mask);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}
.exd {
  width: min(560px, 100%);
  max-height: 86vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.exd__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.exd__header h3 {
  margin: 0;
  font-size: var(--font-size-lg);
}
.exd__close {
  border: none;
  background: none;
  font-size: 22px;
  color: var(--text-tertiary);
  cursor: pointer;
}
.exd__body {
  padding: var(--space-5);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}
.exd__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.exd__radio,
.exd__check {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  padding: var(--space-1) 0;
  cursor: pointer;
}
.exd__radio-hint {
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
}
.exd__fields {
  display: block;
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.exd__check.is-sensitive span {
  color: var(--warning-700);
}
.exd__hint {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.exd__purpose {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  padding: var(--space-2) var(--space-3);
  font: inherit;
}
.exd__section--audit {
  padding: var(--space-3);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-md);
}
.exd__result {
  padding: var(--space-3);
  background: var(--success-50);
  border: 1px solid var(--success-100);
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  color: var(--success-700);
}
.exd__result-meta {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.exd__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-light);
}
.exd__scope-tip {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.exd__ops {
  display: flex;
  gap: var(--space-2);
}
</style>
