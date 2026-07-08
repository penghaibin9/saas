<template>
  <div class="app-ddl" :class="{ 'is-disabled': disabled }">
    <label v-if="label" class="app-ddl__label">
      {{ label }}<i v-if="required">*</i>
      <span v-if="hint" class="app-ddl__hint-inline">{{ hint }}</span>
    </label>
    <div class="app-ddl__row">
      <input
        class="app-ddl__control"
        type="datetime-local"
        :value="inner"
        :disabled="disabled"
        step="60"
        :aria-label="label || '截止时间'"
        @change="onNativeChange"
      />
      <button
        v-if="clearable && inner && !disabled"
        type="button"
        class="app-ddl__clear"
        title="清空"
        @click="clear"
      >清空</button>
    </div>
    <AppDateDisplay
      v-if="showStatus"
      :value="modelValue"
      mode="deadline"
      :status="status"
      :archived="archived"
      :completed="completed"
      class="app-ddl__status"
    />
    <div v-if="showShortcuts" class="app-ddl__shortcuts">
      <button
        v-for="s in shortcutList"
        :key="s.key"
        type="button"
        class="app-ddl__chip"
        :disabled="disabled || (s.key === 'batch' && !batchDeadline)"
        :title="s.key === 'batch' && !batchDeadline ? '当前无批次截止时间' : ''"
        @click="applyShortcut(s)"
      >{{ s.label }}</button>
    </div>
  </div>
</template>

<script>
/**
 * AppDeadlinePicker — 截止时间选择。
 * 选日期后默认落到 23:59；提供「今天/明天/本周五/7/14/30 天 / 批次截止 / 清空」快捷项。
 */
import AppDateDisplay from './AppDateDisplay.vue'
import {
  toDateTimeInputValue,
  withDeadlineTime,
  DEADLINE_SHORTCUTS,
  isEmptyDate
} from '@/utils/dateUtils'

export default {
  name: 'AppDeadlinePicker',
  components: { AppDateDisplay },
  props: {
    modelValue: { type: [String, Date], default: '' },
    label: { type: String, default: '截止时间' },
    hint: { type: String, default: '默认到当日 23:59' },
    required: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    showShortcuts: { type: Boolean, default: true },
    showStatus: { type: Boolean, default: true },
    /** 批次截止：string / Date，或从 batch 对象取 endDate */
    batchDeadline: { type: [String, Date], default: '' },
    batch: { type: Object, default: null },
    status: { type: String, default: '' },
    archived: { type: Boolean, default: false },
    completed: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'change', 'clear'],
  computed: {
    resolvedBatchDeadline() {
      if (!isEmptyDate(this.batchDeadline)) return this.batchDeadline
      if (this.batch) {
        return this.batch.endDate || this.batch.endAt || this.batch.deadline || ''
      }
      return ''
    },
    inner() {
      return toDateTimeInputValue(this.modelValue)
    },
    shortcutList() {
      const list = [...DEADLINE_SHORTCUTS]
      // 在「清空」前插入批次项
      const clearIdx = list.findIndex((s) => s.key === 'clear')
      const batchItem = {
        key: 'batch',
        label: '使用当前批次截止时间',
        value: () => {
          const raw = this.resolvedBatchDeadline
          return isEmptyDate(raw) ? '' : withDeadlineTime(raw)
        }
      }
      if (clearIdx >= 0) list.splice(clearIdx, 0, batchItem)
      else list.push(batchItem)
      return list
    }
  },
  methods: {
    normalize(v) {
      if (!v) return ''
      // 用户只改日期时，保证时分落到 23:59；若已显式选了非 00:00 则保留
      if (/T00:00$/.test(v) || !v.includes('T')) {
        return withDeadlineTime(v)
      }
      // 若只有日期部分从 date 选过来
      if (/^\d{4}-\d{2}-\d{2}$/.test(v)) return withDeadlineTime(v)
      return v
    },
    onNativeChange(e) {
      const raw = e.target.value || ''
      const v = this.normalize(raw)
      this.$emit('update:modelValue', v)
      this.$emit('change', v)
    },
    clear() {
      this.$emit('update:modelValue', '')
      this.$emit('clear')
      this.$emit('change', '')
    },
    applyShortcut(s) {
      const v = typeof s.value === 'function' ? s.value() : s.value
      this.$emit('update:modelValue', v || '')
      this.$emit('change', v || '')
      if (!v) this.$emit('clear')
    },
    /** 供外层：基于批次初始化 */
    applyBatchDefault() {
      const raw = this.resolvedBatchDeadline
      if (isEmptyDate(raw)) return
      const v = withDeadlineTime(raw)
      this.$emit('update:modelValue', v)
      this.$emit('change', v)
    }
  }
}
</script>

<style scoped>
.app-ddl { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.app-ddl__label {
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  color: var(--text-secondary, #64748b);
  display: flex; align-items: center; gap: 4px;
}
.app-ddl__label i { color: var(--danger-600, #dc2626); font-style: normal; }
.app-ddl__hint-inline { font-weight: 400; color: var(--text-tertiary, #94a3b8); margin-left: 4px; }
.app-ddl__row { display: flex; align-items: center; gap: 6px; }
.app-ddl__control {
  flex: 1; min-width: 0; height: 34px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: var(--radius-base, 6px);
  background: var(--bg-card, #fff);
  color: var(--text-primary, #0f172a);
  font: inherit; font-size: var(--font-size-sm, 13px);
  padding: 0 8px; outline: none;
}
.app-ddl__control:focus {
  border-color: var(--primary-500, #2563eb);
  box-shadow: 0 0 0 3px var(--primary-50, #eff6ff);
}
.app-ddl.is-disabled .app-ddl__control {
  background: var(--bg-section-blue, #f8fafc);
  color: var(--text-tertiary, #94a3b8);
  cursor: not-allowed;
}
.app-ddl__clear {
  flex-shrink: 0; height: 28px; padding: 0 8px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: 6px; background: #fff;
  color: var(--text-secondary, #64748b);
  font-size: 12px; cursor: pointer;
}
.app-ddl__clear:hover { color: var(--danger-600, #dc2626); border-color: var(--danger-600, #dc2626); }
.app-ddl__status { margin-top: 2px; }
.app-ddl__shortcuts { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
.app-ddl__chip {
  height: 24px; padding: 0 8px;
  border: 1px solid var(--border-base, #e2e8f0);
  border-radius: 999px; background: #fff;
  color: var(--text-secondary, #64748b);
  font-size: 12px; cursor: pointer;
}
.app-ddl__chip:hover:not(:disabled) {
  border-color: var(--primary-500, #2563eb);
  color: var(--primary-600, #2563eb);
  background: var(--primary-50, #eff6ff);
}
.app-ddl__chip:disabled { opacity: 0.45; cursor: not-allowed; }
</style>
