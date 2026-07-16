<template>
  <div v-if="visible" class="app-confirm-dialog__mask" @click.self="onCancel">
    <div class="app-confirm-dialog" role="dialog" aria-modal="true">
      <div class="app-confirm-dialog__header" :class="`is-${effType}`">
        <span class="app-confirm-dialog__icon">{{ effType === 'danger' ? '!' : '?' }}</span>
        <span class="app-confirm-dialog__title">{{ title }}</span>
      </div>

      <div class="app-confirm-dialog__body">
        <p v-if="displayMessage" class="app-confirm-dialog__message">{{ displayMessage }}</p>
        <slot />

        <div v-if="requireReason" class="app-confirm-dialog__reason">
          <label class="app-confirm-dialog__label">
            {{ reasonLabel }}<span class="app-confirm-dialog__required">*</span>
          </label>
          <div v-if="reasonChips.length" class="app-confirm-dialog__chips">
            <span class="app-confirm-dialog__chips-label">快捷填入：</span>
            <AppQuickFilterChips :options="reasonChips" multiple :model-value="[]" size="compact" @change="onPickChip" />
          </div>
          <textarea
            v-model="reason"
            class="app-confirm-dialog__textarea"
            :placeholder="reasonPlaceholder"
            rows="3"
          />
          <div v-if="reasonError" class="app-confirm-dialog__error">{{ reasonError }}</div>
        </div>

        <label v-if="showNotify" class="app-confirm-dialog__notify">
          <input v-model="notify" type="checkbox" />
          {{ notifyLabel }}
        </label>
      </div>

      <div class="app-confirm-dialog__footer">
        <button type="button" class="acd-btn" @click="onCancel">{{ cancelText }}</button>
        <button
          type="button"
          class="acd-btn acd-btn--confirm"
          :class="`is-${effType}`"
          :disabled="busy"
          @click="onConfirm"
        >
          {{ busy ? '提交中…' : confirmText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * AppConfirmDialog 统一二次确认弹窗
 * 依据 V2.1 §11.2 / §13.4：
 *  - 退回/驳回等高风险操作必须触发本弹窗
 *  - requireReason=true 时原因必填，少于 reasonMinLength（默认5）字不允许提交
 *  - 确认按钮必须写清楚动作（confirmText），不允许只写“确定”
 * Props: visible(v-model)、title、message、type: primary|warning|danger、
 *        confirmText、cancelText、requireReason、reasonLabel、reasonPlaceholder、
 *        reasonMinLength、showNotify（是否显示“通知学生”勾选）、notifyLabel、submitting（防重复提交）、
 *        reasonChips（可选，字符串数组；requireReason 时在原因框上方渲染快捷芯片，点击追加进原因框，
 *        已有内容用「；」拼接，不覆盖已输入内容；不传则不渲染，不影响任何既有调用方）
 * Emits: update:visible、confirm({ reason, notify })、cancel
 * Slots: default（补充说明 / 影响范围 / 附件区）
 */
import AppQuickFilterChips from './display/AppQuickFilterChips.vue'

export default {
  name: 'AppConfirmDialog',
  components: { AppQuickFilterChips },
  props: {
    visible: { type: Boolean, default: false },
    title: { type: String, required: true },
    message: { type: String, default: '' },
    /** content: message 的别名，方便调用方语义化传参 */
    content: { type: String, default: '' },
    type: {
      type: String,
      default: 'warning',
      validator: (v) => ['primary', 'warning', 'danger'].includes(v)
    },
    /** danger: 便捷布尔，等价 type='danger'（优先级高于 type） */
    danger: { type: Boolean, default: false },
    confirmText: { type: String, default: '确认' },
    cancelText: { type: String, default: '取消' },
    requireReason: { type: Boolean, default: false },
    reasonLabel: { type: String, default: '处理原因' },
    reasonPlaceholder: { type: String, default: '请填写具体原因，便于对方理解和修改' },
    reasonMinLength: { type: Number, default: 5 },
    reasonChips: { type: Array, default: () => [] },
    showNotify: { type: Boolean, default: false },
    notifyLabel: { type: String, default: '通知学生' },
    submitting: { type: Boolean, default: false },
    /** loading: submitting 的别名 */
    loading: { type: Boolean, default: false }
  },
  emits: ['update:visible', 'confirm', 'cancel'],
  data() {
    return { reason: '', notify: true, reasonError: '' }
  },
  computed: {
    displayMessage() {
      return this.content || this.message
    },
    effType() {
      return this.danger ? 'danger' : this.type
    },
    busy() {
      return this.loading || this.submitting
    }
  },
  watch: {
    visible(v) {
      if (v) {
        this.reason = ''
        this.notify = true
        this.reasonError = ''
      }
    }
  },
  methods: {
    onPickChip(vals) {
      const text = Array.isArray(vals) ? vals[vals.length - 1] : vals
      if (!text) return
      const cur = (this.reason || '').replace(/[；;\s]+$/, '')
      this.reason = cur ? cur + '；' + text : text
      this.reasonError = ''
    },
    onCancel() {
      this.$emit('update:visible', false)
      this.$emit('cancel')
    },
    onConfirm() {
      if (this.requireReason) {
        const trimmed = this.reason.trim()
        if (trimmed.length < this.reasonMinLength) {
          this.reasonError = `${this.reasonLabel}不能少于 ${this.reasonMinLength} 个字`
          return
        }
      }
      this.reasonError = ''
      this.$emit('confirm', { reason: this.reason.trim(), notify: this.notify })
    }
  }
}
</script>

<style scoped>
.app-confirm-dialog__mask {
  position: fixed;
  inset: 0;
  background: var(--bg-mask);
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
}
.app-confirm-dialog {
  width: 460px;
  max-width: 100%;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}
.app-confirm-dialog__header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-5) var(--space-6) 0;
}
.app-confirm-dialog__icon {
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.is-primary .app-confirm-dialog__icon {
  background: var(--primary-50);
  color: var(--primary-600);
}
.is-warning .app-confirm-dialog__icon {
  background: var(--warning-50);
  color: var(--warning-600);
}
.is-danger .app-confirm-dialog__icon {
  background: var(--danger-50);
  color: var(--danger-600);
}
.app-confirm-dialog__title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.app-confirm-dialog__body {
  padding: var(--space-4) var(--space-6);
}
.app-confirm-dialog__message {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  line-height: var(--line-height-base);
}
.app-confirm-dialog__label {
  display: block;
  font-size: var(--font-size-base);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
}
.app-confirm-dialog__required {
  color: var(--danger-600);
  margin-left: 2px;
}
.app-confirm-dialog__chips {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}
.app-confirm-dialog__chips-label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.app-confirm-dialog__textarea {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  padding: var(--space-2) var(--space-3);
  font-size: var(--font-size-base);
  font-family: var(--font-family-base);
  color: var(--text-primary);
  resize: vertical;
}
.app-confirm-dialog__textarea:focus {
  outline: none;
  border-color: var(--primary-500);
}
.app-confirm-dialog__error {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--danger-600);
}
.app-confirm-dialog__notify {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-3);
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  cursor: pointer;
}
.app-confirm-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-6) var(--space-5);
}
.acd-btn {
  height: 34px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-base);
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  cursor: pointer;
}
.acd-btn:hover {
  border-color: var(--border-dark);
}
.acd-btn--confirm {
  color: var(--text-inverse);
  border: none;
}
.acd-btn--confirm.is-primary {
  background: var(--primary-600);
}
.acd-btn--confirm.is-primary:hover {
  background: var(--primary-700);
}
.acd-btn--confirm.is-warning {
  background: var(--warning-600);
}
.acd-btn--confirm.is-warning:hover {
  background: var(--warning-700);
}
.acd-btn--confirm.is-danger {
  background: var(--danger-600);
}
.acd-btn--confirm.is-danger:hover {
  background: var(--danger-700);
}
.acd-btn--confirm:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
