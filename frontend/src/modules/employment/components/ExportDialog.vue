<template>
  <div v-if="visible" class="exd__mask" @click.self="close">
    <div class="exd" role="dialog" aria-modal="true">
      <header class="exd__header">
        <h3>{{ title }}</h3>
        <button type="button" class="exd__close" aria-label="关闭" @click="close">×</button>
      </header>

      <div class="exd__body">
        <section class="exd__section">
          <div class="exd__label">导出范围</div>
          <label v-for="s in options.scopes || []" :key="s.value" class="exd__radio">
            <input v-model="scope" type="radio" :value="s.value" />
            {{ s.label }}
            <span v-if="s.value === 'SELECTED'" class="exd__radio-hint">（已选 {{ selectedCount }} 条）</span>
          </label>
        </section>

        <section class="exd__section">
          <div class="exd__label">字段选择</div>
          <label v-for="g in options.fieldGroups || []" :key="g.key" class="exd__check" :class="{ 'is-sensitive': g.sensitive }">
            <input v-model="fieldGroups" type="checkbox" :value="g.key" />
            <span>
              {{ g.label }}
              <em class="exd__fields">{{ (g.fields || []).join(' / ') }}</em>
            </span>
          </label>
        </section>

        <section v-if="options.purposeRequired" class="exd__section">
          <label class="exd__purpose-label" for="employment-export-purpose">导出用途 *</label>
          <textarea
            id="employment-export-purpose"
            v-model.trim="purpose"
            class="exd__purpose"
            rows="3"
            maxlength="200"
            placeholder="请填写真实工作用途，不少于 5 个字；将写入服务端审计与文件水印"
          />
          <p class="exd__hint">用途与操作者、时间、数据范围共同写入审计记录。</p>
        </section>

        <section class="exd__section">
          <div class="exd__label">脱敏与水印</div>
          <label class="exd__check">
            <input v-model="mask" type="checkbox" :disabled="options.idCardPlainForbidden && hasSensitive" />
            敏感字段脱敏导出（手机号 / 身份证 / 薪资）
          </label>
          <p v-if="options.idCardPlainForbidden" class="exd__hint">身份证号仅支持脱敏导出，平台不提供明文导出。</p>
          <p class="exd__hint">{{ options.watermarkNote }}</p>
        </section>

        <section class="exd__section exd__section--audit">
          <label class="exd__check">
            <input v-model="auditConfirmed" type="checkbox" />
            {{ options.auditNotice || '我已知悉本次导出将写入审计日志' }}
          </label>
        </section>

        <div v-if="result" class="exd__result">
          已生成导出文件：<b>{{ result.fileName }}</b>
          <div class="exd__result-meta">
            {{ result.watermarkText || result.securityNotice || '服务端已启用水印与审计' }}
            <template v-if="result.auditId || result.taskId"> · 审计/任务编号：{{ result.auditId || result.taskId }}</template>
          </div>
        </div>
      </div>

      <footer class="exd__footer">
        <span class="exd__scope-tip">数据范围：{{ dataScopeName }}</span>
        <div class="exd__ops">
          <AppButton variant="ghost" @click="close">取消</AppButton>
          <AppButton variant="primary" :disabled="!canSubmit" :loading="busy" @click="doExport">
            确认导出
          </AppButton>
        </div>
      </footer>
    </div>
  </div>
</template>

<script>
/**
 * ExportDialog — 就业模块导出弹窗。
 * A3：正式导出必须填写服务端审计用途；范围与字段能力由 API facade 下发，未实现范围不展示。
 */
import { AppButton } from '@/components/ui'
import { toast } from '@/utils/toast'

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
    return { scope: '', fieldGroups: [], mask: true, auditConfirmed: false, purpose: '', busy: false, result: null }
  },
  computed: {
    hasSensitive() {
      return (this.options.fieldGroups || []).some((g) => g.sensitive && this.fieldGroups.includes(g.key))
    },
    canSubmit() {
      if (!this.auditConfirmed || !this.fieldGroups.length || !this.scope) return false
      if (this.options.purposeRequired && this.purpose.trim().length < 5) return false
      return true
    }
  },
  watch: {
    visible(v) {
      if (v) {
        this.scope = this.options.scopes?.[0]?.value || ''
        this.fieldGroups = (this.options.fieldGroups || []).filter((g) => !g.sensitive).map((g) => g.key)
        this.mask = this.options.maskDefault !== false
        this.auditConfirmed = false
        this.purpose = ''
        this.result = null
      }
    }
  },
  methods: {
    close() {
      this.$emit('update:visible', false)
    },
    async doExport() {
      if (!this.canSubmit) return
      this.busy = true
      try {
        const res = await this.exportFn({
          scope: this.scope,
          fieldGroups: this.fieldGroups,
          mask: this.mask || this.hasSensitive,
          auditConfirmed: this.auditConfirmed,
          purpose: this.purpose.trim()
        })
        if (res.code === 0) {
          this.result = res.data
          this.$emit('exported', res.data)
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
.exd__header h3 { margin: 0; font-size: var(--font-size-lg); }
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
.exd__label,
.exd__purpose-label {
  display: block;
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
.exd__radio-hint { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.exd__fields {
  display: block;
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.exd__check.is-sensitive span { color: var(--warning-700); }
.exd__hint {
  margin: var(--space-1) 0 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.exd__purpose {
  width: 100%;
  resize: vertical;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  color: var(--text-primary);
  padding: var(--space-2) var(--space-3);
  font: inherit;
  box-sizing: border-box;
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
.exd__scope-tip { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.exd__ops { display: flex; gap: var(--space-2); }
</style>
