<template>
  <div class="app-dt" :class="{ 'is-disabled': disabled, 'is-invalid': !!errorText }">
    <label v-if="label" class="app-dt__label">
      {{ label }}<i v-if="required">*</i>
      <span v-if="hint" class="app-dt__hint-inline">{{ hint }}</span>
    </label>
    <div class="app-dt__row">
      <input
        class="app-dt__control"
        type="datetime-local"
        :value="inner"
        :disabled="disabled"
        :min="min"
        :max="max"
        step="60"
        :aria-label="label || placeholder"
        @change="onNativeChange"
      />
      <button
        v-if="clearable && inner && !disabled"
        type="button"
        class="app-dt__clear"
        title="清空"
        @click="clear"
      >清空</button>
    </div>
    <p v-if="!inner && showEmptyHint" class="app-dt__placeholder">{{ placeholder }}</p>
    <p v-if="errorText" class="app-dt__err">{{ errorText }}</p>
  </div>
</template>

<script>
/**
 * AppDateTimePicker — 日期+时间（YYYY-MM-DDTHH:mm，对齐 datetime-local）。
 */
import { toDateTimeInputValue, parseDate, isEmptyDate } from '@/utils/dateUtils'

export default {
  name: 'AppDateTimePicker',
  props: {
    modelValue: { type: [String, Date], default: '' },
    label: { type: String, default: '' },
    hint: { type: String, default: '' },
    placeholder: { type: String, default: '请选择日期时间' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    showEmptyHint: { type: Boolean, default: false },
    min: { type: String, default: '' },
    max: { type: String, default: '' },
    endValue: { type: [String, Date], default: '' },
    startValue: { type: [String, Date], default: '' },
    role: { type: String, default: 'single' }
  },
  emits: ['update:modelValue', 'change', 'clear'],
  computed: {
    inner() {
      return toDateTimeInputValue(this.modelValue)
    },
    errorText() {
      const cur = parseDate(this.modelValue)
      if (!cur) return ''
      if (this.role === 'start' && !isEmptyDate(this.endValue)) {
        const end = parseDate(this.endValue)
        if (end && cur.getTime() > end.getTime()) return '开始时间不能晚于结束时间'
      }
      if (this.role === 'end' && !isEmptyDate(this.startValue)) {
        const start = parseDate(this.startValue)
        if (start && cur.getTime() < start.getTime()) return '结束时间不能早于开始时间'
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
.app-dt { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-dt__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary, #64748b);
  display: flex; align-items: center; gap: 4px;
}
.app-dt__label i { color: var(--danger-600, #dc2626); font-style: normal; }
.app-dt__hint-inline { font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.app-dt__row { display: flex; align-items: center; gap: 6px; }
.app-dt__control {
  flex: 1; min-width: 0; height: 34px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: var(--radius-base, 6px);
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  font: inherit; font-size: var(--font-size-sm, 13px);
  padding: 0 8px; outline: none;
}
.app-dt__control:focus {
  border-color: var(--primary-500, #2563eb);
  box-shadow: 0 0 0 3px var(--primary-50, #eff6ff);
}
.app-dt.is-disabled .app-dt__control {
  background: var(--bg-section-blue, #f8fafc);
  color: var(--text-tertiary, #94a3b8);
  cursor: not-allowed;
}
.app-dt.is-invalid .app-dt__control { border-color: var(--danger-600, #dc2626); }
.app-dt__clear {
  flex-shrink: 0; height: 28px; padding: 0 8px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: 6px; background: #fff;
  color: var(--text-secondary, #64748b);
  font-size: 12px; cursor: pointer;
}
.app-dt__clear:hover { color: var(--danger-600, #dc2626); border-color: var(--danger-600, #dc2626); }
.app-dt__placeholder, .app-dt__err { margin: 0; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.app-dt__err { color: var(--danger-600, #dc2626); }
</style>
