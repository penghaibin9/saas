<template>
  <div
    class="app-form-item"
    :class="[`is-${layout}`, { 'is-error': !!errorMsg, 'is-compact': size === 'compact' }]"
  >
    <label
      v-if="label || $slots.label"
      class="app-form-item__label"
      :class="`is-${labelAlign}`"
      :style="labelStyle"
      :for="controlId"
    >
      <span v-if="isRequired" class="app-form-item__req" aria-hidden="true">*</span>
      <slot name="label">{{ label }}</slot>
      <AppHelpTooltip v-if="help" :content="help" class="app-form-item__help" />
    </label>

    <div class="app-form-item__control">
      <slot :id="controlId" :disabled="ctxDisabled" :readonly="ctxReadonly" :status="errorMsg ? 'error' : 'default'" />
      <AppFieldHint v-if="errorMsg" type="error" :text="errorMsg" />
      <AppFieldHint v-else-if="hint" type="hint" :text="hint" />
    </div>
  </div>
</template>

<script>
/**
 * AppFormItem — 表单字段行（label + 必填星 + 帮助气泡 + 校验错误）。
 * 放在 AppForm 内自动继承布局/密度/禁用/只读，并读取 AppForm 的校验错误。
 * 也可脱离 AppForm 单独使用（传 error / required 即可）。
 * Props:
 *  - label / prop(对应 model 字段名，用于取校验错误) / required
 *  - help(标题旁气泡) / hint(常态灰色提示) / error(手动错误，优先级最高)
 * Slot: default（作用域插槽提供 { id, disabled, readonly, status } 便于绑定控件）
 */
import AppHelpTooltip from '../AppHelpTooltip.vue'
import AppFieldHint from '../AppFieldHint.vue'

let uid = 0
export default {
  name: 'AppFormItem',
  components: { AppHelpTooltip, AppFieldHint },
  inject: { appForm: { default: null } },
  props: {
    label: { type: String, default: '' },
    prop: { type: String, default: '' },
    required: { type: Boolean, default: false },
    help: { type: String, default: '' },
    hint: { type: String, default: '' },
    error: { type: String, default: '' }
  },
  data() {
    return { controlId: `app-fi-${++uid}` }
  },
  computed: {
    layout() {
      return this.appForm ? this.appForm.layout : 'vertical'
    },
    size() {
      return this.appForm ? this.appForm.size : 'normal'
    },
    labelAlign() {
      return this.appForm ? this.appForm.labelAlign : 'left'
    },
    labelStyle() {
      if (this.layout === 'horizontal' && this.appForm) {
        return { width: this.appForm.labelWidth }
      }
      return null
    },
    ctxDisabled() {
      return this.appForm ? this.appForm.disabled : false
    },
    ctxReadonly() {
      return this.appForm ? this.appForm.readonly : false
    },
    isRequired() {
      if (this.required) return true
      const rules = this.appForm && this.prop ? this.appForm.rules[this.prop] : null
      return !!(rules && rules.some((r) => r.required))
    },
    errorMsg() {
      if (this.error) return this.error
      if (this.appForm && this.prop) return this.appForm.fieldErrors[this.prop] || ''
      return ''
    }
  }
}
</script>

<style scoped>
.app-form-item {
  margin-bottom: var(--space-4);
}
.app-form-item.is-compact { margin-bottom: var(--space-3); }
.app-form-item.is-horizontal {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}
.app-form-item.is-inline { margin-bottom: 0; }
.app-form-item__label {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  margin-bottom: var(--space-2);
  line-height: 32px;
}
.is-horizontal .app-form-item__label {
  flex-shrink: 0;
  margin-bottom: 0;
  justify-content: flex-start;
}
.is-horizontal .app-form-item__label.is-right { justify-content: flex-end; }
.app-form-item__req {
  color: var(--danger-600);
  font-family: var(--font-family-base);
}
.app-form-item__help { margin-left: 2px; }
.app-form-item__control {
  flex: 1;
  min-width: 0;
}
</style>
