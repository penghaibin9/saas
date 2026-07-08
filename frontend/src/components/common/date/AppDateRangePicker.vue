<template>
  <div class="app-dr" :class="{ 'is-filter': mode === 'filter' }">
    <label v-if="label" class="app-dr__label">
      {{ label }}<i v-if="required">*</i>
      <span v-if="hint" class="app-dr__hint-inline">{{ hint }}</span>
    </label>

    <div class="app-dr__body">
      <div class="app-dr__inputs">
        <AppDatePicker
          v-if="!withTime"
          :model-value="start"
          :role="'start'"
          :end-value="end"
          :disabled="disabled"
          :clearable="false"
          :placeholder="emptyLabel"
          @update:model-value="onStart"
        />
        <AppDateTimePicker
          v-else
          :model-value="start"
          :role="'start'"
          :end-value="end"
          :disabled="disabled"
          :clearable="false"
          :placeholder="emptyLabel"
          @update:model-value="onStart"
        />
        <span class="app-dr__sep">至</span>
        <AppDatePicker
          v-if="!withTime"
          :model-value="end"
          :role="'end'"
          :start-value="start"
          :disabled="disabled"
          :clearable="false"
          :placeholder="emptyLabel"
          @update:model-value="onEnd"
        />
        <AppDateTimePicker
          v-else
          :model-value="end"
          :role="'end'"
          :start-value="start"
          :disabled="disabled"
          :clearable="false"
          :placeholder="emptyLabel"
          @update:model-value="onEnd"
        />
        <button
          v-if="clearable && hasValue && !disabled"
          type="button"
          class="app-dr__clear"
          @click="clear"
        >清空</button>
      </div>

      <p v-if="mode === 'filter' && !hasValue" class="app-dr__empty">{{ emptyLabel }}</p>
      <p v-if="rangeError" class="app-dr__err">{{ rangeError }}</p>

      <div v-if="showShortcuts" class="app-dr__shortcuts">
        <button
          v-for="s in shortcuts"
          :key="s.key"
          type="button"
          class="app-dr__chip"
          :disabled="disabled"
          @click="applyShortcut(s)"
        >{{ s.label }}</button>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * AppDateRangePicker — 日期范围。
 * mode=filter：默认空=不限日期（文案「全部时间」），支持快捷项与页面记忆。
 * v-model: { start, end } 或分开用 startKey/endKey 由父级 filters 持有。
 */
import AppDatePicker from './AppDatePicker.vue'
import AppDateTimePicker from './AppDateTimePicker.vue'
import {
  FILTER_SHORTCUTS,
  FILTER_EMPTY_LABEL,
  validateRange,
  isEmptyDate,
  loadFilterMemory,
  saveFilterMemory,
  clearFilterMemory
} from '@/utils/dateUtils'

export default {
  name: 'AppDateRangePicker',
  components: { AppDatePicker, AppDateTimePicker },
  props: {
    modelValue: {
      type: Object,
      default: () => ({ start: '', end: '' })
    },
    label: { type: String, default: '' },
    hint: { type: String, default: '' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    withTime: { type: Boolean, default: false },
    /** filter | form */
    mode: { type: String, default: 'filter' },
    emptyLabel: { type: String, default: FILTER_EMPTY_LABEL },
    showShortcuts: { type: Boolean, default: true },
    /** 当前页面记忆 key，如 graduation.students.dateRange */
    memoryKey: { type: String, default: '' },
    restoreMemory: { type: Boolean, default: true }
  },
  emits: ['update:modelValue', 'change', 'clear'],
  computed: {
    start() { return (this.modelValue && this.modelValue.start) || '' },
    end() { return (this.modelValue && this.modelValue.end) || '' },
    hasValue() { return !isEmptyDate(this.start) || !isEmptyDate(this.end) },
    shortcuts() { return FILTER_SHORTCUTS },
    rangeError() {
      const r = validateRange(this.start, this.end)
      return r.ok ? '' : r.message
    }
  },
  created() {
    if (this.restoreMemory && this.memoryKey && this.mode === 'filter' && !this.hasValue) {
      const mem = loadFilterMemory(this.memoryKey)
      if (mem && (mem.start || mem.end)) {
        this.emitValue({ start: mem.start || '', end: mem.end || '' })
      }
    }
  },
  methods: {
    emitValue(next) {
      const v = { start: next.start || '', end: next.end || '' }
      this.$emit('update:modelValue', v)
      this.$emit('change', v)
      if (this.memoryKey && this.mode === 'filter') {
        if (!v.start && !v.end) clearFilterMemory(this.memoryKey)
        else saveFilterMemory(this.memoryKey, v)
      }
    },
    onStart(v) { this.emitValue({ start: v, end: this.end }) },
    onEnd(v) { this.emitValue({ start: this.start, end: v }) },
    clear() {
      this.emitValue({ start: '', end: '' })
      this.$emit('clear')
    },
    applyShortcut(s) {
      const r = s.range()
      this.emitValue({ start: r.start || '', end: r.end || '' })
    }
  }
}
</script>

<style scoped>
.app-dr { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-dr__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary, #64748b);
  display: flex; align-items: center; gap: 4px;
}
.app-dr__label i { color: var(--danger-600, #dc2626); font-style: normal; }
.app-dr__hint-inline { font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.app-dr__inputs {
  display: flex; flex-wrap: wrap; align-items: flex-start; gap: 8px;
}
.app-dr__inputs :deep(.app-date),
.app-dr__inputs :deep(.app-dt) { flex: 1; min-width: 140px; }
.app-dr__sep {
  align-self: center; color: var(--text-tertiary, #94a3b8); font-size: 12px; padding-top: 2px;
}
.app-dr__clear {
  height: 28px; padding: 0 8px; margin-top: 2px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: 6px; background: #fff;
  color: var(--text-secondary, #64748b); font-size: 12px; cursor: pointer;
}
.app-dr__clear:hover { color: var(--danger-600, #dc2626); }
.app-dr__empty { margin: 0; font-size: 12px; color: var(--text-tertiary, #94a3b8); }
.app-dr__err { margin: 0; font-size: 12px; color: var(--danger-600, #dc2626); }
.app-dr__shortcuts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.app-dr__chip {
  height: 24px; padding: 0 8px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: 999px; background: #fff;
  color: var(--text-secondary, #64748b);
  font-size: 12px; cursor: pointer;
}
.app-dr__chip:hover {
  border-color: var(--primary-500, #2563eb);
  color: var(--primary-600, #2563eb);
  background: var(--primary-50, #eff6ff);
}
.app-dr__chip:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
