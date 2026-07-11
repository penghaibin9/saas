<template>
  <section class="app-stats-toolbar">
    <div class="app-stats-toolbar__fields">
      <div v-for="field in fields" :key="field.key" class="app-stats-toolbar__field">
        <span class="app-stats-toolbar__label">{{ field.label }}</span>
        <AppDateRangePicker
          v-if="field.type === 'dateRange'"
          :model-value="valueOf(field.key) || { start: '', end: '' }"
          mode="filter"
          :show-shortcuts="field.showShortcuts !== false"
          :memory-key="field.memoryKey || ''"
          @update:model-value="setValue(field.key, $event)"
        />
        <AppSelect
          v-else
          :model-value="valueOf(field.key)"
          :options="field.options || []"
          :placeholder="field.placeholder || '全部'"
          size="compact"
          @update:model-value="setValue(field.key, $event)"
        />
      </div>
    </div>
    <div class="app-stats-toolbar__actions">
      <span v-if="hint" class="app-stats-toolbar__hint">{{ hint }}</span>
      <AppButton variant="secondary" @click="$emit('reset')">重置</AppButton>
      <AppButton variant="primary" :loading="loading" @click="$emit('search', localValue)">查询</AppButton>
      <AppButton v-if="exportable" variant="secondary" :loading="exporting" @click="$emit('export', localValue)">导出</AppButton>
    </div>
  </section>
</template>

<script>
/**
 * AppStatsToolbar — 统计报表筛选条。
 * fields: [{ key, label, type: 'select'|'dateRange', options?, placeholder?, memoryKey? }]
 */
import { AppButton } from '@/components/ui'
import AppSelect from '../form/AppSelect.vue'
import AppDateRangePicker from '../date/AppDateRangePicker.vue'

export default {
  name: 'AppStatsToolbar',
  components: { AppButton, AppSelect, AppDateRangePicker },
  props: {
    modelValue: { type: Object, default: () => ({}) },
    fields: { type: Array, default: () => [] },
    hint: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    exporting: { type: Boolean, default: false },
    exportable: { type: Boolean, default: true }
  },
  emits: ['update:modelValue', 'change', 'search', 'reset', 'export'],
  computed: {
    localValue() {
      return this.modelValue || {}
    }
  },
  methods: {
    valueOf(key) {
      return this.localValue[key] ?? ''
    },
    setValue(key, value) {
      const next = { ...this.localValue, [key]: value }
      this.$emit('update:modelValue', next)
      this.$emit('change', next)
    }
  }
}
</script>

<style scoped>
.app-stats-toolbar {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: var(--radius-md);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.96));
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.app-stats-toolbar__fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(168px, 1fr));
  gap: 12px 14px;
  flex: 1;
  min-width: 0;
}
.app-stats-toolbar__field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}
.app-stats-toolbar__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  font-weight: var(--font-weight-semibold);
}
.app-stats-toolbar__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-stats-toolbar__hint {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
  padding-right: 6px;
}
@media (max-width: 860px) {
  .app-stats-toolbar {
    align-items: stretch;
    flex-direction: column;
  }
  .app-stats-toolbar__actions {
    justify-content: flex-start;
  }
}
</style>
