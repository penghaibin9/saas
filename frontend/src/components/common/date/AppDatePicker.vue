<template>
  <div class="app-date" :class="{ 'is-disabled': disabled, 'is-invalid': !!errorText }">
    <label v-if="label" class="app-date__label">
      {{ label }}<i v-if="required">*</i>
      <span v-if="hint" class="app-date__hint-inline">{{ hint }}</span>
    </label>
    <div class="app-date__row">
      <input
        class="app-date__control"
        type="date"
        :value="inner"
        :disabled="disabled"
        :min="min"
        :max="max"
        :aria-label="label || placeholder"
        @change="onNativeChange"
      />
      <button
        v-if="clearable && inner && !disabled"
        type="button"
        class="app-date__clear"
        title="清空"
        @click="clear"
      >清空</button>
    </div>
    <p v-if="!inner && showEmptyHint" class="app-date__placeholder">{{ placeholder }}</p>
    <p v-if="errorText" class="app-date__err">{{ errorText }}</p>
  </div>
</template>

<script>
/**
 * AppDatePicker — 单日期选择（YYYY-MM-DD）。
 * 不展示 yyyy/mm/日 占位；空值由外层 placeholder / AppDateDisplay 负责文案。
 */
import { toDateInputValue, formatDate, isEmptyDate } from '@/utils/dateUtils'

export default {
  name: 'AppDatePicker',
  props: {
    modelValue: { type: [String, Date], default: '' },
    label: { type: String, default: '' },
    hint: { type: String, default: '' },
    placeholder: { type: String, default: '请选择日期' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    showEmptyHint: { type: Boolean, default: false },
    min: { type: String, default: '' },
    max: { type: String, default: '' },
    /** 与配对结束日联动：开始不能晚于 end */
    endValue: { type: [String, Date], default: '' },
    /** 与配对开始日联动：结束不能早于 start */
    startValue: { type: [String, Date], default: '' },
    role: { type: String, default: 'single' } // single | start | end
  },
  emits: ['update:modelValue', 'change', 'clear'],
  computed: {
    inner() {
      return toDateInputValue(this.modelValue)
    },
    errorText() {
      if (this.role === 'start' && !isEmptyDate(this.modelValue) && !isEmptyDate(this.endValue)) {
        const a = formatDate(this.modelValue, '')
        const b = formatDate(this.endValue, '')
        if (a && b && a > b) return '开始时间不能晚于结束时间'
      }
      if (this.role === 'end' && !isEmptyDate(this.modelValue) && !isEmptyDate(this.startValue)) {
        const a = formatDate(this.startValue, '')
        const b = formatDate(this.modelValue, '')
        if (a && b && b < a) return '结束时间不能早于开始时间'
      }
      return ''
    }
  },
  methods: {
    onNativeChange(e) {
      const v = e.target.value || ''
      this.$emit('update:modelValue', v)
      this.$emit('change', v)
    },
    clear() {
      this.$emit('update:modelValue', '')
      this.$emit('clear')
      this.$emit('change', '')
    }
  }
}
</script>

<style scoped>
.app-date { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-date__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary, #64748b);
  display: flex; align-items: center; gap: 4px;
}
.app-date__label i { color: var(--danger-600, #dc2626); font-style: normal; }
.app-date__hint-inline { font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.app-date__row { display: flex; align-items: center; gap: 6px; }
.app-date__control {
  flex: 1; min-width: 0; height: 34px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: var(--radius-base, 6px);
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  font: inherit; font-size: var(--font-size-sm, 13px);
  padding: 0 8px; outline: none;
}
.app-date__control:focus {
  border-color: var(--primary-500, #2563eb);
  box-shadow: 0 0 0 3px var(--primary-50, #eff6ff);
}
.app-date.is-disabled .app-date__control {
  background: var(--bg-section-blue, #f8fafc);
  color: var(--text-tertiary, #94a3b8);
  cursor: not-allowed;
}
.app-date.is-invalid .app-date__control { border-color: var(--danger-600, #dc2626); }
.app-date__clear {
  flex-shrink: 0; height: 28px; padding: 0 8px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: 6px; background: #fff;
  color: var(--text-secondary, #64748b);
  font-size: 12px; cursor: pointer;
}
.app-date__clear:hover { color: var(--danger-600, #dc2626); border-color: var(--danger-600, #dc2626); }
.app-date__placeholder, .app-date__err {
  margin: 0; font-size: 12px; color: var(--text-tertiary, #94a3b8);
}
.app-date__err { color: var(--danger-600, #dc2626); }
</style>
